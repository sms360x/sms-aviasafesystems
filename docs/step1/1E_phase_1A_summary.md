# Phase 1A — Security Verification

## What it was

Verify that the security findings from the 2026-09-18 Security
Review (and the HANDOFF_GUIDE ground truth) were closed in the
current code, and add regression tests. The review proved stale:
most findings were already remediated, so Phase 1A was primarily
verification-with-tests, not new code.

## What closed

- **1A.1 — RBAC middleware.** Confirmed registered (`main.py`);
  module gate + tenant isolation. 8 unit tests rewritten/kept and
  2 real-route integration tests added (file: 10 passed).
  `1A.1_rbac_middleware.md`.
- **1A.2 — SPI authentication (H1).** Every SPI route requires
  auth; tenant routes enforce tenant match; state routes require
  the regulator role. Existing 13-test suite verified; 2
  module-gate tests added (file: 15 passed). `1A.2_spi_auth.md`.
- **1A.3 — N-HRC authentication (H1).** Same pattern as 1A.2;
  11 existing tests verified; 3 added (file: 14 passed).
  `1A.3_nhrc_auth.md`.
- **1A.4 — Middleware map gaps.** Added `/api/v1/dashboard/caan`
  → module5, `/api/v1/spi/tenant` → module2, `/api/v1/nhrc/tenant`
  → module2; documented why `/api/v1/dashboard` (hub), admin, and
  N-HRC reference routes stay unmapped. New file: 5 passed.
  `1A.4_middleware_map.md`.
- **1A.5 — Token revocation (M1).** Confirmed `check_revoked=True`
  at the single verification site; every caller routes through it.
  New file: 12 passed. `1A.5_token_revocation.md`.
- **1A.6 — Create User dropdown.** Removed the stale
  "CAAN SMD (Regulator)" option from both admin role selects
  (2 lines). `1A.6_create_user_dropdown.md`.
- **1A.7 — VSR cross-tenant exposure.** Cross-tenant list excludes
  `voluntary`; cross-tenant VSR detail/risk-assessment → 404.
  New file: 8 tests. `1A.7_vsr_exposure_mitigation.md`.
- **1A.8 — hazard_analysis.py authentication.** Removed the
  unauthenticated `X-Tenant-Id` write path; every route now uses
  the session tenant via `get_tenant_user`. New file: 15 tests.
  `1A.8_hazard_analysis_auth.md`.

## What it produced

- 8 items closed; 4 new test files and extensions to 3 existing
  files (~65 tests touched/added).
- 1 small UI deletion (1A.6, 2 lines); 1 middleware-map change
  (1A.4, 3 entries); 1 auth fix (1A.8).
- All evidence committed on `step1-audit-readiness`.

## What it deferred

- **1A.9** — rename `/api/v1/dashboard/caan` → `/api/v1/dashboard/state`
  (state-agnostic path; follows a future regulator-slug model).
- **1A.10** — public tenant-lookup: trim response (drop `tenant_id`
  slug per rule L6), remove/environment-gate the `?tenant=` fallback,
  server-side survey-window + active-status enforcement.

## Residuals

- `/api/v1/dashboard` (operator hub) remains unmapped by design —
  module-tagged cards must be enforced per-card (Step 2).
- Legacy `CAAN_SMD` stored claims show blank in the Edit dropdown
  until the Step 2 L4 role-migration; backend still accepts the value.
- `hazard_analysis.py` router remains unmounted; its frontend view
  posts to a different path (pre-existing wiring gap).
- RLS bypass on the app path (Phase 1B) is orthogonal and untouched here.
