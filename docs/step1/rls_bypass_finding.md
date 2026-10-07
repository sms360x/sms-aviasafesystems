# Step 1 Finding — RLS is bypassed on the application path

Status: Finding, documented for Step 2. Not fixed in Step 1.
Date: 2026-10-08
Source: HANDOFF_GUIDE.md (2026-10-01 / 2026-10-03)

## What the finding is

Row-Level Security is effectively bypassed on the application path:

1. The backend connects to Supabase as the **owner** role, and `rls_forced = false` everywhere. Postgres RLS does not apply to the table owner unless the table is set `FORCE ROW LEVEL SECURITY`.
2. The live RLS policies read **Supabase JWT** claims (`auth.jwt()`), but the application authenticates with **Firebase** ID tokens. The policies therefore evaluate against claims that the app path never presents.

Consequence: enabling RLS on a table does **not**, by itself, enforce tenant isolation for requests served by the backend.

## Evidence

- `HANDOFF_GUIDE.md:1314-1321` (Deferred item A — RLS coverage gap): "the backend connects as the Supabase owner (`rls_forced = false` everywhere) -> RLS is bypassed on the app path regardless"; live policies read `auth.jwt()` (Supabase JWT), not Firebase claims.
- `HANDOFF_GUIDE.md:766-792` (Pre-existing issues carried forward): the module-gate leak and related boundary gaps pre-date Step 1.
- `HANDOFF_GUIDE.md:1323-1329` (Deferred item B): ~12 live RLS policies have no repo source.
- 10 `public` tables have RLS enabled with **zero policies** (default-deny for any non-owner role): `audit_dispatches`, `dead_letter_queue`, `feedback`, `hazard_assessments`, `hazard_capas`, `hazard_rca_entries`, `hazard_rca_factors`, `invites`, `psoe_findings`, `sms_dispatches` (`HANDOFF_GUIDE.md:1314-1317`).

## Effect

Tenant isolation on the app path is currently enforced by **application code** (per-route dependencies + the RBAC middleware and its tenant-param checks), not by the database. Any table whose app-path query omits a tenant filter is not protected by RLS. This is why Step 1's 1B work must not claim isolation merely because a table "has RLS".

## Why it is not fixed in Step 1

RLS enforcement is coupled to the Step 2 decisions: the membership/oversight model and the single tenant-key scheme. Reworking RLS to read Firebase-derived authorization (or to force RLS for the owner) is a Step 2 change. Step 1's job is to make the finding **visible and documented**, not to fix it.

## What an auditor should be told

This is a **known, documented, scheduled** finding:

- Tenant isolation is presently enforced in application code, with RLS present but non-enforcing on the app path.
- The gap is recorded here and in `HANDOFF_GUIDE.md`, and scheduled for Step 2 (membership model + tenant key) where RLS enforcement is restored.
- It is not being hidden, and 1B.3's coverage test will explicitly skip-with-reason (never silently pass) where the owner connection bypasses enforcement, pointing back to this document.
