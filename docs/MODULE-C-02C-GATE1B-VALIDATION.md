# MODULE-C-02C — Gate 1B Targeted Validation Report

Date: 05 November 2026
Mode: READ-ONLY
Authorization: Validation only

## Task 1 — PostgreSQL integration

- `backend/app/db/pg.py` is the synchronous bridge over SQLAlchemy/Postgres. Supports `fetch_all`, `fetch_by`, `insert`, `bulk_insert`, `bulk_update`, `upsert`, `update`, `delete` (lines 302-459). Transactions run per-call via `_run_on_bridge` (line 125) with begin/commit and OperationalError retry.
- ORM models live in `backend/app/db/db_models.py`; `tenant_hrc_versions` and `hrc_category_mappings` are NOT present (grep returned no matches).
- Sessions managed by `app/db/session.py` (`get_bridge_session`, `session_scope`).
- Errors: pg functions return None on no-match; exceptions propagate; no domain-specific rollback handling beyond per-call transaction.
- Atomic versioning: bridge runs each call in its own transaction; multi-step operations (new-version: select + insert) are NOT atomic across calls — concurrency risk. No row-level locking helpers exposed.

## Task 2 — SQL review

- `tenant_hrc_versions`: PK uuid, tenant_id text, code/title text, version int>0, status check, unique (tenant,code,version), partial unique index for one published per tenant/code, trigger prevents update/delete of published rows (lines 22-34). Good immutability.
- `hrc_category_mappings`: source/target table checks, trigger validates cross-tenant (lines 47-68). No unique constraint on (source_id,target_id) -> seed uses ON CONFLICT DO NOTHING which requires a unique constraint; without one, idempotency NOT guaranteed. SQL defect: add UNIQUE(source_table,source_id,target_table,target_id) or adjust seed.
- RLS enabled on both (lines 70-71) but no policies shown in this migration; relies on existing RLS conventions.
- tenant_id is text (not uuid) in tenant_hrc_versions; backend uses deterministic uuid for other tables — potential mismatch. Need verify.
- Seed resolves 5 DIRECT (CFIT,LOC-I,MAC,RE,RI) + 1 CROSS (ARC) = six correspondences. Verify script counts mappings and duplicates.

## Task 3 — HRC service logic

- `tenant_hrc_service.py`: draft create/edit, publish, new-version, retire, history, list. Uses `.single()` (line 35) which may raise on no row. `retire` (line 47) does not check status -> can retire any record including published? Trigger prevents published update at DB level, so retire on published fails at DB. `update_draft` checks draft status.
- API `_service` (tenant_hrc.py lines 9-16): tenant check + role/department. publish adds TENANT_ADMIN check (lines 35-37). retire has no extra approval check.
- Record-level ownership: service filters by tenant_id on all queries. Good.
- Transaction boundaries: none across multi-step; new_version reads then inserts separately.

## Task 4 — Mapping service contract (minimal)

- Read-only reference retrieval: list hrc_reference_versions by classification/jurisdiction.
- Six approved correspondences: query hrc_category_mappings.
- Unmapped categories: reference categories not in mappings.
- Airline-specific mappings: tenant_hrc_versions <-> reference/global via hrc_category_mappings with tenant isolation trigger.
- Mutations: mapping insert/delete should be TENANT_ADMIN or SUPER_ADMIN; no unrestricted endpoints.

## Task 5 — Implementation plan

Files to modify:
- `backend/app/db/db_models.py`: add `TenantHrcVersion`, `HrcCategoryMapping` ORM models.
- `backend/app/services/tenant_hrc_service.py`: rewrite to use `app.db.pg`.
- `backend/app/api/v1/tenant_hrc.py`: fix import, add Pydantic schemas, error handling.
- New: `backend/app/schemas/tenant_hrc.py` (or models), mapping service + routes.
- `backend/app/api/v1/router.py`: register mapping router if added.

SQL defects: missing unique constraint for seed idempotency; tenant_id type mismatch (text vs uuid) to verify; RLS policies not defined in migration.

Live-test prerequisites: apply migration + seed in staging, verify counts, run auth tests.

GO/NO-GO: NO-GO for implementation until SQL defects corrected and owner approval granted.

## STOP — AWAIT OWNER REVIEW
