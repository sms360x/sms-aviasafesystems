# ============================================================================
# FILE: audit.py
# PATH: backend/app/routes/audit.py
# PURPOSE: Durable audit-trail read/verify surface (Phase 2E.2).
#
#          The trail itself is append-only and SUPER_ADMIN-readable only
#          (see supabase/migrations/20261021220000_durable_audit.sql). This
#          router exposes the chain-verification endpoint.
# ============================================================================

from fastapi import APIRouter, Depends, Query

from sqlalchemy import text

from app.db.ids import tenant_uuid
from app.db.session import session_scope
from app.middleware.auth import get_admin_user
from app.services.audit_service import hmac_key

router = APIRouter()


@router.get("/verify")
async def verify_audit(
    tenant_id: str = Query(..., description="Tenant slug whose chain to verify"),
    user: dict = Depends(get_admin_user),
):
    """Recompute the per-tenant HMAC chain and return its validity.

    SUPER_ADMIN only. Returns ``{"valid": true}`` when the chain links cleanly,
    otherwise ``{"valid": false, "broken_at_id": "<id>"}`` for the first break.
    """
    tid = tenant_uuid(str(tenant_id))
    key = hmac_key()

    async with session_scope() as session:
        result = await session.execute(
            text("SELECT public.verify_durable_chain(:tid, :key)"),
            {"tid": tid, "key": key},
        )
        broken = result.scalar_one()

    if broken is None:
        return {"valid": True}
    return {"valid": False, "broken_at_id": str(broken)}
