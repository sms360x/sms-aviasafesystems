# ============================================================================
# FILE: auth.py
# PATH: backend/app/middleware/auth.py
# VERSION: 1.0.0
# DATE CREATED: 2026-07-03
# DATE REVISED: 2026-07-03
# PURPOSE: Authentication middleware for FastAPI routes.
#          Verifies Firebase ID tokens and extracts user claims.
# AUTHOR: Ghanshyam Acharya
# CODE OWNER: AviaSafeSystems
# ============================================================================

from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, Optional
from loguru import logger

from app.core.config import settings
from app.db import pg
from app.db.db_models import Tenant, UserProfile
from app.db.rls import clear_current_identity, identity_from_user, set_current_identity
from app.firebase import verify_firebase_token
from app.middleware.tenant_status_cache import get_status, set_status
from app.services.tenant_service import get_tenant_slug_from_email

security = HTTPBearer()


def _lookup_tenant_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Search all tenant rows for a safety_manager with matching email.

    This is a fallback when Firebase Auth custom claims are not available
    in the ID token (known Firebase propagation issue). Sourced from the
    Postgres tenants table (safety_manager JSONB column).
    """
    try:
        docs = pg.fetch_all(
            Tenant,
            where=[Tenant.safety_manager["email"].astext == email],
            limit=50,
        )
        for td in docs:
            sm = td.get("safety_manager")
            if sm and sm.get("email") == email:
                return {"tenant_id": td.get("tenant_id") or td.get("slug") or td.get("id"), "role": "AIRLINE_ADMIN"}
            # Also check for CAAN_SMD emails in a separate config
        return None
    except Exception as e:
        logger.warning(f"Tenant lookup failed for {email}: {e}")
        return None


def _tenant_slug(tenant_uuid_value: Any) -> Optional[str]:
    """Resolve a users.tenant_id (uuid) to the tenant slug (or None).

    The users row stores tenant_id as the deterministic uuid5('tenant:'+slug)
    FK, but the request user dict carries the slug.
    """
    if tenant_uuid_value is None:
        return None
    try:
        rows = pg.fetch_all(Tenant, where=[Tenant.id == tenant_uuid_value])
        if rows:
            return rows[0].get("slug") or rows[0].get("id")
    except Exception as e:
        logger.warning(f"Tenant slug lookup failed for {tenant_uuid_value}: {e}")
    from app.db.ids import tenant_slug
    return tenant_slug(tenant_uuid_value)


def resolve_user_context(email: str) -> Dict[str, Any]:
    """Resolve the request's role and tenant from the users row.

    2A.5 (SME ruling 2026-10-12): one user = one tenant = one role (ICAO
    accountability). The ``users`` row is the authoritative identity source.
    The ``memberships`` table is retained as a Super-Admin reporting
    substrate only and is NOT read on any operational path. A missing users
    row yields ``role=None`` / ``tenant_id=None`` and a WARN log; protected
    endpoints then deny.
    """
    urow = None
    if email:
        try:
            urow = pg.fetch_by(UserProfile, "email", email)
        except Exception as e:
            logger.warning(f"User lookup failed for {email}: {e}")

    if urow is None:
        logger.warning(f"No users row for user (email={email}).")
        return {"role": None, "tenant_id": None}

    ctx = {
        "role": urow.get("role"),
        "tenant_id": _tenant_slug(urow.get("tenant_id")),
    }
    # 2C.7: carry the users-row department (authoritative) so the
    # department-based raw-VSR rule does not depend on token freshness. Omitted
    # when NULL/empty to keep the resolved shape minimal.
    department = urow.get("department")
    if department:
        ctx["department"] = department
    return ctx


SUSPENDED_TENANT_DETAIL = (
    "This organization account is currently inactive or suspended. "
    "Please contact support@aviasafesystems.com."
)


def _tenant_is_suspended(tenant_id: str) -> bool:
    """True when the tenants-table governance status is SUSPENDED.

    Fail-open by design: a missing row, missing status or a database error
    must never lock a user out of the platform — only an explicit
    ``status == "SUSPENDED"`` blocks access.

    The status read is served from a short-TTL in-memory cache
    (middleware/tenant_status_cache) so the per-request auth check does not
    query the tenants table on every request — that lookup was the single most
    frequent slow statement in production profiling. Tenant status writes
    invalidate the entry immediately.
    """
    cached = get_status(tenant_id)
    if cached is not None:
        return cached == "SUSPENDED"
    try:
        td = pg.fetch_by(Tenant, "slug", tenant_id)
        set_status(tenant_id, ((td.get("status") or "") if td else ""))
        return (td.get("status") or "") == "SUSPENDED" if td else False
    except Exception as e:
        logger.warning(f"Tenant status check failed for {tenant_id}: {e}")
        return False


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, Any]:
    token = credentials.credentials
    decoded_token = verify_firebase_token(token)

    if not decoded_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = decoded_token.get('email', '')
    role = decoded_token.get('role', settings.ROLE_DEFAULT)
    tenant_id = decoded_token.get('tenant_id')
    department = decoded_token.get('department') or None

    resolved = resolve_user_context(email)
    role = resolved["role"]
    tenant_id = resolved["tenant_id"]
    # 2C.7: the users-row department is authoritative; fall back to the token
    # claim only when the users row has none.
    department = resolved.get("department") or department

    if tenant_id and role not in settings.CROSS_TENANT_ROLES and _tenant_is_suspended(tenant_id):
        logger.warning(f"Suspended tenant access denied for {email} (tenant={tenant_id})")
        raise HTTPException(status_code=403, detail=SUSPENDED_TENANT_DETAIL)

    logger.info(f"Authenticated user {email}: role={role}, tenant_id={tenant_id}")

    user_context = {
        "uid": decoded_token['uid'],
        "email": email,
        "role": role,
        "tenant_id": tenant_id,
        "department": department,
        "claims": {"role": role, "tenant_id": tenant_id, "department": department},
    }
    # Phase 2C.3: publish the identity for the DB session GUC listener. The
    # ContextVar is per-request (per-task); clear any residual first so a
    # reused context can never carry a stale identity.
    clear_current_identity()
    set_current_identity(identity_from_user(user_context))
    return user_context


async def get_tenant_user(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    if not user.get('tenant_id'):
        raise HTTPException(
            status_code=403,
            detail="User does not have tenant access"
        )
    return user


async def get_caan_user(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    if user.get('role') not in settings.CROSS_TENANT_ROLES:
        raise HTTPException(
            status_code=403,
            detail="CAAN_SMD role required"
        )
    return user


async def get_admin_user(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    if user.get('role') not in settings.SUPER_ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="SUPER_ADMIN role required"
        )
    return user


async def get_safety_manager(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    if user.get('role') not in settings.CROSS_TENANT_ROLES and user.get('role') not in settings.TENANT_ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Safety Manager or CAAN_SMD role required"
        )
    if user.get('role') in settings.TENANT_ADMIN_ROLES and not user.get('tenant_id'):
        raise HTTPException(
            status_code=403,
            detail="Tenant access required for Safety Manager"
        )
    return user


# Department accounts (email prefix) -> the canonical department CODE they are
# scoped to (2B.4a: codes, not labels). Used to restrict 145 / CAMO / Ops users
# to only their own department's CANs & CAPs.
DEPARTMENT_SCOPE_PREFIXES = {
    "145": "maintenance_145",
    "camo": "camo",
    "ops": "flight_ops",
}


# Roles that consume only aggregate surfaces. They are denied raw operational
# lists (hazards / CANs / CAPs / reports) at the route layer; the same matrix is
# re-enforced in RLS (defense in depth, see supabase/migrations).
AGGREGATE_ONLY_ROLES = frozenset({"ACCOUNTABLE_EXECUTIVE", "STATE_SMD"})


def resolve_role_scope(user: Dict[str, Any]) -> Dict[str, Any]:
    """Return WHERE-clause parameters that scope a raw list to the caller's role.

    - ``DEPT_ADMIN`` -> ``{"department": <user's department>}`` (own department
      only). A DEPT_ADMIN without a department is denied (least privilege).
    - everyone else -> ``{}`` (tenant scope is applied by the service layer).
    """
    role = (user or {}).get("role")
    if role in settings.DEPT_ADMIN_ROLES:
        dept = (user or {}).get("department")
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Department scope is required for this account",
            )
        return {"department": dept}
    return {}


def require_not_aggregate_only(user: Dict[str, Any], resource: str = "records") -> None:
    """Deny ACCOUNTABLE_EXECUTIVE / STATE_SMD raw-list access (403)."""
    role = (user or {}).get("role")
    if role in AGGREGATE_ONLY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{resource} is not available for aggregate-only roles",
        )


def get_department_scope(user: Dict[str, Any]) -> Optional[str]:
    """Return the department a user is restricted to based on their email prefix.

    Emails starting with ``145`` or ``camo`` belong to the Part-145 / CAMO
    departments and should only ever see CANs and CAPs for that department.
    Returns ``None`` for all other users (no restriction).
    """
    email = (user.get("email") or "").lower()
    for prefix, department in DEPARTMENT_SCOPE_PREFIXES.items():
        if email.startswith(prefix):
            return department
    return None


async def get_responsible_manager(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    allowed = (
        settings.CROSS_TENANT_ROLES
        + settings.TENANT_ADMIN_ROLES
        + settings.SAFETY_OFFICER_ROLES
        + settings.STAFF_ROLES
    )
    if user.get('role') not in allowed:
        raise HTTPException(
            status_code=403,
            detail="Responsible Manager, Safety Manager, or CAAN_SMD role required"
        )
    if not user.get('tenant_id') and user.get('role') not in settings.CROSS_TENANT_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Tenant access required"
        )
    return user


async def get_accountable_executive(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """AE-only gate (2B.4b fix). Hazard closure is an AE sign-off (Doc 9859).

    Admits only ACCOUNTABLE_EXECUTIVE for its owning tenant; denies the retired
    AIRLINE_ADMIN and cross-tenant callers (STATE_SMD / SUPER_ADMIN). Identity
    is session-derived — no request parameter sets the signer (1C.2).
    """
    if user.get('role') != "ACCOUNTABLE_EXECUTIVE":
        raise HTTPException(
            status_code=403,
            detail="Accountable Executive role required"
        )
    if not user.get('tenant_id'):
        raise HTTPException(
            status_code=403,
            detail="Tenant access required for Accountable Executive"
        )
    return user