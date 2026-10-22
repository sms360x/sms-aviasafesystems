# ============================================================================
# FILE: system_config_service.py
# PATH: backend/app/services/system_config_service.py
# PURPOSE: System Configs surface for the SUPER_ADMIN console (Phase 3A.2).
#
#          Scope:
#            * Feature flags  — the tenant module toggles the shell already
#              consumes (canonical module_a_survey / module_b_srm /
#              module_c_regulator, stored in the legacy module1..module4 bag
#              that public/js/nav-config.js maps).
#            * Tenant settings — the survey-management config map
#              (rate limit, open/close dates, active flag, instructions) that
#              app/services/tenant_service.py already owns and validates.
#            * Platform configuration — READ-ONLY visibility of the canonical
#              role/department vocabulary and the audit-chain policy.
#
#          Writes never touch a table directly: they go through the
#          SECURITY DEFINER function public.set_tenant_config_key(), which
#          merges the new value, keeps undeclared keys, refreshes the derived
#          camelCase mirror and appends the durable audit event in the SAME
#          transaction.
#
#          NON-GOALS: this service does not expose the audit trail, reporter
#          contacts, tenant lifecycle status or any platform secret.
# ============================================================================

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from app.core.config import DEPARTMENT_CODES, settings
from app.db.session import is_transient_conn_error, session_scope
from app.services.audit_service import hmac_key
from app.services.tenant_service import (
    SURVEY_RATE_LIMIT_OPTIONS,
    build_config_update,
)

# ── Registry ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConfigKeySpec:
    """One permitted configuration key."""

    key: str
    target: str            # "config" (survey settings) | "modules" (feature flags)
    value_type: str        # "bool" | "int" | "text" | "date"
    label: str
    description: str
    group: str             # "feature_flags" | "tenant_settings"
    editable: bool = True
    options: Tuple[Any, ...] = ()
    legacy_keys: Tuple[str, ...] = ()   # storage keys (module flags only)
    max_length: Optional[int] = None


CONFIG_KEYS: Tuple[ConfigKeySpec, ...] = (
    ConfigKeySpec(
        key="module_a_survey",
        target="modules",
        value_type="bool",
        label="Module A — SMS Maturity Assessment",
        description=(
            "Tenant access to the Module A maturity assessment (SMS health "
            "questionnaire). Stored as the legacy `module1` flag."
        ),
        group="feature_flags",
        legacy_keys=("module1",),
    ),
    ConfigKeySpec(
        key="module_b_srm",
        target="modules",
        value_type="bool",
        label="Module B — Hazard & Risk (SRM)",
        description=(
            "Tenant access to Module B safety risk management. The CAN/CAP "
            "add-on inherits this flag. Stored as the legacy `module2` flag."
        ),
        group="feature_flags",
        legacy_keys=("module2",),
    ),
    ConfigKeySpec(
        key="module_c_regulator",
        target="modules",
        value_type="bool",
        label="Module C — PSOE audit + Regulator dashboard",
        description=(
            "Tenant access to Module C (PSOE audit and the regulator "
            "dashboard). Stored as the legacy `module3`/`module4` pair."
        ),
        group="feature_flags",
        legacy_keys=("module3", "module4"),
    ),
    ConfigKeySpec(
        key="survey_rate_limit",
        target="config",
        value_type="int",
        label="Survey daily submission limit",
        description="Maximum number of survey submissions per day for this tenant.",
        group="tenant_settings",
        options=tuple(SURVEY_RATE_LIMIT_OPTIONS),
    ),
    ConfigKeySpec(
        key="survey_open_date",
        target="config",
        value_type="date",
        label="Survey open date",
        description="Date the public survey portal opens (YYYY-MM-DD).",
        group="tenant_settings",
    ),
    ConfigKeySpec(
        key="survey_close_date",
        target="config",
        value_type="date",
        label="Survey close date",
        description="Date the public survey portal closes (YYYY-MM-DD).",
        group="tenant_settings",
    ),
    ConfigKeySpec(
        key="is_survey_active",
        target="config",
        value_type="bool",
        label="Survey open/close override",
        description=(
            "Manual override for the survey portal. When left to the derived "
            "value the portal follows the configured open/close dates."
        ),
        group="tenant_settings",
    ),
    ConfigKeySpec(
        key="survey_instructions",
        target="config",
        value_type="text",
        label="Survey instructions",
        description="Intro message shown at the top of the tenant's survey.",
        group="tenant_settings",
        max_length=2000,
    ),
)

# Read-only derived value: the CAN/CAP add-on has no stored flag of its own —
# the shell derives it from module_b_srm (public/js/nav-config.js).
DERIVED_KEYS: Tuple[Dict[str, Any], ...] = (
    {
        "key": "module_b_can_cap",
        "target": "modules",
        "value_type": "bool",
        "label": "Module B add-on — CAN/CAP register",
        "description": (
            "Derived from module_b_srm (the shell inherits the CAN/CAP "
            "register from the Module B flag). Shown for visibility only."
        ),
        "group": "feature_flags",
        "editable": False,
        "derived_from": "module_b_srm",
    },
)

_KEYS_BY_NAME: Dict[str, ConfigKeySpec] = {spec.key: spec for spec in CONFIG_KEYS}
_DERIVED_KEY_NAMES = frozenset(item["key"] for item in DERIVED_KEYS)
_CONFIG_KEY_NAMES = tuple(
    spec.key for spec in CONFIG_KEYS if spec.target == "config"
)


def _spec(key: str) -> ConfigKeySpec:
    spec = _KEYS_BY_NAME.get(str(key or "").strip())
    if spec is None:
        raise KeyError(key)
    return spec


# ── Validation ──────────────────────────────────────────────────────────────


def _validate(spec: ConfigKeySpec, value: Any) -> Any:
    """Validate + normalize a value for a permitted key.

    `None` is the explicit *clear* request: the key is set to a JSON null
    (or removed, for the date fields, which follow the tenant-config merge
    semantics) so the tenant falls back to the platform default.
    """
    if value is None:
        if spec.value_type == "date":
            # Dates clear through the empty-string semantics of
            # tenant_service.build_config_update (the key is removed and the
            # derived mirror entry is dropped).
            return ""
        return None

    if spec.value_type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in ("true", "false"):
            return value.strip().lower() == "true"
        raise ValueError(f"{spec.key} must be a boolean")

    if spec.value_type == "int":
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError(f"{spec.key} must be a number")
        try:
            number = int(str(value).strip())
        except (TypeError, ValueError):
            raise ValueError(f"{spec.key} must be a number")
        if spec.options and number not in spec.options:
            raise ValueError(
                f"{spec.key} must be one of "
                f"{', '.join(str(o) for o in spec.options)}"
            )
        return number

    if spec.value_type == "date":
        if not isinstance(value, str):
            raise ValueError(f"{spec.key} must be a YYYY-MM-DD string")
        candidate = value.strip()[:10]
        if not candidate:
            # Empty value clears the field (same semantics as
            # tenant_service.build_config_update).
            return ""
        try:
            from datetime import date as _date

            _date.fromisoformat(candidate)
        except ValueError:
            raise ValueError(f"{spec.key} must be a YYYY-MM-DD date")
        return candidate

    if spec.value_type == "text":
        if not isinstance(value, str):
            raise ValueError(f"{spec.key} must be text")
        if spec.max_length and len(value) > spec.max_length:
            raise ValueError(
                f"{spec.key} must be at most {spec.max_length} characters"
            )
        return value

    raise ValueError(f"unsupported value type for {spec.key}")


# ── Registry + platform view ────────────────────────────────────────────────


def registry() -> List[Dict[str, Any]]:
    """The permitted key inventory (what the console is allowed to edit)."""
    out: List[Dict[str, Any]] = []
    for spec in CONFIG_KEYS:
        out.append(
            {
                "key": spec.key,
                "target": spec.target,
                "value_type": spec.value_type,
                "label": spec.label,
                "description": spec.description,
                "group": spec.group,
                "editable": spec.editable,
                "options": list(spec.options),
                "max_length": spec.max_length,
                "storage_keys": list(spec.legacy_keys),
            }
        )
    out.extend(dict(item) for item in DERIVED_KEYS)
    return out


def platform_config() -> Dict[str, Any]:
    """Read-only platform configuration (roles, departments, audit policy)."""
    return {
        "canonical_roles": list(settings.CANONICAL_ROLES),
        "department_codes": [
            {"code": code, "label": label} for code, label in DEPARTMENT_CODES
        ],
        "cross_tenant_roles": list(settings.CROSS_TENANT_ROLES),
        "super_admin_roles": list(settings.SUPER_ADMIN_ROLES),
        "tenant_admin_roles": list(settings.TENANT_ADMIN_ROLES),
        "environment": settings.ENVIRONMENT,
        "rls_enforcement_enabled": bool(settings.RLS_ENFORCEMENT_ENABLED),
        "audit_chain": {
            "policy": "append-only, per-tenant HMAC-SHA256 chain",
            "storage": "public.durable_audit_logs",
            "read_access": "SUPER_ADMIN",
            "write_path": "append_audit_event() (SECURITY DEFINER)",
            "mutation": "none — no update, delete, reorder or repair path exists",
            "hmac_key_configured": bool(settings.AUDIT_HMAC_KEY),
        },
    }


# ── Tenant reads ────────────────────────────────────────────────────────────


async def _tenant_rows() -> List[Dict[str, Any]]:
    """Every tenant row (definer read view), read-only with one retry."""
    rows: List[Any] = []
    for attempt in range(2):
        try:
            async with session_scope() as session:
                result = await session.execute(
                    text(
                        "SELECT slug, name, tenant_uuid, kind, status, module_flags, "
                        "config, survey_config FROM public.admin_tenant_view()"
                    )
                )
                rows = result.fetchall()
            break
        except Exception as exc:  # noqa: BLE001 - re-raised unless transient
            if attempt == 0 and (
                isinstance(exc, TimeoutError) or is_transient_conn_error(exc)
            ):
                continue
            raise

    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "slug": row[0],
                "name": row[1],
                "tenant_id": str(row[2]),
                "kind": row[3],
                "status": row[4],
                "module_flags": row[5] or {},
                "config": row[6] or {},
                "survey_config": row[7] or {},
            }
        )
    return out


def _flag_values(row: Dict[str, Any]) -> Dict[str, Any]:
    """Canonical flag values for a tenant row (derived keys included)."""
    modules = row.get("module_flags") or {}
    values: Dict[str, Any] = {}
    for spec in CONFIG_KEYS:
        if spec.target != "modules":
            continue
        if len(spec.legacy_keys) == 1:
            values[spec.key] = bool(modules.get(spec.legacy_keys[0]))
        else:
            values[spec.key] = any(
                bool(modules.get(key)) for key in spec.legacy_keys
            )
    # module_b_can_cap inherits module_b_srm in the shell.
    values["module_b_can_cap"] = values.get("module_b_srm", False)
    return values


def _config_values(row: Dict[str, Any]) -> Dict[str, Any]:
    config = row.get("config") or {}
    return {key: config.get(key) for key in _CONFIG_KEY_NAMES}


def _tenant_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tenant_id": row["tenant_id"],
        "slug": row["slug"],
        "name": row["name"],
        "kind": row["kind"],
        "status": row["status"],
        "values": {**_flag_values(row), **_config_values(row)},
    }


async def list_tenants() -> List[Dict[str, Any]]:
    """Every tenant with its permitted config values."""
    rows = await _tenant_rows()
    return [_tenant_payload(row) for row in rows]


async def tenant_config(slug: str) -> Optional[Dict[str, Any]]:
    """One tenant's permitted config values (None when unknown)."""
    rows = await _tenant_rows()
    for row in rows:
        if row["slug"] == slug:
            return _tenant_payload(row)
    return None


# ── Writes ──────────────────────────────────────────────────────────────────


async def apply_key(
    slug: str,
    key: str,
    value: Any,
    actor: Optional[str] = None,
    actor_role: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply one permitted config key for one tenant.

    The write is performed by the SECURITY DEFINER function
    `set_tenant_config_key`, which merges the value into the tenant row and
    appends the durable audit event in the same transaction.
    """
    if key in _DERIVED_KEY_NAMES:
        raise ValueError(f"{key} is read-only (derived value)")
    spec = _spec(key)
    if not spec.editable:
        raise ValueError(f"{spec.key} is read-only")
    normalized = _validate(spec, value)
    rows = await _tenant_rows()
    row = next((r for r in rows if r["slug"] == slug), None)
    if row is None:
        raise KeyError(slug)

    if spec.target == "config":
        updated_config, survey_config = build_config_update(
            {spec.key: normalized},
            row.get("config") or {},
            row.get("survey_config") or {},
        )
        if normalized is None:
            # Explicit clear: the key stays in the map with a null value, which
            # every reader treats as "not set" (the platform default applies).
            updated_config = dict(updated_config)
            updated_config[spec.key] = None
        payload = updated_config
        allowed = ",".join(_CONFIG_KEY_NAMES)
        extra = survey_config
    else:
        modules = dict(row.get("module_flags") or {})
        for legacy in spec.legacy_keys:
            modules[legacy] = normalized
        payload = modules
        allowed = ",".join(spec.legacy_keys)
        extra = None

    async with session_scope() as session:
        result = await session.execute(
            text(
                "SELECT public.set_tenant_config_key("
                ":slug, :target, (:value)::jsonb, string_to_array(:allowed, ','), "
                "(:extra)::jsonb, :audit_key, (:audit_value)::jsonb, "
                ":actor, :actor_role, :hmac_key)"
            ),
            {
                "slug": slug,
                "target": spec.target,
                "value": json.dumps(payload),
                "allowed": allowed,
                "extra": json.dumps(extra) if extra is not None else None,
                "audit_key": spec.key,
                "audit_value": json.dumps(normalized),
                "actor": actor,
                "actor_role": actor_role,
                "hmac_key": hmac_key(),
            },
        )
        result.scalar_one()

    updated = await tenant_config(slug)
    return {
        "tenant": updated,
        "key": spec.key,
        "value": normalized,
        "applied_at": None,
    }
