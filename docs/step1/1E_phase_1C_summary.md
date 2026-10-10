# Phase 1C — Compliance Rows

## What it was

Close (or correctly defer) the five unique "Missing" compliance
requirements: confidential/voluntary reporting, AE non-delegability,
predictive analysis, prescriptive analysis, and data governance.

## What closed

- **1C.1 — VSR visibility rule.** Raw VSR restricted to the owning
  tenant's Safety Manager; others denied (403); cross-tenant VSR
  excluded (1A.7). `1C.1_vsr_visibility.md`.
- **1C.1 correction** — `SAFETY_OFFICER` added to the raw-VSR allowed
  set (Safety Department officer). `1C.1_vsr_visibility.md`.
- **1C.2 — AE non-delegability.** Risk acceptance graded on initial
  tolerability: an Intolerable risk only the `ACCOUNTABLE_EXECUTIVE`
  may accept; identity from the session; CAP AE decision AE-only and
  audited. `1C.2_ae_non_delegability.md`.
- **1C.3 — Predictive analysis.** `PredictiveService.project_open_hazards`
  over the `hazards` register (linear-trend projection). New service +
  10 tests. `1C.3_predictive_analysis.md`.
- **1C.4 — Prescriptive analysis.** `PrescriptiveService.recommend_hazard_actions`
  over the `hazards` register (two documented deterministic rules).
  New service + 8 tests. `1C.4_prescriptive_analysis.md`.
- **1C.5 — Data governance record.** SME-approved ownership,
  retention (lifetime of the operator's SMS), and per-role access
  rules. `1C.5_data_governance.md`.

## What it produced

- 2 new pure services (predictive, prescriptive) with 18 unit tests.
- 17 VSR-visibility tests (1C.1 + correction) and 11 AE
  non-delegability tests.
- The data-governance record.

## What it deferred

- **1C.1b-i** — confidential-reporting-service wiring: **stopped**
  (integration point ambiguous; three conflicting role models),
  documented. `1C.1b-i_confidential_wiring.md`.
- **1C.1b-ii** — reporter-contact store (schema change) — **Step 2**.
- **1C.1b-iii** — AE aggregate VSR view — **Step 4**.

## Residuals

- The confidential-reporting service remains **unwired**; the role
  models (`_RAW_VSR_ROLES`, `CUSTODIAN_ROLES`, `REPORT_VIEWER_ROLES`)
  are inconsistent and need Step 2 unification.
- Predictor/prescriber are not wired to any endpoint or UI (by design).
- Risk acceptance writes no audit record; hazard-closure gating is
  mis-implemented (`get_accountable_executive`) — both Step 2.
