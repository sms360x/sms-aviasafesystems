"""Master Logsheet import endpoints."""
from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
import uuid
from app.services.import_service import parse_batch
from app.middleware.auth import get_current_user, get_safety_manager
from app.db import pg
from app.db.db_models import MasterLogsheetStaging

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])


@router.post("/master-logsheet")
async def import_master_logsheet(
    file: UploadFile = File(...),
    user=Depends(get_safety_manager),
):
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "No tenant context")
    try:
        mapping, unmapped, staged = parse_batch(file.file, file.filename or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Parse failed: {e}")

    batch_id = str(uuid.uuid4())
    for row in staged:
        pg.insert(MasterLogsheetStaging, {
            "batch_id": batch_id,
            "tenant_id": tenant_id,
            "row_number": row["row_number"],
            "raw_data": row["raw_data"],
            "mapped_data": row["mapped_data"],
            "destination_tables": row["destination_tables"],
            "validation_status": "pending",
        })

    return {
        "batch_id": batch_id,
        "total_rows": len(staged),
        "staged_rows": len(staged),
        "unmapped_columns": unmapped,
        "preview": staged[:10],
    }


@router.get("/{batch_id}/preview")
async def preview_import(batch_id: str, user=Depends(get_safety_manager)):
    tenant_id = user.get("tenant_id")
    rows = pg.fetch_all(
        MasterLogsheetStaging,
        where=[
            MasterLogsheetStaging.batch_id == batch_id,
            MasterLogsheetStaging.tenant_id == tenant_id,
        ],
    )
    return {"rows": rows}


@router.post("/{batch_id}/promote")
async def promote_import(batch_id: str, user=Depends(get_safety_manager)):
    tenant_id = user.get("tenant_id")
    pg.update(
        MasterLogsheetStaging,
        "batch_id",
        batch_id,
        {"validation_status": "promoted", "promoted_at": None},
    )
    return {"success": True, "batch_id": batch_id}


@router.delete("/{batch_id}")
async def discard_import(batch_id: str, user=Depends(get_safety_manager)):
    tenant_id = user.get("tenant_id")
    pg.delete(MasterLogsheetStaging, "batch_id", batch_id)
    return {"success": True}
