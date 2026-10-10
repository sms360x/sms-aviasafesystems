# Step 1 Evidence Pack — Index

Every item below is closed. Evidence documents are in
docs/step1/. Each item has been committed to the branch
step1-audit-readiness.

## Phase 1A — Security verification

| Item | What it closed | Evidence doc | Commit |
|---|---|---|---|
| 1A.1 | RBAC middleware verification | 1A.1_rbac_middleware.md | 88e9447 |
| 1A.2 | SPI authentication | 1A.2_spi_auth.md | 420c99e |
| 1A.3 | N-HRC authentication | 1A.3_nhrc_auth.md | a31876f |
| 1A.4 | Middleware map gaps | 1A.4_middleware_map.md | cb00744 |
| 1A.5 | Token revocation | 1A.5_token_revocation.md | 4d696ce |
| 1A.6 | Create User dropdown | 1A.6_create_user_dropdown.md | 7336e19 |
| 1A.7 | VSR cross-tenant exposure | 1A.7_vsr_exposure_mitigation.md | 56c0326 |
| 1A.8 | hazard_analysis.py authentication | 1A.8_hazard_analysis_auth.md | 52d3a5c |

## Phase 1B — RLS and schema

| Item | What it closed | Evidence doc | Commit |
|---|---|---|---|
| 1B.1 | RLS inventory | 1B.1_rls_inventory.md | 57791a7 |
| 1B.2 | RLS exemptions and deferral | 1B.2_rls_exemptions.md | 465a8aa |
| 1B.3 | RLS coverage test | 1B.3_rls_coverage_test.md | dcf5189 |
| 1B.4 | barrier_register.srm_date | 1B.4_barrier_register_srm_date.md | 6d30abd |
| 1B.5 | RLS bypass consolidation | rls_bypass_finding.md | bbce5fc |

## Phase 1C — Compliance rows

| Item | What it closed | Evidence doc | Commit |
|---|---|---|---|
| 1C.1 | VSR visibility rule | 1C.1_vsr_visibility.md | 9a2b788 |
| 1C.1 corr | SAFETY_OFFICER raw access | 1C.1_vsr_visibility.md | b648699 |
| 1C.1b-i | Confidential wiring (deferred) | 1C.1b-i_confidential_wiring.md | 2c0ba46 |
| 1C.2 | AE non-delegability | 1C.2_ae_non_delegability.md | 939f669 |
| 1C.3 | Predictive analysis | 1C.3_predictive_analysis.md | 9006e99 |
| 1C.4 | Prescriptive analysis | 1C.4_prescriptive_analysis.md | 170e0f9 |
| 1C.5 | Data governance record | 1C.5_data_governance.md | 54d3923 |

## Phase 1D — Data completeness

| Item | What it covered | Evidence doc | Commit |
|---|---|---|---|
| 1D | Data-completeness findings | 1D_computed_data_trace.md, 1D_targets.md, 1D_page_data_gap.md, 1D_gap_and_scoping.md, 1D_nhrc_and_confidentiality.md | e3f647d, feb9cf5, af7ab71 |

## Cross-cutting documents

| Document | Purpose |
|---|---|
| Decision_Record.md (in docs/step0/) | Signed G1–G11 decisions |
| Step1_Work_Plan.md | Step 1 plan with known-failures list |
| live_data_findings.md | SME facts L1–L11 |
| rls_bypass_finding.md | Canonical RLS bypass statement |
| G3_Final_Register_Map.md (in docs/step0/) | Canonical register model |
| 1D_confidentiality_exposure_table.md | State-facing endpoint classification |
| 1D_fabricated_fallbacks_table.md | Placeholder values |
| 1D_drilldown_audit_coverage.md | Drill-down audit state |
| 1D_reporter_redaction_check.md | Reporter redaction state |
| 1D_page_data_gap.md | Per-page data block classification |
| 1D_gap_and_scoping.md | Step 4 scoping |
