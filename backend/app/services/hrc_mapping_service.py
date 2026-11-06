from typing import List, Dict, Any
from datetime import datetime, timezone
import uuid
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError

from app.db.session import session_scope
from app.db.db_models import TenantHrcVersion, HrcCategoryMapping
from app.db.ids import tenant_uuid


class HrcMappingService:
    def __init__(self, tenant_id: str = None):
        self.tenant_id = tenant_id
        self.tenant_uuid = uuid.UUID(tenant_uuid(tenant_id)) if tenant_id else None

    async def list_reference(self, classification: str = None) -> List[Dict[str, Any]]:
        from sqlalchemy import text
        async with session_scope() as s:
            q = "SELECT * FROM hrc_reference_versions"
            params = {}
            if classification:
                q += " WHERE classification = :c"
                params["c"] = classification
            res = await s.execute(text(q), params)
            rows = res.mappings().all()
            return [dict(r) for r in rows]

    async def list_mappings(self, tenant_id: str = None) -> List[Dict[str, Any]]:
        async with session_scope() as s:
            stmt = select(HrcCategoryMapping).join(TenantHrcVersion, (HrcCategoryMapping.source_id == TenantHrcVersion.id) & (HrcCategoryMapping.source_table == "tenant_hrc_versions"))
            if tenant_id:
                tuuid = uuid.UUID(tenant_uuid(tenant_id))
                stmt = stmt.where(TenantHrcVersion.tenant_id == tuuid)
            res = await s.execute(stmt)
            out = []
            for r in res.scalars().all():
                out.append({
                    "id": str(r.id),
                    "source_table": r.source_table,
                    "source_id": str(r.source_id),
                    "target_table": r.target_table,
                    "target_id": str(r.target_id),
                    "mapping_type": r.mapping_type,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                })
            return out

    async def unmapped(self) -> List[Dict[str, Any]]:
        refs = await self.list_reference()
        mapped = await self.list_mappings()
        mapped_ids = {m["source_id"] for m in mapped} | {m["target_id"] for m in mapped}
        return [r for r in refs if str(r.get("id")) not in mapped_ids]

    async def _verify_source_owner(self, s, source_id: str):
        rid = uuid.UUID(source_id)
        res = await s.execute(select(TenantHrcVersion).where(TenantHrcVersion.id == rid))
        src = res.scalar_one_or_none()
        if not src or (self.tenant_uuid and src.tenant_id != self.tenant_uuid):
            raise ValueError("source not found or not owned")
        return src

    async def create_mapping(self, source_id: str, target_id: str, mapping_type: str) -> Dict[str, Any]:
        async with session_scope() as s:
            await self._verify_source_owner(s, source_id)
            obj = HrcCategoryMapping(
                source_table="tenant_hrc_versions",
                source_id=uuid.UUID(source_id),
                target_table="hrc_reference_versions",
                target_id=uuid.UUID(target_id),
                mapping_type=mapping_type,
            )
            s.add(obj)
            try:
                await s.flush()
            except IntegrityError:
                raise ValueError("duplicate mapping")
            return {"id": str(obj.id)}

    async def delete_mapping(self, mapping_id: str) -> Dict[str, Any]:
        async with session_scope() as s:
            mid = uuid.UUID(mapping_id)
            res = await s.execute(select(HrcCategoryMapping).where(HrcCategoryMapping.id == mid))
            obj = res.scalar_one_or_none()
            if not obj:
                raise ValueError("mapping not found")
            src_res = await s.execute(select(TenantHrcVersion).where(TenantHrcVersion.id == obj.source_id))
            src = src_res.scalar_one_or_none()
            if not src or (self.tenant_uuid and src.tenant_id != self.tenant_uuid):
                raise ValueError("not authorized")
            await s.delete(obj)
            await s.flush()
            return {"id": str(mid), "deleted": True}

    async def replace_mapping(self, mapping_id: str, new_target_id: str, mapping_type: str = None) -> Dict[str, Any]:
        async with session_scope() as s:
            mid = uuid.UUID(mapping_id)
            res = await s.execute(select(HrcCategoryMapping).where(HrcCategoryMapping.id == mid))
            old = res.scalar_one_or_none()
            if not old:
                raise ValueError("mapping not found")
            src_res = await s.execute(select(TenantHrcVersion).where(TenantHrcVersion.id == old.source_id))
            src = src_res.scalar_one_or_none()
            if not src or (self.tenant_uuid and src.tenant_id != self.tenant_uuid):
                raise ValueError("not authorized")
            # delete old
            await s.delete(old)
            await s.flush()
            # create new
            new_obj = HrcCategoryMapping(
                source_table=old.source_table,
                source_id=old.source_id,
                target_table=old.target_table,
                target_id=uuid.UUID(new_target_id),
                mapping_type=mapping_type or old.mapping_type,
            )
            s.add(new_obj)
            try:
                await s.flush()
            except IntegrityError:
                raise ValueError("duplicate mapping")
            return {"old_id": str(mid), "new_id": str(new_obj.id)}