# Phase 1B — RLS and Schema Hygiene

## What it was

Inventory the live RLS state, record exemptions/deferrals, add a
coverage test that does not silently pass, apply one additive
column, and consolidate the pre-existing RLS-bypass finding.

## What closed

- **1B.1 — RLS inventory.** Live read-only catalog: **58 public
  tables**, RLS **enabled on all 58**, **forced on none**, 57
  policies across 48 tables, 10 zero-policy tables; owner =
  `postgres`; every policy reads Supabase GoTrue claims the
  Firebase app path never presents. `1B.1_rls_inventory.md`.
- **1B.2 — Exemptions and deferral.** **2 platform exemptions**
  (`dead_letter_queue`, `sms_dispatches`); **8 tenant-owned
  zero-policy tables deferred** (`audit_dispatches`, `feedback`,
  `hazard_assessments`, `hazard_capas`, `hazard_rca_entries`,
  `hazard_rca_factors`, `invites`, `psoe_findings`); corrected the
  `audit_dispatches` classification. `1B.2_rls_exemptions.md`.
- **1B.3 — RLS coverage test.** Asserts each tenant-owned table has
  RLS, skipping **with a reason** where the owner connection bypasses
  enforcement (never silently passing). `1B.3_rls_coverage_test.md`.
- **1B.4 — `barrier_register.srm_date`.** Additive column
  (CAAN SRM Manual §2.3.4). `1B.4_barrier_register_srm_date.md`.
- **1B.5 — RLS bypass consolidation.** `rls_bypass_finding.md` made
  the single canonical statement; 1B.1 classification aligned.
  `rls_bypass_finding.md`.

## What it produced

- A full RLS inventory and the canonical bypass finding.
- A coverage test and one additive schema column (migration).
- Confirmed the effective control today is **application-layer**
  tenant isolation, not the database.

## What it deferred

- The **database-layer RLS fix** (owner-connection + claim-mismatch)
  — **Step 2** (membership/identity model), per
  `rls_bypass_finding.md`.
- Writing the **8 deferred tenant-owned policies** — Step 2.
- Capturing the **~12 unversioned live policies** and 10 live-only
  RLS enablements into `supabase/migrations/` with a `pg_policies`
  drift check.

## Residuals

- RLS is enabled but **not enforced** on the app path; tenant
  isolation rests on application code (verified by 1A.2/1A.3/1A.7/1A.8).
- Exemption/deferral reasoning is recorded in `1B.2_rls_exemptions.md`.
