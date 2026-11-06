# MODULE-C-02C — Gate 2A SQL Contract & Implementation Preparation

Date: 05 November 2026
Authorization: Validation and proposed corrections only
Status: No implementation authorization

## Task A — Mapping uniqueness

Proposed minimal unique constraint:
`UNIQUE (source_table, source_id, target_table, target_id)` on `hrc_category_mappings`.
Seed uses `ON CONFLICT DO NOTHING` (seeds/hrc_mappings_seed.sql lines 10,18); without a unique constraint, idempotency is not guaranteed. Add constraint before running seed. Nullable tenant/version fields: none in mapping table (source/target ids are uuid NOT NULL), so simple unique constraint suffices.

## Task B — Canonical tenant identity

- `tenants.id` is UUID (uuid5('tenant:'+slug)) (db_models.py lines 2139-2143).
- `tenant_hrc_versions.tenant_id` is TEXT (migration line 4).
- Existing backend authorization compares path tenant_id to user claim tenant_id (tenant_hrc.py lines 10-11); user claim is slug typically.
- Canonical stored identifier should be the deterministic UUID to enable FK to tenants.id; but API uses slug. Proposed: either store slug (text, no FK) for compatibility, or add `tenant_id_uuid` with FK. Recommendation: keep text slug for API compatibility now, document mismatch; no record changes.

## Task C — Published lifecycle

Trigger `prevent_published_tenant_hrc_mutation` (migration lines 22-34) prevents UPDATE/DELETE of published rows. Supports:
1. Draft creation: insert draft.
2. Draft editing: update where status='draft'.
3. Publication: update draft->published (allowed, since OLD.status != published).
4. New-version: insert new draft from published source (read-only source).
5. Historical retrieval: select all versions by code.
6. Retirement: cannot update published row due to trigger -> need correction: allow status change published->deprecated. Proposed trigger exception for retirement (set retired_at + status='deprecated') only, or separate retired_at update without mutating published content. Smallest correction: modify trigger to permit UPDATE when only approval_status transitions published->deprecated and retired_at set.

## Task D — Atomic transactions

Use existing `session_scope()` (session.py lines 282-317) and `pg` functions wrapped in a single transaction. For publication/versioning, perform select+update/insert within one session_scope; rely on DB trigger and unique index for concurrency protection. No new client.

## Task E — Authorization and RLS

- Global/national reference reads: any authenticated user (subject to tenant).
- Tenant HRC drafts: TENANT_ADMIN or OFFICER (safety/corporate_safety) per tenant_hrc.py lines 12-14.
- Publishing: TENANT_ADMIN only (lines 35-37).
- Retiring: recommend TENANT_ADMIN only.
- Mappings: tenant-scoped mappings require same tenant; cross-tenant blocked by trigger. Read mappings across jurisdiction: global/national references readable; tenant mappings isolated.

SUPER_ADMIN bypass: existing code allows SUPER_ADMIN to bypass tenant identity check (line 10) but still must pass role check (lines 12-14) where SUPER_ADMIN is not in allowed roles -> SUPER_ADMIN currently cannot manage tenant HRC. This is a contract gap to address in Gate 2B (decide whether SUPER_ADMIN may act).

## Deliverable summary

- SQL corrections: unique constraint on mappings; trigger adjustment for retirement; optional tenant_id type reconciliation.
- Canonical tenant id: deterministic UUID (slug-based) per backend, but migration stores text; document and defer conversion.
- Lifecycle: draft->published->deprecated with immutability except retirement transition.
- Transaction: session_scope + DB constraints.
- Authorization matrix: as above.
- File plan: db_models additions, service rewrite, API schemas/errors, mapping service/routes, router registration.
- Blockers: SQL corrections not applied; SUPER_ADMIN role contract; tenant_id type mismatch.
- GO/NO-GO: NO-GO until SQL corrections applied and owner approval.

STOP for owner review.
