"""Master Logsheet import endpoints."""
from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, BackgroundTasks
import uuid
import datetime
from app.services.import_service import parse_batch
from app.middleware.auth import get_current_user, get_safety_manager
from app.db import pg
from app.db.db_models import MasterLogsheetStaging, Occurrence, Hazard, FlightDiversion, SafetyDeficiency, Report
from app.db.rls import set_current_identity, identity_from_user, clear_current_identity
from app.db.session import get_engine
from sqlalchemy import text
import asyncio

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
    if isinstance(tenant_id, str):
        try:
            tenant_uuid = uuid.UUID(tenant_id)
        except ValueError:
            tenant_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"tenant:{tenant_id}")
    else:
        tenant_uuid = tenant_id
    try:
        mapping, unmapped, staged = parse_batch(file.file, file.filename or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Parse failed: {e}")

    batch_id = str(uuid.uuid4())
    staging_rows = []
    for row in staged:
        staging_rows.append({
            "batch_id": batch_id,
            "tenant_id": tenant_id,
            "row_number": row["row_number"],
            "raw_data": row["raw_data"],
            "mapped_data": row["mapped_data"],
            "destination_tables": row["destination_tables"],
            "validation_status": "pending",
        })

    try:
        async with get_engine().begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"),
                {"t": str(tenant_uuid)}
            )
            if staging_rows:
                import json
                for row in staging_rows:
                    row["id"] = str(uuid.uuid4())
                    row["raw_data"] = json.dumps(row["raw_data"])
                    row["mapped_data"] = json.dumps(row["mapped_data"])
                await conn.execute(
                    text("""
                        INSERT INTO master_logsheet_staging 
                        (id, batch_id, tenant_id, row_number, raw_data, mapped_data, destination_tables, validation_status)
                        VALUES (:id, :batch_id, :tenant_id, :row_number, :raw_data, :mapped_data, :destination_tables, :validation_status)
                    """),
                    staging_rows
                )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Database staging failed: {str(e)}")

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
    set_current_identity(identity_from_user(user))
    rows = pg.fetch_all(
        MasterLogsheetStaging,
        where=[
            MasterLogsheetStaging.batch_id == batch_id,
            MasterLogsheetStaging.tenant_id == tenant_id,
        ],
    )
    return {"rows": rows}


def process_promote_batch(batch_id: str, tenant_id_raw: str, tenant_uuid):
    import datetime

    async def _run():
        async with get_engine().begin() as conn:
            # CRITICAL: Use the UUID for RLS context
            await conn.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"),
                {"t": str(tenant_uuid)}
            )

            result = await conn.execute(
                text("SELECT * FROM master_logsheet_staging WHERE batch_id = :bid AND validation_status = 'pending'"),
                {"bid": batch_id}
            )
            rows = result.mappings().all()
            if not rows:
                return

            for row in rows:
                mapped = row.get("mapped_data") or {}
                dests = row.get("destination_tables") or []
                dest = dests[0] if dests else None

                rpt_type = "voluntary"
                if dest in ["occurrences", "flight_diversions"]:
                    rpt_type = "mandatory"

                await conn.execute(
                    text("""
                        INSERT INTO reports (tenant_id, report_type, status, narrative, location, occurrence_date)
                        VALUES (:tenant_id, :report_type, :status, :narrative, :location, :occurrence_date)
                    """),
                    {
                        "tenant_id": tenant_uuid,
                        "report_type": rpt_type,
                        "status": mapped.get("status", "Open"),
                        "narrative": mapped.get("description", "Imported"),
                        "location": mapped.get("concerned_department", "Unknown"),
                        "occurrence_date": datetime.datetime.now(datetime.timezone.utc),
                    }
                )

            await conn.execute(
                text("UPDATE master_logsheet_staging SET validation_status = 'promoted', promoted_at = NOW() WHERE batch_id = :bid"),
                {"bid": batch_id}
            )

    asyncio.run(_run())


@router.post("/{batch_id}/promote")
async def promote_import(
    batch_id: str,
    background_tasks: BackgroundTasks,
    user=Depends(get_safety_manager),
):
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "No tenant context")

    # 1. Determine the tenant UUID (same logic as before)
    if isinstance(tenant_id, str):
        try:
            tenant_uuid = uuid.UUID(tenant_id)
        except ValueError:
            tenant_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"tenant:{tenant_id}")
    else:
        tenant_uuid = tenant_id

    # 2. Fetch pending rows in an isolated transaction (bypassing the bridge session)
    from sqlalchemy import text

    try:
        async with get_engine().begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"),
                {"t": str(tenant_uuid)}
            )
            result = await conn.execute(
                text("""
                    SELECT * FROM master_logsheet_staging 
                    WHERE batch_id = :bid AND tenant_id = :tid AND validation_status = 'pending'
                """),
                {"bid": batch_id, "tid": tenant_id}
            )
            rows = result.mappings().all()
    except Exception as e:
        raise HTTPException(500, f"Database fetch failed: {str(e)}")

    if not rows:
        raise HTTPException(404, "No pending rows found.")

    # 3. Queue background task
    background_tasks.add_task(process_promote_batch, batch_id, tenant_id, tenant_uuid)
    return {
        "success": True,
        "batch_id": batch_id,
        "message": "Import started in background.",
        "promoted_rows": len(rows),
    }


@router.delete("/{batch_id}")
async def discard_import(batch_id: str, user=Depends(get_safety_manager)):
    tenant_id = user.get("tenant_id")
    pg.delete(MasterLogsheetStaging, "batch_id", batch_id)
    return {"success": True}
