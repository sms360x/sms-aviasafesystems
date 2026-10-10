# Step 1 Finding — RLS is bypassed on the application path

Status: Finding, documented for Step 2. Not fixed in Step 1.
Date: 2026-10-08
Source: HANDOFF_GUIDE.md (2026-10-01 / 2026-10-03)

## What the bypass is

The database layer does not enforce RLS on the app path.
Tenant isolation is enforced by application code only.

## Why (two reasons, both present)

1. Owner connection.
   The backend connects as the table owner (postgres /
   postgres.bftnwljnpnpniksmalnk via the Supabase pooler).
   PostgreSQL skips RLS for the table owner unless
   FORCE ROW LEVEL SECURITY is set. rls_forced is false on
   every table.

2. Identity mismatch.
   The live RLS policies read Supabase GoTrue claims
   (auth.jwt(), auth.uid(), app.current_tenant). The app
   path uses Firebase Auth and does not present GoTrue
   claims. Even if the connection were not the owner, the
   policies would not match.

## Effect

- RLS is enabled on all 58 public tables.
- It does not gate any query on the app path.
- Tenant isolation currently relies on application-layer
  query filters (WHERE tenant_id = <session tenant>).
- Evidence items 1A.2, 1A.3, 1A.7, 1A.8 verified that the
  application-layer isolation works correctly.

## What is exempted or deferred

- Platform exemptions (2): dead_letter_queue, sms_dispatches.
- Deferred tenant-owned zero-policy tables (8):
  audit_dispatches, feedback, hazard_assessments,
  hazard_capas, hazard_rca_entries, hazard_rca_factors,
  invites, psoe_findings.
See docs/step1/1B.2_rls_exemptions.md for the reasoning.

## What an auditor should be told

- RLS is enabled but not enforced on the app path.
- Application-layer isolation is enforced and tested.
- The database-layer fix requires resolving the identity
  mismatch, which is Step 2 work (membership model).
- No cross-tenant exposure has been identified on the app
  path.

## Step 2 scope

- Decide the RLS identity model (Firebase claim path).
- Rewrite the ~12 live policies against that model.
- Write the 8 deferred tenant-owned policies.
- Decide whether FORCE ROW LEVEL SECURITY should be set.

## Related items

- 1B.1 RLS inventory: docs/step1/1B.1_rls_inventory.md
- 1B.2 exemptions and deferral:
  docs/step1/1B.2_rls_exemptions.md
- 1B.3 coverage test:
  docs/step1/1B.3_rls_coverage_test.md

## Evidence

- `HANDOFF_GUIDE.md:1314-1321` (Deferred item A — RLS coverage gap): "the backend connects as the Supabase owner (`rls_forced = false` everywhere) -> RLS is bypassed on the app path regardless"; live policies read `auth.jwt()` (Supabase JWT), not Firebase claims.
- `HANDOFF_GUIDE.md:766-792` (Pre-existing issues carried forward): the module-gate leak and related boundary gaps pre-date Step 1.
- `HANDOFF_GUIDE.md:1323-1329` (Deferred item B): ~12 live RLS policies have no repo source.
- 10 `public` tables have RLS enabled with **zero policies** (default-deny for any non-owner role): `audit_dispatches`, `dead_letter_queue`, `feedback`, `hazard_assessments`, `hazard_capas`, `hazard_rca_entries`, `hazard_rca_factors`, `invites`, `psoe_findings`, `sms_dispatches` (`HANDOFF_GUIDE.md:1314-1317`).

## Why it is not fixed in Step 1

RLS enforcement is coupled to the Step 2 decisions: the membership/oversight model and the single tenant-key scheme. Reworking RLS to read Firebase-derived authorization (or to force RLS for the owner) is a Step 2 change. Step 1's job is to make the finding **visible and documented**, not to fix it.
