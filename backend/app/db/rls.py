# ============================================================================
# FILE: rls.py
# PATH: backend/app/db/rls.py
# PURPOSE: Phase 2C.3 — carry the authenticated request identity into the
#          database session so RLS policies can read it (D7/D8).
#
#          A request-scoped ContextVar holds the identity. A SQLAlchemy
#          `after_begin` listener sets the five `app.current_*` session GUCs on
#          every transaction that has an identity (harmless under the owner
#          role), and additionally runs `SET LOCAL ROLE authenticated` only when
#          settings.RLS_ENFORCEMENT_ENABLED is true.
#
#          Non-authenticated contexts (seeders, workers, migrations) have no
#          identity, so the listener does nothing and the owner connection is
#          unchanged. The GUCs are transaction-local, so nothing leaks between
#          requests.
# ============================================================================

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Dict, Optional

# The request identity, or None for non-authenticated contexts. A ContextVar is
# per-task: a value set while handling one request is not visible to another.
_current_identity: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "rls_current_identity", default=None
)


def set_current_identity(identity: Optional[Dict[str, Any]]):
    """Set (or clear) the request identity for the current context."""
    return _current_identity.set(identity)


def clear_current_identity() -> None:
    _current_identity.set(None)


def get_current_identity() -> Optional[Dict[str, Any]]:
    return _current_identity.get()


def identity_from_user(user: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Build the RLS identity from the authenticated request user dict.

    ``tenant_uuid`` is derived deterministically from the tenant slug
    (``app.db.ids.tenant_uuid``); ``user_uid`` is the Firebase uid (the value
    the ``users.uid`` column and the ``app.current_user`` GUC both carry).
    """
    if not user:
        return None
    slug = user.get("tenant_id")
    tenant_uuid_value: Optional[str] = None
    if slug:
        try:
            from app.db.ids import tenant_uuid

            tenant_uuid_value = tenant_uuid(str(slug))
        except Exception:
            tenant_uuid_value = None
    return {
        "tenant_uuid": tenant_uuid_value,
        "tenant_slug": str(slug) if slug else None,
        "role": user.get("role"),
        "department": user.get("department"),
        "user_uid": user.get("uid"),
    }


def _q(value: Any) -> str:
    """Quote a value as a SQL string literal (single quotes doubled)."""
    return "'" + str(value if value is not None else "").replace("'", "''") + "'"


def _apply_identity(conn) -> None:
    """SQLAlchemy ``begin`` handler: set the session GUCs (+ role).

    Runs when a connection's transaction begins. The statements execute within
    that transaction, so ``set_config(..., true)`` and ``SET LOCAL`` are
    transaction-scoped and reset at commit/rollback. Values are quoted literals
    (uuid / slug / canonical role / Firebase uid — all controlled values).
    """
    identity = _current_identity.get()
    if not identity:
        return

    conn.exec_driver_sql(
        "SELECT set_config('app.current_tenant', "
        f"{_q(identity.get('tenant_uuid'))}, true)"
    )
    conn.exec_driver_sql(
        "SELECT set_config('app.current_tenant_slug', "
        f"{_q(identity.get('tenant_slug'))}, true)"
    )
    conn.exec_driver_sql(
        "SELECT set_config('app.current_role', "
        f"{_q(identity.get('role'))}, true)"
    )
    # 2D.2: "safety department" is a constraint on VSR-related activity, not a
    # role. Policies that gate VSR work need the department alongside the role.
    conn.exec_driver_sql(
        "SELECT set_config('app.current_department', "
        f"{_q(identity.get('department'))}, true)"
    )
    conn.exec_driver_sql(
        "SELECT set_config('app.current_user', "
        f"{_q(identity.get('user_uid'))}, true)"
    )

    from app.core.config import settings

    if settings.RLS_ENFORCEMENT_ENABLED:
        conn.exec_driver_sql("SET LOCAL ROLE authenticated")


def install_rls_listener(engine) -> None:
    """Attach the ``begin`` listener to an async engine.

    ``engine.sync_engine`` is the event target for async engines; the same
    listener therefore fires for both the async session path and the
    bridge-session path (both draw connections from this engine).
    """
    from sqlalchemy import event

    event.listen(engine.sync_engine, "begin", _apply_identity)
