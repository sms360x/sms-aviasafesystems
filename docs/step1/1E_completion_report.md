# Step 1 Completion Report

## Summary

Step 1 — Audit Readiness — is complete.

Phases:
    - 1A: security verification (8 items closed)
    - 1B: RLS and schema hygiene (5 items closed)
    - 1C: compliance rows (9 items closed or deferred)
    - 1D: data-completeness findings (5 documents)
    - 1E: this evidence pack

The work was verification-heavy: the 2026-09-18 Security Review was
stale, so Phase 1A mostly confirmed already-present controls and
pinned them with regression tests. Every item is one commit on the
branch `step1-audit-readiness`, each revertible. No deploy, no push.

## Test suite

Final Phase 1E run (branch tip `54d3923` + this pack):

- **pytest:** `1154 passed, 2 failed, 1 skipped, 79 deselected`.
  The 2 failures are both on the known list (see below); no new failure.
- **Node:** `dashboard.test.js` 4 passed; `sram.test.js` 9 passed;
  `test_nav_config.js` 1 failed (`test_ae_narrow_menu`) — known.

Known environmental failures are live-DB / ordering dependent and
pass in isolation; they are not Step 1 regressions.

## What was closed

- **Security (1A):** RBAC middleware registration; SPI and N-HRC auth
  (H1); middleware map gaps; token revocation (M1); Create-User
  dropdown; VSR cross-tenant exposure; unauthenticated
  `hazard_analysis.py` writes.
- **RLS (1B):** full 58-table inventory; exemptions/deferrals recorded;
  coverage test; `barrier_register.srm_date`; canonical RLS-bypass
  finding.
- **Compliance (1C):** VSR raw-visibility rule (+ SAFETY_OFFICER
  correction); AE non-delegability; minimum-viable predictive and
  prescriptive functions; the data-governance record.

## What was deferred

| Deferred item | Target |
|---|---|
| Database-layer RLS enforcement fix (owner connection + claim mismatch) | Step 2 |
| 8 tenant-owned zero-policy RLS policies; capture ~12 unversioned live policies | Step 2 |
| 1A.9 rename `/api/v1/dashboard/caan` → `/dashboard/state` | Step 2 |
| 1A.10 public tenant-lookup trim + sandbox removal + server-side survey enforcement | Step 2 |
| 1C.1b-ii reporter-contact store (schema + custodian) | Step 2 |
| 1C.1b-iii AE aggregate VSR view | Step 4 |
| Role-model unification (`_RAW_VSR_ROLES` / `CUSTODIAN_ROLES` / `REPORT_VIEWER_ROLES`); retire `SAFETY_OFFICER` → `OFFICER` + department | Step 2 |
| 1D.1/1D.2 persist operator SPI/SPT; state table RLS tests | Step 2 / Step 4 |
| 1D.8 durable escalation/drill-down grants | Step 2 |
| 1D.9 remove/label fabricated fallback values | Step 2 |
| 1D.10 audit coverage on `/state-risk/*`, `/nhrc/*` | Step 2 |
| Step 4 scoping (persist measures → aggregate → OIP) | Step 4 |

## Known failures

| Test | Classification |
|---|---|
| `tests/test_tenant_sms.py::TestV1RouterRegistration::test_v1_router_includes_all_sub_routers` | known pre-existing (v1-router registration; `assert "/state-risk" in []`) |
| `tests/test_hazard_enrichment.py::test_enrichment_adds_and_records_before_after` | known environmental (live-DB; passes in isolation) |
| `tests/test_risk_matrix.py::test_hazard_create_honours_risk_index_without_classifying` | known environmental (intermittent live-DB socket timeout) |
| `tests/test_hazard_triage.py::test_rejected_closes_hazard` | known environmental / order-dependent (unscoped `TRI-001` query; Step 2 test cleanup) |
| Node `frontend-tests/test_nav_config.js::test_ae_narrow_menu` | known pre-existing (AE nav menu expectation) |

## Residual findings

- **RLS is bypassed on the app path** (`rls_bypass_finding.md`): owner
  connection + GoTrue-vs-Firebase claim mismatch. Tenant isolation
  today rests on application code, which 1A verifies.
- **Confidential-reporting service is unwired**; three role models
  disagree (`1C.1b-i_confidential_wiring.md`).
- **Hazard-closure AE gating is mis-implemented**
  (`get_accountable_executive`); risk acceptance writes no audit
  record (`1C.2` residual).
- **Fabricated/placeholder values** remain on several dashboards
  (`1D_fabricated_fallbacks_table.md`).
- **Audit coverage is partial**; drill-down grants are in-memory
  (`1D_drilldown_audit_coverage.md`).
- **Predictive/prescriptive** services are not wired to endpoints/UI.
- **Legacy `CAAN_SMD` stored claims** show blank in the admin Edit
  dropdown until the Step 2 migration.

## What an auditor can inspect

1. `1E_evidence_pack_index.md` — every closed item with its evidence
   document and commit hash.
2. This report.
3. `Step1_Summary.md` — the plain-language summary.
4. The per-phase summaries (`1E_phase_1A_summary.md` …
   `1E_phase_1D_summary.md`).
5. The individual evidence documents in `docs/step1/`, each with its
   finding, action, tests, and result.
