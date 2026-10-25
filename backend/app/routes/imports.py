"""Master Logsheet import endpoints."""
from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
import uuid
import datetime
from app.services.import_service import parse_batch
from app.middleware.auth import get_current_user, get_safety_manager
from app.db import pg
from app.db.db_models import MasterLogsheetStaging, Occurrence, Hazard, FlightDiversion, SafetyDeficiency, Report

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])


def sanitize_taxonomy(tax):
    allowed = {"Organizational", "Technical", "Human", "Environmental"}
    if not tax:
        return "Organizational"
    tax_lower = str(tax).lower()
    for a in allowed:
        if a.lower() in tax_lower:
            return a
    return "Organizational"


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
    tenant_id_raw = user.get("tenant_id")
    if not tenant_id_raw:
        raise HTTPException(400, "No tenant context")
    tenant_id = tenant_id_raw
    if isinstance(tenant_id_raw, str):
        try:
            tenant_uuid = uuid.UUID(tenant_id_raw)
        except ValueError:
            tenant_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"tenant:{tenant_id_raw}")
    else:
        tenant_uuid = tenant_id_raw

    rows = pg.fetch_all(
        MasterLogsheetStaging,
        where=[
            MasterLogsheetStaging.batch_id == batch_id,
            MasterLogsheetStaging.tenant_id == tenant_id,
            MasterLogsheetStaging.validation_status == "pending",
        ],
    )
    if not rows:
        raise HTTPException(404, "No pending rows found.")

    existing_diversions = pg.fetch_all(
        FlightDiversion,
        where=[FlightDiversion.tenant_id == tenant_uuid],
    )
    existing_diversion_ids = {r.get("diversion_id") for r in existing_diversions}

    hazards_to_insert = []
    occurrences_to_insert = []
    diversions_to_insert = []
    deficiencies_to_insert = []
    reports_to_insert = []
    staging_ids = []

    try:
        for row in rows:
            mapped = row.get("mapped_data") or {}
            dests = row.get("destination_tables") or []
            staging_ids.append(row.get("id"))

            def val(k, d=None):
                v = mapped.get(k)
                return v if v is not None else d

            for dest in dests:
                if dest == "occurrences":
                    occurrences_to_insert.append({
                        "tenant_id": str(tenant_uuid),
                        "occurrence_id": val("sequence_number"),
                        "date": _parse_dt(val("occurrence_date") or val("reported_date")) or datetime.datetime.now(datetime.timezone.utc),
                        "source": val("source"),
                        "description": val("description"),
                        "status": val("status", "Open"),
                        "department": val("concerned_department"),
                        "remarks": val("remarks"),
                    })
                    reports_to_insert.append({
                        "tenant_id": tenant_uuid,
                        "report_type": "mandatory",
                        "status": val("status", "Open"),
                        "narrative": val("description", "Imported"),
                        "location": val("concerned_department", "Unknown"),
                        "occurrence_date": _parse_dt(val("occurrence_date") or val("reported_date")) or datetime.datetime.now(datetime.timezone.utc),
                    })
                elif dest == "hazards":
                    hazards_to_insert.append({
                        "tenant_id": tenant_uuid,
                        "hazard_id": val("sequence_number", f"IMP-{uuid.uuid4()}"),
                        "title": (val("description", "Imported hazard"))[:100],
                        "description": val("description", "") or "",
                        "source": val("source", "Import"),
                        "source_id": "",
                        "taxonomy": sanitize_taxonomy(val("taxonomy")),
                        "priority": val("priority", "M"),
                        "status": val("status", "Open"),
                        "threat": val("threat"),
                        "consequence": val("consequence"),
                        "top_event": val("top_event"),
                        "remarks": val("remarks"),
                    })
                    reports_to_insert.append({
                        "tenant_id": tenant_uuid,
                        "report_type": "voluntary",
                        "status": val("status", "Open"),
                        "narrative": val("description", "Imported"),
                        "location": val("concerned_department", "Unknown"),
                        "occurrence_date": _parse_dt(val("occurrence_date") or val("reported_date")) or datetime.datetime.now(datetime.timezone.utc),
                    })
                elif dest == "flight_diversions":
                    diversion_id_val = val("sequence_number", f"IMP-{uuid.uuid4()}")
                    if diversion_id_val in existing_diversion_ids:
                        continue
                    sector = val("flight_sector", "") or ""
                    if "-" in str(sector):
                        parts = [p.strip() for p in str(sector).split("-", 1)]
                    else:
                        parts = [str(sector).strip(), str(sector).strip()]
                    diversions_to_insert.append({
                        "tenant_id": tenant_uuid,
                        "diversion_id": diversion_id_val,
                        "date": _parse_dt(val("occurrence_date") or val("reported_date")) or datetime.datetime.now(datetime.timezone.utc),
                        "flight_number": val("flight_number", "UNKNOWN"),
                        "aircraft_registration": val("aircraft_registration", "UNKNOWN"),
                        "sector_from": parts[0] or "UNKNOWN",
                        "sector_to": parts[1] if len(parts) > 1 else (parts[0] or "UNKNOWN"),
                        "diverted_to": val("diverted_to", "UNKNOWN"),
                        "reason": val("reason", "Imported"),
                        "description": val("description", "") or "",
                        "status": val("status", "Open"),
                        "remarks": val("remarks"),
                    })
                    reports_to_insert.append({
                        "tenant_id": tenant_uuid,
                        "report_type": "mandatory",
                        "status": val("status", "Open"),
                        "narrative": val("description", "Imported"),
                        "location": val("concerned_department", "Unknown"),
                        "occurrence_date": _parse_dt(val("occurrence_date") or val("reported_date")) or datetime.datetime.now(datetime.timezone.utc),
                    })
                elif dest == "safety_deficiencies":
                    deficiencies_to_insert.append({
                        "tenant_id": tenant_uuid,
                        "source": val("source", "Import"),
                        "description": val("description", "") or "",
                        "status": val("status", "Open"),
                    })
                    reports_to_insert.append({
                        "tenant_id": tenant_uuid,
                        "report_type": "voluntary",
                        "status": val("status", "Open"),
                        "narrative": val("description", "Imported"),
                        "location": val("concerned_department", "Unknown"),
                        "occurrence_date": _parse_dt(val("occurrence_date") or val("reported_date")) or datetime.datetime.now(datetime.timezone.utc),
                    })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed while building promote data: {str(e)}")

    try:
        if occurrences_to_insert:
            pg.bulk_insert(Occurrence, occurrences_to_insert)
        if hazards_to_insert:
            pg.bulk_insert(Hazard, hazards_to_insert)
        if diversions_to_insert:
            pg.bulk_insert(FlightDiversion, diversions_to_insert)
        if deficiencies_to_insert:
            pg.bulk_insert(SafetyDeficiency, deficiencies_to_insert)
        if reports_to_insert:
            pg.bulk_insert(Report, reports_to_insert)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed during bulk insert: {str(e)}")

    try:
        pg.bulk_update(
            MasterLogsheetStaging,
            staging_ids,
            {"validation_status": "promoted", "promoted_at": datetime.datetime.now(datetime.timezone.utc)},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed during staging update: {str(e)}")

    return {"success": True, "batch_id": batch_id, "promoted_rows": len(staging_ids)}


@router.delete("/{batch_id}")
async def discard_import(batch_id: str, user=Depends(get_safety_manager)):
    tenant_id = user.get("tenant_id")
    pg.delete(MasterLogsheetStaging, "batch_id", batch_id)
    return {"success": True}