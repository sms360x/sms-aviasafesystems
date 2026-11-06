# ============================================================================
# FILE: backend/app/services/demo_eligibility.py
# PURPOSE: Central shared-DEMO eligibility resolution (DEMO-ELIGIBILITY-02C,
#          Section A).
#
#          Single source of truth for deciding whether an authenticated tenant
#          may read the shared demonstration dataset. Decides purely from the
#          provisioned tenant record (tenants.module_access.shared_demo) plus
#          the tenant's operational state --- never from a manually maintained
#          airline-slug list.
#
#          Fails closed: any failure to validate the tenant or establish its
#          operational state denies shared-demo access (returns eligible=False).
# ============================================================================

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from loguru import logger

from app.core.config import settings
from app.db import pg
from app.db.db_models import (
    Can,
    Cap,
    Hazard,
    Report,
    Tenant,
)

# Core operational workflow tables. A tenant that owns >= 1 non-demo (live) row
# in any of these is operationally LIVE and must not receive shared-demo reads
# (DEMO-to-LIVE transition, Section E). Administrative ACTIVE status alone does
# NOT make a tenant operational; only genuine operational records do.
OPERATIONAL_TABLES = (Report, Hazard, Can, Cap)

# Result cache: slug -> (DemoEligibility, expires_at_monotonic).
#
# NOTE: disabled for initial deployment (TTL = 0). The cache is intentionally
# not invalidated after write/provisioning transitions, so any non-zero TTL
# could serve stale eligibility (e.g. a tenant that just became operationally
# LIVE could keep reading shared-demo rows for up to the TTL window). With
# TTL = 0, every request re-validates against the tenant registry and the
# operational-state probe, so fail-closed behavior is synchronous.
_CACHE: Dict[str, Tuple[DemoEligibility, float]] = {}
_CACHE_TTL_SECONDS = 0.0


@dataclass(frozen=True)
class DemoEligibility:
    """Outcome of the shared-DEMO eligibility assessment."""

    eligible: bool
    reason: str
    tenant_slug: Optional[str] = None
    tenant_uuid: Optional[str] = None
    shared_demo: bool = False
    operational: bool = False
    read_tenant_slug: Optional[str] = None


def _now() -> float:
    return time.monotonic()


def _cached(slug: str) -> Optional[DemoEligibility]:
    # Cache disabled (TTL = 0) for initial deployment: every request
    # re-validates against the tenant registry so fail-closed is synchronous.
    if _CACHE_TTL_SECONDS <= 0:
        return None
    entry = _CACHE.get(slug)
    if entry is None:
        return None
    result, expires_at = entry
    if _now() > expires_at:
        _CACHE.pop(slug, None)
        return None
    return result


def _cache(slug: str, result: DemoEligibility) -> None:
    _CACHE[slug] = (result, _now() + _CACHE_TTL_SECONDS)


def invalidate(slug: Optional[str] = None) -> None:
    """Drop the cached eligibility for one tenant (or every tenant).

    Called by write paths so a tenant's first genuine operational record (or a
    provisioning change to module_access.shared_demo) takes effect without
    waiting out the TTL.
    """
    if slug is None:
        _CACHE.clear()
        return
    _CACHE.pop(str(slug).strip().lower(), None)


def _tenant_row(slug: str) -> Optional[dict]:
    """Resolve the authenticated tenant's registry row. None when unknown or
    the registry cannot be read (fail closed)."""
    try:
        return pg.fetch_by(Tenant, "slug", slug)
    except Exception as exc:  # pragma: no cover - defensive
        from loguru import logger

        logger.warning(f"demo-eligibility: tenant registry lookup failed for {slug}: {exc}")
        return None


def _tenant_disabled(row: dict) -> bool:
    """True when the tenant record is disabled (inactive or terminal status)."""
    if row.get("active") is False:
        return True
    status = str(row.get("status") or "").strip().upper()
    return status in {"SUSPENDED", "RETIRED", "CANCELLED", "CANCELED", "INACTIVE"}


def _tenant_operational(tenant_uuid_value) -> Optional[bool]:
    """True when the tenant owns any operational (is_demo=false) row in a core
    workflow table. None when the operational state cannot be established
    reliably (DB error) --- the caller must fail closed."""
    if tenant_uuid_value is None:
        return None
    try:
        for model in OPERATIONAL_TABLES:
            rows = pg.fetch_all(
                model,
                where=[
                    model.tenant_id == tenant_uuid_value,
                    model.is_demo == False,  # noqa: E712
                ],
                limit=1,
            )
            if rows:
                return True
        return False
    except Exception as exc:  # pragma: no cover - defensive
        from loguru import logger

        logger.warning(
            f"demo-eligibility: operational-state probe failed: {exc} (failing closed)"
        )
        return None


def assess_demo_eligibility(user: dict) -> DemoEligibility:
    """Decide whether the authenticated tenant may read the shared demo dataset.

    Rules (in order; first rejecting rule wins):
      1. The caller must be authenticated to a tenant (user.tenant_id present).
      2. The tenant must exist in the Supabase tenant registry (unknown -> reject).
      3. The tenant must not be disabled (inactive / terminal status -> reject).
      4. tenants.module_access.shared_demo must be exactly true (not opted in -> reject).
      5. The tenant must not be operationally LIVE: no operational (is_demo=false)
         rows in reports/hazards/cans/caps. If the operational state cannot be
         established reliably -> fail closed (reject).
      6. When eligible: read_tenant_slug = GLOBAL_DEMO_TENANT_ID (the shared
         seeded dataset, e.g. "sita-air"); the caller's own tenant id is never
         leaked into the shared-demo rows.
    """
    user = user or {}
    tenant_slug = (user.get("tenant_id") or "").strip().lower()
    if not tenant_slug:
        logger.info(
            "demo-eligibility",
            extra={
                "event": "demo_eligibility",
                "tenant_slug": None,
                "role": str(user.get("role") or ""),
                "reason": "no authenticated tenant",
                "eligible": False,
                "shared_demo": False,
                "source_configured": bool(
                    getattr(settings, "GLOBAL_DEMO_TENANT_ID", None)
                ),
            },
        )
        return DemoEligibility(
            eligible=False,
            reason="no authenticated tenant",
            tenant_slug=None,
        )

    cached = _cached(tenant_slug)
    if cached is not None:
        return cached

    # 1+2. Tenant must exist in the registry.
    row = _tenant_row(tenant_slug)
    if row is None:
        result = DemoEligibility(
            eligible=False,
            reason="unknown tenant",
            tenant_slug=tenant_slug,
        )
        _cache(tenant_slug, result)
        logger.info(
            "demo-eligibility",
            extra={
                "event": "demo_eligibility",
                "tenant_slug": tenant_slug,
                "role": str(user.get("role") or ""),
                "reason": result.reason,
                "eligible": result.eligible,
                "shared_demo": result.shared_demo,
                "source_configured": bool(
                    getattr(settings, "GLOBAL_DEMO_TENANT_ID", None)
                ),
            },
        )
        return result

    tenant_uuid_value = row.get("id")

    # 3. Reject disabled tenants.
    if _tenant_disabled(row):
        result = DemoEligibility(
            eligible=False,
            reason="tenant disabled",
            tenant_slug=tenant_slug,
            tenant_uuid=str(tenant_uuid_value) if tenant_uuid_value else None,
        )
        _cache(tenant_slug, result)
        logger.info(
            "demo-eligibility",
            extra={
                "event": "demo_eligibility",
                "tenant_slug": tenant_slug,
                "role": str(user.get("role") or ""),
                "reason": result.reason,
                "eligible": result.eligible,
                "shared_demo": result.shared_demo,
                "source_configured": bool(
                    getattr(settings, "GLOBAL_DEMO_TENANT_ID", None)
                ),
            },
        )
        return result

    # 4. Require explicit module_access.shared_demo == true.
    module_access = row.get("module_access") or {}
    if not isinstance(module_access, dict) or module_access.get("shared_demo") is not True:
        result = DemoEligibility(
            eligible=False,
            reason="shared demo not enabled",
            tenant_slug=tenant_slug,
            tenant_uuid=str(tenant_uuid_value) if tenant_uuid_value else None,
        )
        _cache(tenant_slug, result)
        logger.info(
            "demo-eligibility",
            extra={
                "event": "demo_eligibility",
                "tenant_slug": tenant_slug,
                "role": str(user.get("role") or ""),
                "reason": result.reason,
                "eligible": result.eligible,
                "shared_demo": result.shared_demo,
                "source_configured": bool(
                    getattr(settings, "GLOBAL_DEMO_TENANT_ID", None)
                ),
            },
        )
        return result

    # 5. DEMO-to-LIVE: the tenant must not be operationally LIVE. Fail closed
    #    when the operational state cannot be established.
    operational = _tenant_operational(tenant_uuid_value)
    if operational is None:
        result = DemoEligibility(
            eligible=False,
            reason="operational state undeterminable",
            tenant_slug=tenant_slug,
            tenant_uuid=str(tenant_uuid_value) if tenant_uuid_value else None,
        )
        _cache(tenant_slug, result)
        logger.info(
            "demo-eligibility",
            extra={
                "event": "demo_eligibility",
                "tenant_slug": tenant_slug,
                "role": str(user.get("role") or ""),
                "reason": result.reason,
                "eligible": result.eligible,
                "shared_demo": result.shared_demo,
                "source_configured": bool(
                    getattr(settings, "GLOBAL_DEMO_TENANT_ID", None)
                ),
            },
        )
        return result
    if operational:
        result = DemoEligibility(
            eligible=False,
            reason="tenant is operationally live",
            tenant_slug=tenant_slug,
            tenant_uuid=str(tenant_uuid_value) if tenant_uuid_value else None,
            operational=True,
        )
        _cache(tenant_slug, result)
        logger.info(
            "demo-eligibility",
            extra={
                "event": "demo_eligibility",
                "tenant_slug": tenant_slug,
                "role": str(user.get("role") or ""),
                "reason": result.reason,
                "eligible": result.eligible,
                "shared_demo": result.shared_demo,
                "source_configured": bool(
                    getattr(settings, "GLOBAL_DEMO_TENANT_ID", None)
                ),
            },
        )
        return result

    # 6. Eligible: read the shared seeded dataset under GLOBAL_DEMO_TENANT_ID.
    #    No silent fallback: if the source is not configured, fail closed.
    read_tenant_slug = (
        getattr(settings, "GLOBAL_DEMO_TENANT_ID", None) or ""
    ).strip().lower() or None
    if not read_tenant_slug:
        result = DemoEligibility(
            eligible=False,
            reason="shared demo source not configured",
            tenant_slug=tenant_slug,
            tenant_uuid=str(tenant_uuid_value) if tenant_uuid_value else None,
        )
        _cache(tenant_slug, result)
        logger.info(
            "demo-eligibility",
            extra={
                "event": "demo_eligibility",
                "tenant_slug": tenant_slug,
                "role": str(user.get("role") or ""),
                "reason": result.reason,
                "eligible": result.eligible,
                "shared_demo": result.shared_demo,
                "source_configured": False,
            },
        )
        return result
    result = DemoEligibility(
        eligible=True,
        reason="ok",
        tenant_slug=tenant_slug,
        tenant_uuid=str(tenant_uuid_value) if tenant_uuid_value else None,
        shared_demo=True,
        operational=False,
        read_tenant_slug=read_tenant_slug,
    )
    _cache(tenant_slug, result)
    logger.info(
        "demo-eligibility",
        extra={
            "event": "demo_eligibility",
            "tenant_slug": tenant_slug,
            "role": str(user.get("role") or ""),
            "reason": result.reason,
            "eligible": result.eligible,
            "shared_demo": result.shared_demo,
            "read_tenant_slug": result.read_tenant_slug,
            "source_configured": True,
        },
    )
    return result


def demo_read_tenant(user: dict) -> Tuple[Optional[str], bool, DemoEligibility]:
    """Convenience: (effective_read_slug, used_shared_demo, eligibility).

    When the tenant is demo-eligible, returns (GLOBAL_DEMO_TENANT_ID, True,
    eligibility). Otherwise returns (caller's own tenant slug, False,
    eligibility).
    """
    eligibility = assess_demo_eligibility(user)
    if eligibility.eligible and eligibility.read_tenant_slug:
        return eligibility.read_tenant_slug, True, eligibility
    own = (user.get("tenant_id") or "").strip().lower() or None
    return own, False, eligibility


def demo_write_blocked(user: dict) -> Optional[str]:
    """Return a rejection reason when the tenant is demo-eligible (a read-only
    shared-demo consumer) and therefore must not mutate anything, else None.

    Demonstration users read the shared seeded workflow; they may not create,
    modify, delete, submit, approve, or otherwise mutate operational records
    while accessing it. Enforced server-side (never relying on hidden frontend
    buttons). LIVE tenants are never blocked by this guard (they never read
    shared-demo data, so they are never demo-eligible).
    """
    eligibility = assess_demo_eligibility(user)
    if eligibility.eligible:
        return (
            "shared-demo tenant is read-only: "
            "create/modify/delete/submit/approve mutations are not permitted "
            "while accessing the shared seeded workflow"
        )
    return None
