# ============================================================================
# FILE: audit.py
# PATH: backend/app/routes/audit.py
# PURPOSE: Durable audit-trail read/verify surface (Phase 2E.2) plus the
#          SUPER_ADMIN Audit Chain Viewer (Phase 3A.2).
#
#          The trail itself is append-only and SUPER_ADMIN-readable only
#          (see supabase/migrations/20261021220000_durable_audit.sql). This
#          router is READ-ONLY: it exposes chain inspection (list / detail /
#          per-tenant summary / verification). There is no update, delete,
#          reorder, backfill or "repair chain" endpoint — and none may be
#          added: `durable_audit_logs` is append-only by design and only
#          `append_audit_event` (SECURITY DEFINER) may write to it.
#
#          The HMAC secret never leaves the server. Clients receive a verdict
#          per event ("valid" / "broken" / "unlinked"), never the key and never
#          enough material to recompute a hash themselves.
# ============================================================================

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy import text

from app.db.ids import tenant_uuid
from app.db.session import session_scope
from app.middleware.auth import get_admin_user
from app.services.audit_service import hmac_key
from app.services.audit_view_service import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    get_event,
    list_events,
    tenant_chains,
)

router = APIRouter()


def _parse_dt(value: Optional[str], field: str) -> Optional[str]:
    """Validate an ISO-8601 boundary and return it as an ISO string."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")).isoformat()
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"{field} must be an ISO-8601 timestamp"
        )


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


@router.get("/events")
async def list_audit_events(
    tenant_id: Optional[str] = Query(
        None, description="Tenant slug; omit to read across every tenant"
    ),
    action: Optional[str] = Query(None, description="Exact event type"),
    actor_role: Optional[str] = Query(
        None, description="Canonical role recorded on the event"
    ),
    date_from: Optional[str] = Query(None, description="ISO-8601 lower bound"),
    date_to: Optional[str] = Query(None, description="ISO-8601 upper bound"),
    verification: Optional[str] = Query(
        None, description="Filter: valid | broken | unlinked"
    ),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_admin_user),
):
    """List durable audit events (SUPER_ADMIN only, read-only).

    Every row is tenant-labelled. Cross-tenant reads are permitted for
    SUPER_ADMIN and are explicitly flagged as cross-tenant in the response.
    """
    try:
        events = await list_events(
            tenant_slug=tenant_id,
            action=action,
            actor_role=actor_role,
            date_from=_parse_dt(date_from, "date_from"),
            date_to=_parse_dt(date_to, "date_to"),
            verification=verification,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        **events,
        "cross_tenant": not tenant_id,
        "requested_by_role": user.get("role"),
    }


@router.get("/events/{event_id}")
async def get_audit_event(
    event_id: str,
    user: dict = Depends(get_admin_user),
):
    """Return one audit event with its chain link (SUPER_ADMIN only)."""
    try:
        uuid.UUID(str(event_id))
    except (ValueError, AttributeError, TypeError):
        # Not an event id at all — answer 404 rather than letting the uuid
        # cast fail deep in the database.
        raise HTTPException(status_code=404, detail="Audit event not found")

    event = await get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return event


@router.get("/tenants")
async def list_audit_tenant_chains(
    user: dict = Depends(get_admin_user),
):
    """Per-tenant chain summary: volume, chain segments and structural breaks.

    SUPER_ADMIN only, read-only. `status` is `valid` when the partition has
    no forked and no dangling links, otherwise `broken`.
    """
    chains: List[Dict[str, Any]] = await tenant_chains()
    return {
        "tenants": chains,
        "total": len(chains),
        "cross_tenant": True,
    }
