"""Master Logsheet import endpoints."""
from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
import uuid
from app.services.import_service import parse_batch
from app.middleware.auth import get_current_user, get_safety_manager
from app.db import pg
from app.db.db_models import MasterLogsheetStaging, Occurrence, Hazard, FlightDiversion, SafetyDeficiency
import datetime
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


def _parse_dt(value):
    if value is None:
        return None
    try:
        import pandas as pd
        ts = pd.to_datetime(value, errors="coerce", dayfirst=True)
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except Exception:
        return None


@router.post("/{batch_id}/promote")
async def promote_import(batch_id: str, user=Depends(get_safety_manager)):
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "No tenant context")
    tenant_uuid = uuid.UUID(tenant_id)
    rows = pg.fetch_all(
        MasterLogsheetStaging,
        where=[
            MasterLogsheetStaging.batch_id == batch_id,
            MasterLogsheetStaging.tenant_id == tenant_id,
        ],
    )
    promoted = 0
    for row in rows:
        if row.get("validation_status") != "pending":
            continue
        if row.get("promoted_at") is not None:
            continue
        mapped = row.get("mapped_data") or {}
        dests = row.get("destination_tables") or []
        try:
            for dest in dests:
                if dest == "occurrences":
                    pg.insert(Occurrence, {
                        "tenant_id": tenant_id,
                        "occurrence_id": mapped.get("sequence_number"),
                        "date": _parse_dt(mapped.get("occurrence_date") or mapped.get("reported_date")),
                        "source": mapped.get("source"),
                        "description": mapped.get("description"),
                        "status": mapped.get("status") or "Open",
                        "department": mapped.get("concerned_department"),
                        "remarks": mapped.get("remarks"),
                    })
                elif dest == "hazards":
                    pg.insert(Hazard, {
                        "tenant_id": tenant_uuid,
                        "hazard_id": mapped.get("sequence_number") or f"IMP-{uuid.uuid4()}",
                        "title": mapped.get("description") or "Imported hazard",
                        "description": mapped.get("description") or "",
                        "source": mapped.get("source") or "Import",
                        "source_id": "",
                        "taxonomy": mapped.get("taxonomy") or "Organizational",
                        "priority": "M",
                        "status": mapped.get("status") or "Open",
                        "threat": mapped.get("threat"),
                        "consequence": mapped.get("consequence"),
                        "top_event": mapped.get("top_event"),
                        "remarks": mapped.get("remarks"),
                    })
                elif dest == "flight_diversions":
                    sector = mapped.get("flight_sector") or ""
                    if "-" in str(sector):
                        parts = [p.strip() for p in str(sector).split("-", 1)]
                    else:
                        parts = [str(sector).strip(), str(sector).strip()]
                    pg.insert(FlightDiversion, {
                        "tenant_id": tenant_uuid,
                        "diversion_id": mapped.get("sequence_number") or f"IMP-{uuid.uuid4()}",
                        "date": _parse_dt(mapped.get("occurrence_date") or mapped.get("reported_date")),
                        "flight_number": mapped.get("flight_number") or "UNKNOWN",
                        "aircraft_registration": mapped.get("aircraft_registration") or "UNKNOWN",
                        "sector_from": parts[0] or "UNKNOWN",
                        "sector_to": parts[1] if len(parts) > 1 else (parts[0] or "UNKNOWN"),
                        "diverted_to": mapped.get("diverted_to") or "UNKNOWN",
                        "reason": mapped.get("reason") or "Imported",
                        "description": mapped.get("description") or "",
                        "status": mapped.get("status") or "Open",
                        "remarks": mapped.get("remarks"),
                    })
                elif dest == "safety_deficiencies":
                    pg.insert(SafetyDeficiency, {
                        "tenant_id": tenant_uuid,
                        "source": mapped.get("source") or "Import",
                        "description": mapped.get("description") or "",
                        "status": mapped.get("status") or "Open",
                    })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to insert into {dest} for row {row.get('row_number')}: {str(e)}")
        pg.update(
            MasterLogsheetStaging,
            "id",
            row.get("id"),
            {"validation_status": "promoted", "promoted_at": datetime.datetime.now(datetime.timezone.utc)},
        )
        promoted += 1
    return {"success": True, "batch_id": batch_id, "promoted_rows": promoted}


@router.delete("/{batch_id}")
async def discard_import(batch_id: str, user=Depends(get_safety_manager)):
    tenant_id = user.get("tenant_id")
    pg.delete(MasterLogsheetStaging, "batch_id", batch_id)
    return {"success": True}
