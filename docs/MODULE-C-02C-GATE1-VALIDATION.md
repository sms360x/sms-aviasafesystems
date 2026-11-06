# MODULE-C-02C — Gate 1 Validation Report

Date: 05 November 2026
Mode: READ-ONLY VALIDATION
Implementation authorization: NOT GRANTED

## Validation A — Backend endpoints

File: `backend/app/api/v1/tenant_hrc.py`
Router registration: `backend/app/api/v1/router.py` line 7/20 includes `tenant_hrc_router` without prefix; router itself has `prefix="/tenant-hrc"` (line 7). `v1_router` mounted at `/api/v1` in `backend/app/main.py` line 331. Therefore full paths are `/api/v1/tenant-hrc/{tenant_id}` etc. — matches the 7 reported endpoints.

All 7 endpoints are registered:
- GET `/{tenant_id}` (line 18)
- POST `/{tenant_id}/draft` (line 23)
- PUT `/{tenant_id}/draft/{record_id}` (line 28)
- POST `/{tenant_id}/publish/{record_id}` (line 33)
- POST `/{tenant_id}/new-version/{published_id}` (line 41)
- POST `/{tenant_id}/retire/{record_id}` (line 46)
- GET `/{tenant_id}/history/{code}` (line 51)

Route ordering: FastAPI evaluates in declaration order; no path collisions among the listed routes (distinct static segments). `/history/{code}` could shadow only if a tenant_id value equals "history", but tenant_id is path param consumed first at `/{tenant_id}`; a request to `/tenant-hrc/x/history/y` correctly matches history route because of extra segment. No collision.

## Validation B — Supabase client integration

`backend/app/api/v1/tenant_hrc.py` line 5 imports `from app.db.supabase_client import get_supabase_client`. This module does NOT exist anywhere in the repository (glob `backend/**/supabase_client*` returned no files). Therefore importing this router will raise `ModuleNotFoundError` at import time, meaning ALL 7 endpoints are non-functional and the v1 router import itself may fail (depending on import order). This confirms the earlier report's "assumed existing" comment is inaccurate.

The actual persistence layer is `backend/app/db/pg.py` (synchronous SQLAlchemy/Postgres bridge), not Supabase client. There is no `get_supabase_client` factory anywhere. Existing services use `app.db.pg` (e.g. `pg.fetch_all`, `pg.insert`) and `app.db.db_models` ORM models. `TenantHRCService` uses Supabase-style chained `.table(...).select(...).execute()` API which does not exist in this codebase, so even if the import were fixed, the service would fail.

There is no ORM model for `tenant_hrc_versions` in `backend/app/db/db_models.py` (grep found no `tenant_hrc_versions` / `TenantHrc` model). The table exists only in the prepared (unapplied) migration `supabase/migrations/20261104130000_tenant_hrc_and_mappings.sql`.

## Findings summary

1. Endpoints are declared but backed by a non-existent import -> module cannot be imported -> endpoints unavailable.
2. Service implementation uses a Supabase client API not present in this repository; persistence pattern is SQLAlchemy/Postgres via `app.db.pg`.
3. No ORM model for `tenant_hrc_versions` exists; migration prepared but not applied (per baseline, MODULE-C-02B prepared, not executed).
4. Auth/tenant/role checks exist in `_service` and publish endpoint, but cannot run due to import failure. Role strings checked: `TENANT_ADMIN`, `OFFICER` with department in `("safety","corporate_safety")`; SUPER_ADMIN bypasses tenant check only. Note: `publish` requires `TENANT_ADMIN`.
5. No Pydantic request/response schemas; uses `Dict[str, Any]`. Input validation minimal (direct `body["code"]` access -> KeyError on missing).
6. Error handling: service raises `RuntimeError`/`ValueError`; not translated to HTTPException, so unhandled -> 500.

## Verified facts vs assumptions

- Verified: import missing; service uses nonexistent API; no ORM model; endpoints declared; router mounting yields correct prefix.
- Assumption (not verified here): whether migration SQL has been applied to the live Supabase DB (baseline says prepared, not executed).

## Gate 1 conclusion

Implementation is NOT functional. Do not proceed to implementation without owner approval. Awaiting explicit owner approval.
