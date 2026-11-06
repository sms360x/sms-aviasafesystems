from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from app.middleware.auth import get_current_user
from app.services.hrc_mapping_service import HrcMappingService

router = APIRouter(prefix="/hrc-mappings", tags=["HRC Mappings"])

class MappingCreate(BaseModel):
    source_id: str
    target_id: str
    mapping_type: str = "DIRECT"

class MappingReplace(BaseModel):
    new_target_id: str
    mapping_type: Optional[str] = None

def _svc(user):
    tid = user.get("tenant_id")
    if not tid:
        raise HTTPException(403, "tenant required")
    if user.get("role") != "TENANT_ADMIN":
        raise HTTPException(403, "not authorized")
    return HrcMappingService(tid)

@router.get("/references", response_model=List[Dict[str, Any]])
async def refs(classification: str = None, user: Dict[str, Any] = Depends(get_current_user)):
    return await HrcMappingService().list_reference(classification)

@router.get("/", response_model=List[Dict[str, Any]])
async def mappings(user: Dict[str, Any] = Depends(get_current_user)):
    tid = user.get("tenant_id")
    if not tid:
        raise HTTPException(403, "tenant required")
    return await HrcMappingService(tid).list_mappings(tenant_id=tid)

@router.get("/unmapped", response_model=List[Dict[str, Any]])
async def unmapped(user: Dict[str, Any] = Depends(get_current_user)):
    return await HrcMappingService().unmapped()

@router.post("/", response_model=Dict[str, Any], status_code=201)
async def create_mapping(body: MappingCreate, user: Dict[str, Any] = Depends(get_current_user)):
    svc = _svc(user)
    try:
        return await svc.create_mapping(body.source_id, body.target_id, body.mapping_type)
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.delete("/{mapping_id}", response_model=Dict[str, Any])
async def delete_mapping(mapping_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    svc = _svc(user)
    try:
        return await svc.delete_mapping(mapping_id)
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.put("/{mapping_id}", response_model=Dict[str, Any])
async def replace_mapping(mapping_id: str, body: MappingReplace, user: Dict[str, Any] = Depends(get_current_user)):
    svc = _svc(user)
    try:
        return await svc.replace_mapping(mapping_id, body.new_target_id, body.mapping_type)
    except ValueError as e:
        msg = str(e)
        if "duplicate" in msg:
            raise HTTPException(409, msg)
        raise HTTPException(400, msg)