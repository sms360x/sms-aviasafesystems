# MODULE-C-02C — Gate 2D Phase B1 Validation (Complete)

Date: 05 November 2026
Mode: Read-only

## 1. Tenant isolation

- Create: source HRC must belong to tenant (verify TenantHrcVersion.tenant_id == canonical tenant UUID). Target reference may be global/national (no tenant).
- Retire/revise/history: mapping ownership derived via source tenant HRC version; verify source belongs to tenant.
- Cross-tenant denied by trigger and service checks.

## 2. Authorization

- Mutations restricted to TENANT_ADMIN (existing pattern in tenant_hrc.py publish/retire).
- Reads allowed to authorized tenant users.

## 3. Transaction handling

- Use session_scope() for retire+create replacement in one transaction.
- Concurrency: partial unique index prevents duplicate active mappings; IntegrityError -> 409.

## 4. GET compatibility

- Existing GET endpoints return all mappings; update to filter active by default? Contract: add query param include_retired=false default; keep backward compatible.

## 5. Proposed endpoint contracts

- POST /hrc-mappings/ {source_id, target_id, mapping_type} -> 201, 400/403/404/409
- POST /hrc-mappings/{id}/retire -> 200
- POST /hrc-mappings/{id}/revise {new_target_id} -> 201 (retire old + create new)
- GET /hrc-mappings/history?tenant_id=... -> list including retired

## 6. Seed idempotency

- Partial unique index allows seed ON CONFLICT DO NOTHING; repeated runs no duplicates.

## 7. Files to modify

- backend/app/db/db_models.py (add created_by, retired_at, retired_by to HrcCategoryMapping)
- backend/app/services/hrc_mapping_service.py (create/retire/revise/history)
- backend/app/api/v1/hrc_mappings.py (new endpoints + schemas)
- supabase/migrations/... (schema extension + partial unique index)

## Unresolved blockers

- None material; awaiting owner approval for Phase B implementation.