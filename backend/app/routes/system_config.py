# ============================================================================
# FILE: system_config.py
# PATH: backend/app/routes/system_config.py
# PURPOSE: System Configs surface for the SUPER_ADMIN console (Phase 3A.2).
#
#          Reads expose the permitted configuration inventory (feature flags,
#          tenant settings) and read-only platform configuration. Writes are
#          restricted to the permitted key set, are performed through the
#          SECURITY DEFINER function `set_tenant_config_key` and are written to
#          the durable audit trail in the same transaction.
#
#          Access: SUPER_ADMIN only (`get_admin_user`). Writes additionally
#          require the admin setup key, matching the other admin provisioning
#          endpoints (RC-1).
#
#          NON-GOALS: no route here can edit the audit trail, reporter
#          contacts, tenant lifecycle status or any platform secret.
# ============================================================================

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field

from app.middleware.auth import get_admin_user
from app.services import system_config_service
from app.services.setup_key import verify_setup_key

router = APIRouter()


class ConfigKeyUpdateRequest(BaseModel):
    """Body for a single permitted key change."""

    setup_key: str = Field(..., description="Admin setup key (SETUP_SECRET)")
    value: Any = Field(..., description="New value for the key")


@router.get("/registry")
async def get_config_registry(user: Dict[str, Any] = Depends(get_admin_user)):
    """The permitted configuration inventory + read-only platform config."""
    return {
        "keys": system_config_service.registry(),
        "platform": system_config_service.platform_config(),
        "requested_by_role": user.get("role"),
    }


@router.get("/tenants")
async def list_tenant_configs(user: Dict[str, Any] = Depends(get_admin_user)):
    """Every tenant with its permitted configuration values."""
    tenants = await system_config_service.list_tenants()
    return {"tenants": tenants, "total": len(tenants)}


@router.get("/{tenant_slug}")
async def get_tenant_config(
    tenant_slug: str,
    user: Dict[str, Any] = Depends(get_admin_user),
):
    """One tenant's permitted configuration values."""
    tenant = await system_config_service.tenant_config(tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.put("/{tenant_slug}/keys/{key}")
async def update_tenant_config_key(
    tenant_slug: str,
    key: str,
    req: ConfigKeyUpdateRequest,
    user: Dict[str, Any] = Depends(get_admin_user),
):
    """Apply one permitted configuration key for one tenant (SUPER_ADMIN).

    The change is written by `set_tenant_config_key` (SECURITY DEFINER), which
    appends a `SYSTEM_CONFIG_UPDATED` event to the durable audit chain in the
    same transaction. Unknown keys and read-only (derived) keys are rejected.
    """
    verify_setup_key(req.setup_key)
    try:
        result = await system_config_service.apply_key(
            tenant_slug,
            key,
            req.value,
            actor=user.get("email") or user.get("uid"),
            actor_role=user.get("role"),
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"Unknown key or tenant: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # pragma: no cover - defensive
        logger.error(f"System config update failed for {tenant_slug}/{key}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update system configuration",
        )
    return {"success": True, **result}
