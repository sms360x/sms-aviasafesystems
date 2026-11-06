from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from app.middleware.auth import get_current_user
from app.services.tenant_hrc_service import TenantHRCService

router = APIRouter(prefix="/tenant-hrc", tags=["Tenant HRC"])

class DraftCreate(BaseModel):
    code: str
    title: str
    description: Optional[str] = None

class DraftUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

def _service(user, tenant_id):
    if user.get("tenant_id") != tenant_id and user.get("role") not in ("SUPER_ADMIN",):
        raise HTTPException(403, "tenant access denied")
    role = user.get("role")
    if role not in ("TENANT_ADMIN", "OFFICER") or (role == "OFFICER" and user.get("claims", {}).get("department") not in ("safety", "corporate_safety")):
        raise HTTPException(403, "not authorized")
    return TenantHRCService(tenant_id)

def _handle(exc):
    if isinstance(exc, ValueError):
        raise HTTPException(404, str(exc))
    if isinstance(exc, IntegrityError):
        raise HTTPException(409, "conflict")
    raise HTTPException(500, "internal error")

from sqlalchemy.exc import IntegrityError

@router.get("/{tenant_id}", response_model=List[Dict[str, Any]])
async def list_tenant_hrc(tenant_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    svc = _service(user, tenant_id)
    try:
        return await svc.list_tenant_hrcs()
    except Exception as e:
        _handle(e)

@router.post("/{tenant_id}/draft", response_model=Dict[str, Any])
async def create_draft(tenant_id: str, body: DraftCreate, user: Dict[str, Any] = Depends(get_current_user)):
    svc = _service(user, tenant_id)
    try:
        return await svc.create_draft(body.code, body.title, body.description, user.get("email"))
    except Exception as e:
        _handle(e)

@router.put("/{tenant_id}/draft/{record_id}", response_model=Dict[str, Any])
async def update_draft(tenant_id: str, record_id: str, body: DraftUpdate, user: Dict[str, Any] = Depends(get_current_user)):
    svc = _service(user, tenant_id)
    try:
        return await svc.update_draft(record_id, body.title, body.description)
    except Exception as e:
        _handle(e)

@router.post("/{tenant_id}/publish/{record_id}", response_model=Dict[str, Any])
async def publish(tenant_id: str, record_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    if user.get("role") != "TENANT_ADMIN":
        raise HTTPException(403, "approval not permitted")
    svc = _service(user, tenant_id)
    try:
        return await svc.publish(record_id, user.get("email"))
    except Exception as e:
        _handle(e)

@router.post("/{tenant_id}/new-version/{published_id}", response_model=Dict[str, Any])
async def new_version(tenant_id: str, published_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    svc = _service(user, tenant_id)
    try:
        return await svc.new_version(published_id, user.get("email"))
    except Exception as e:
        _handle(e)

@router.post("/{tenant_id}/retire/{record_id}", response_model=Dict[str, Any])
async def retire(tenant_id: str, record_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    if user.get("role") != "TENANT_ADMIN":
        raise HTTPException(403, "approval not permitted")
    svc = _service(user, tenant_id)
    try:
        return await svc.retire(record_id, user.get("email"))
    except Exception as e:
        _handle(e)

@router.get("/{tenant_id}/history/{code}", response_model=List[Dict[str, Any]])
async def history(tenant_id: str, code: str, user: Dict[str, Any] = Depends(get_current_user)):
    svc = _service(user, tenant_id)
    try:
        return await svc.history(code)
    except Exception as e:
        _handle(e)