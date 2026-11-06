# MODULE-C-02C — Gate 2F Simplification Validation

Date: 05 November 2026
Mode: Read-only

## Proposed changes

- Remove `created_by`, `retired_at`, `retired_by` from mapping table.
- Remove partial unique index; restore unconditional UNIQUE(source_table,source_id,target_table,target_id).
- Remove mapping mutation trigger preventing deletion; allow controlled delete.
- Remove history endpoint and historical retrieval.
- Simplify service to create/replace/delete current mappings.

## Affected files

- supabase/migrations/20261104130000_tenant_hrc_and_mappings.sql
- backend/app/db/db_models.py (HrcCategoryMapping)
- backend/app/services/hrc_mapping_service.py
- backend/app/api/v1/hrc_mappings.py

## Dependencies on retired mappings/history

- None in other modules identified (grep only in these files).

## Compatibility risks

- Any external consumers expecting history endpoint will break (none known).
- Seed idempotency remains via UNIQUE.

## Unresolved

- None; awaiting owner approval for Phase B.