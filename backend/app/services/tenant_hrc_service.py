from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy import select, update, insert
from sqlalchemy.exc import IntegrityError

from app.db.session import session_scope
from app.db.db_models import TenantHrcVersion
from app.db.ids import tenant_uuid
import uuid


class TenantHRCService:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.tenant_uuid = uuid.UUID(tenant_uuid(tenant_id))

    async def list_tenant_hrcs(self) -> List[Dict[str, Any]]:
        async with session_scope() as s:
            res = await s.execute(select(TenantHrcVersion).where(TenantHrcVersion.tenant_id == self.tenant_uuid))
            rows = res.scalars().all()
            return [self._to_dict(r) for r in rows]

    async def create_draft(self, code: str, title: str, description: Optional[str], created_by: str) -> Dict[str, Any]:
        async with session_scope() as s:
            obj = TenantHrcVersion(tenant_id=self.tenant_uuid, code=code, title=title, description=description,
                                  created_by=created_by, approval_status="draft", version=1)
            s.add(obj)
            await s.flush()
            return self._to_dict(obj)

    async def update_draft(self, record_id: str, title: Optional[str], description: Optional[str]) -> Dict[str, Any]:
        async with session_scope() as s:
            rid = uuid.UUID(record_id)
            res = await s.execute(select(TenantHrcVersion).where(TenantHrcVersion.id == rid, TenantHrcVersion.tenant_id == self.tenant_uuid, TenantHrcVersion.approval_status == "draft"))
            obj = res.scalar_one_or_none()
            if not obj:
                raise ValueError("draft not found or not editable")
            if title is not None:
                obj.title = title
            if description is not None:
                obj.description = description
            await s.flush()
            return self._to_dict(obj)

    async def publish(self, record_id: str, approved_by: str) -> Dict[str, Any]:
        async with session_scope() as s:
            rid = uuid.UUID(record_id)
            res = await s.execute(select(TenantHrcVersion).where(TenantHrcVersion.id == rid, TenantHrcVersion.tenant_id == self.tenant_uuid, TenantHrcVersion.approval_status == "draft"))
            obj = res.scalar_one_or_none()
            if not obj:
                raise ValueError("draft not found")
            obj.approval_status = "published"
            obj.approved_by = approved_by
            obj.approved_at = datetime.now(timezone.utc)
            await s.flush()
            return self._to_dict(obj)

    async def new_version(self, published_id: str, created_by: str) -> Dict[str, Any]:
        async with session_scope() as s:
            pid = uuid.UUID(published_id)
            res = await s.execute(select(TenantHrcVersion).where(TenantHrcVersion.id == pid, TenantHrcVersion.tenant_id == self.tenant_uuid, TenantHrcVersion.approval_status == "published"))
            src = res.scalar_one_or_none()
            if not src:
                raise ValueError("published record not found")
            # next version
            res2 = await s.execute(select(TenantHrcVersion.version).where(TenantHrcVersion.tenant_id == self.tenant_uuid, TenantHrcVersion.code == src.code).order_by(TenantHrcVersion.version.desc()).limit(1))
            next_v = (res2.scalar() or 1) + 1
            obj = TenantHrcVersion(tenant_id=self.tenant_uuid, code=src.code, title=src.title, description=src.description,
                                  created_by=created_by, approval_status="draft", version=next_v)
            s.add(obj)
            await s.flush()
            return self._to_dict(obj)

    async def retire(self, record_id: str, retired_by: str) -> Dict[str, Any]:
        async with session_scope() as s:
            rid = uuid.UUID(record_id)
            res = await s.execute(select(TenantHrcVersion).where(TenantHrcVersion.id == rid, TenantHrcVersion.tenant_id == self.tenant_uuid, TenantHrcVersion.approval_status == "published"))
            obj = res.scalar_one_or_none()
            if not obj:
                raise ValueError("published record not found")
            obj.approval_status = "deprecated"
            obj.retired_at = datetime.now(timezone.utc)
            await s.flush()
            return self._to_dict(obj)

    async def history(self, code: str) -> List[Dict[str, Any]]:
        async with session_scope() as s:
            res = await s.execute(select(TenantHrcVersion).where(TenantHrcVersion.tenant_id == self.tenant_uuid, TenantHrcVersion.code == code).order_by(TenantHrcVersion.version))
            rows = res.scalars().all()
            return [self._to_dict(r) for r in rows]

    def _to_dict(self, r):
        return {
            "id": str(r.id),
            "tenant_id": str(r.tenant_id),
            "code": r.code,
            "title": r.title,
            "description": r.description,
            "version": r.version,
            "approval_status": r.approval_status,
            "approved_by": r.approved_by,
            "approved_at": r.approved_at.isoformat() if r.approved_at else None,
            "created_by": r.created_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "effective_from": r.effective_from.isoformat() if r.effective_from else None,
            "retired_at": r.retired_at.isoformat() if r.retired_at else None,
        }