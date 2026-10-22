from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from loguru import logger

from sqlalchemy import text

from app.core.config import settings
from app.db.ids import tenant_uuid
from app.db.rls import get_current_identity
from app.db.runner import run
from app.db.session import session_scope
from app.firebase import get_db

AUDIT_COLLECTION = "audit_logs"

# 2E.2: dev-only HMAC key used when AUDIT_HMAC_KEY is unset. MUST match the
# fallback literal in supabase/migrations/20261021220000_durable_audit.sql so
# backfilled rows chain with app-appended rows.
DEV_AUDIT_HMAC_KEY = "dev-only-audit-hmac-key-2e2"

# Tenantless events (LOGIN, CAAN reads, STATE_SPT, …) chain under this partition.
GLOBAL_TENANT_UUID = tenant_uuid("__global__")

# Actions that must never carry an actor identity (2D.2 VSR anonymity).
_ANONYMOUS_ACTIONS = {
    "VSR_SUBMITTED",
    "REPORTER_CONTACT_WRITTEN",
    "REPORTER_CONTACT_READ",
    "REPORTER_CONTACT_READ_DENIED",
}

# Metadata keys stripped from anonymous events to avoid re-identifying a VSR.
_PII_METADATA_TOKENS = ("email", "ip", "reporter")


def request_context(request) -> Tuple[Optional[str], Optional[str]]:
    """Return (client_ip, request_id) from a FastAPI Request."""
    if request is None:
        return None, None
    client = getattr(request, "client", None)
    ip = client.host if client else None
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        request_id = request.headers.get("X-Request-ID")
    return ip, request_id or None


def hmac_key() -> str:
    """Resolve the durable-audit HMAC key (env, else dev-only + warning)."""
    key = settings.AUDIT_HMAC_KEY
    if not key:
        logger.warning(
            "AUDIT_HMAC_KEY is not set; using a dev-only HMAC key for the "
            "durable audit chain (insecure — set AUDIT_HMAC_KEY in production)"
        )
        key = DEV_AUDIT_HMAC_KEY
    return key


def _tenant_uuid(tenant_id: Optional[str]) -> str:
    if not tenant_id:
        return GLOBAL_TENANT_UUID
    return tenant_uuid(str(tenant_id))


def _redact(action: str, user: Optional[str], metadata: Optional[Dict[str, Any]]):
    """Return (actor_uid, metadata) with PII removed for anonymous actions."""
    meta = dict(metadata or {})
    if action in _ANONYMOUS_ACTIONS:
        actor_uid = None
        meta = {
            k: v
            for k, v in meta.items()
            if not any(t in str(k).lower() for t in _PII_METADATA_TOKENS)
        }
    else:
        actor_uid = user
    return actor_uid, meta


def _resolve_actor_role(actor_role: Optional[str]) -> Optional[str]:
    """Resolve the role the actor held when the event was recorded.

    Explicit ``actor_role`` wins; otherwise the role is taken from the
    request-scoped RLS identity (Phase 3A.2) so every request-scoped event
    records who acted in what capacity without touching the call sites.
    """
    if actor_role:
        return str(actor_role)
    identity = get_current_identity()
    if identity:
        role = identity.get("role")
        if role:
            return str(role)
    return None


def _append_event(
    tenant_id: Optional[str],
    action: str,
    actor_uid: Optional[str],
    actor_role: Optional[str],
    resource_type: Optional[str],
    resource_id: Optional[str],
    metadata: Dict[str, Any],
) -> str:
    """Append one event via the SECURITY DEFINER `append_audit_event` function."""
    import json

    tid = _tenant_uuid(tenant_id)
    meta_json = json.dumps(metadata or {})
    key = hmac_key()

    async def _go():
        async with session_scope() as session:
            result = await session.execute(
                text(
                    "SELECT public.append_audit_event("
                    ":tid, :action, :actor, :rtype, :rid, (:meta)::jsonb, :role, :key)"
                ),
                {
                    "tid": tid,
                    "action": action,
                    "actor": actor_uid,
                    "rtype": resource_type,
                    "rid": resource_id,
                    "meta": meta_json,
                    "role": actor_role,
                    "key": key,
                },
            )
            return result.scalar_one()

    return run(_go())


def log_audit(
    *,
    action: str,
    user: Optional[str] = None,
    tenant_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    ip: Optional[str] = None,
    request_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    actor_role: Optional[str] = None,
) -> None:
    """Append an entry to the durable audit trail (Postgres primary).

    Postgres `durable_audit_logs` is the system of record (append-only, HMAC
    hash-chained). Firestore remains a best-effort mirror. Failures to persist
    an audit entry must never break the business request, so both writes are
    best-effort and only logged as a warning. IP is dropped entirely (2E.1
    Q-PII-1) — `ip` is accepted for signature compatibility but not stored.

    Phase 3A.2: `actor_role` records the role the actor held at append time
    (it is evidence alongside the event, not part of the signed body, so
    existing chains keep verifying). It is derived from the request identity
    when not supplied, and is never set for anonymous VSR actions.
    """
    actor_uid, meta = _redact(action, user, metadata)
    role = None if action in _ANONYMOUS_ACTIONS else _resolve_actor_role(actor_role)
    try:
        _append_event(tenant_id, action, actor_uid, role, target_type, target_id, meta)
    except Exception as e:
        logger.warning(f"Durable audit append failed for action={action}: {e}")

    try:
        # 2E.1 Q-MIRROR-1: keep Firestore as a best-effort mirror. Firestore was
        # removed from the data plane (A1), so get_db() raises
        # NotImplementedError today; treat that as "mirror unavailable" and keep
        # going. Never let the mirror block the Postgres write.
        get_db().collection(AUDIT_COLLECTION).add(
            {
                "action": action,
                "user": actor_uid,
                "tenant_id": tenant_id,
                "target_type": target_type,
                "target_id": target_id,
                "metadata": meta,
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except NotImplementedError:
        pass
    except Exception as e:
        logger.warning(f"Audit mirror write failed for action={action}: {e}")


# ── Missing events added in 2E.2 ─────────────────────────────────────────────

def log_user_role_changed(
    uid: str, from_role: str, to_role: str, tenant_id: Optional[str] = None
) -> None:
    """Audit a role change on a user (best-effort)."""
    log_audit(
        action="USER_ROLE_CHANGED",
        user=uid,
        tenant_id=tenant_id,
        target_type="user",
        target_id=uid,
        metadata={"from_role": from_role, "to_role": to_role},
    )


def log_authorization_denied(
    user: Optional[Dict[str, Any]],
    resource: str,
    reason: str,
    tenant_id: Optional[str] = None,
) -> None:
    """Audit a 403 authorization denial (best-effort)."""
    u = user or {}
    log_audit(
        action="AUTHORIZATION_DENIED",
        user=u.get("email") or u.get("uid"),
        tenant_id=tenant_id or u.get("tenant_id"),
        target_type="resource",
        target_id=resource,
        metadata={"reason": reason, "role": u.get("role")},
    )


def log_report_read(
    user: Dict[str, Any], report_id: str, report_type: Optional[str] = None
) -> None:
    """Audit a privileged raw-report read (TENANT_ADMIN / OFFICER only)."""
    role = (user or {}).get("role")
    if role not in ("TENANT_ADMIN", "OFFICER"):
        return
    log_audit(
        action="REPORT_READ",
        user=(user or {}).get("email") or (user or {}).get("uid"),
        tenant_id=(user or {}).get("tenant_id"),
        target_type="report",
        target_id=report_id,
        metadata={"report_type": report_type},
    )
