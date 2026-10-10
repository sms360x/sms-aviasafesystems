# Phase 1D — Data Completeness

## What it was

Read-only trace of what each dashboard page actually renders, where
each computed measure comes from, and what is missing or fabricated —
to bound the operator→state data chain and scope Step 4.

## What it produced

- **1D_computed_data_trace.md** — endpoint → service → source →
  classification for the Priority-1 pages.
- **1D_targets.md** — 14 computed targets (T1–T14) and where each is
  computed/stored/rendered.
- **1D_page_data_gap.md** — all 16 pages classified
  (computed / demo / cached / placeholder / broken).
- **1D_gap_and_scoping.md** — the 5-stage chain gap and the ordered
  Step 4 scoping (persist SPI → govern SPT → compare → aggregate →
  render → confidentiality → OIP).
- **1D_nhrc_and_confidentiality.md** — N-HRC linkage and the
  **corrected ICAO/Annex-19 confidentiality model** (state sees
  OUTCOME, not PROCESS; VSR aggregate-only).
- Supporting: `1D_confidentiality_exposure_table.md`,
  `1D_fabricated_fallbacks_table.md`, `1D_drilldown_audit_coverage.md`,
  `1D_reporter_redaction_check.md`.

## What closed

- The corrected confidentiality model (a prior flagged "violation"
  was reclassified as correct outcome-level exposure).
- The VSR cross-tenant row was resolved by 1A.7/1A.7-ext.
- A complete inventory of fabricated/placeholder rendered values.
- The drill-down audit-coverage and reporter-redaction state.

## What it deferred

- **1D.1 / 1D.2** — persist operator SPI/SPT; state tables RLS tests.
- **1D.8** — durable drill-down/escalation persistence (grants are
  in-memory today).
- **1D.9** — remove or explicitly label every fabricated/placeholder
  value (synthetic culture score, synthetic trend charts, literal
  scenario banner).
- **1D.10** — extend CAAN read auditing to `/api/v1/state-risk/*`
  and `/api/v1/nhrc/*`.
- Items 4–7 (state aggregation from persisted measures, confidentiality
  boundary, OIP) — **Step 2/Step 4**.

## Residuals

- Operator measures (SPI/SPT) are computed per request, not persisted.
- State aggregation is a mix of live-computed and persisted; operators
  appear **named** in outcome views.
- Confidential reporting is not wired on the state path.
