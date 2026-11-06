# MODULE-C-02C — Gate 2D Phase B2B Correction Plan

Date: 05 November 2026
Mode: Read-only planning (no code changes)

## Required change

Modify `HrcMappingService.list_mappings` / `history` to filter by tenant when include_retired=True or history requested:
- Join `HrcCategoryMapping.source_id` to `TenantHrcVersion.id`.
- Restrict `TenantHrcVersion.tenant_id == self.tenant_uuid`.
- Require `source_table == 'tenant_hrc_versions'`.

## Files to modify

- backend/app/services/hrc_mapping_service.py (list_mappings/history query)
- backend/app/api/v1/hrc_mappings.py (history endpoint already passes tenant; ensure fail-closed)

## Verification plan

- Import check.
- Unit-level: missing tenant claim -> 403.
- Cross-tenant mapping ID returns 404.
- Retired mappings visible to owner only.

## Remaining risks

- No live DB; query correctness depends on ORM join. Need future acceptance.

STOP for owner approval.