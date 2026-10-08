# 1D — Confidentiality Exposure Table (corrected ICAO model)

Read-only. Date: 2026-10-08. Corrected per SME 2026-10-08 (ICAO Annex 19 / Doc 9859).

Classification rules applied:
- VSR content — must be aggregate; if raw, flag.
- MOR / Audit / Accident — may be named; correct.
- Internal register outcome — may be named; correct.
- Internal register process — must not be exposed; if exposed, flag.
- Drill-down endpoints — must be purpose-bound and audited; if open or unaudited, flag.

| Endpoint | Page(s) | Source category | View served | Correct per model? | Drill-down required? | Audited? | Notes |
|---|---|---|---|---|---|---|---|
| GET `/api/v1/dashboard/caan/state` | state-oversight.html, state-sms-maturity.html | Internal register (hazards, reports, surveys) | Outcome + **named operator grid** | yes (outcome-level) | no | no | Returns named operators with outcome counts, not process. Reads not audited — gap (1D.10). |
| GET `/api/v1/dashboard/caan/survey-maturity` | state-sms-maturity.html | Internal register (surveys) | Aggregate outcome | yes | no | no | Not audited. |
| GET `/api/v1/dashboard/caan/sms-maturity-assessment` | state-sms-maturity.html | Internal register (surveys) + `sms_maturity` cache | Aggregate outcome + cached recommendations | yes | no | no | Not audited. |
| GET `/api/v1/state-risk/aggregate` | state-risk-register.html | Internal register (hazards, reports) | Outcome + `contributing_tenants` (named) | yes (outcome) | no | no | Named contributing operators = outcome, permitted. Not audited — gap (1D.10). |
| GET `/api/v1/state-risk/register` | state-risk-register.html | Persisted `state_risk_register` | Outcome | yes | no | no | Not audited. |
| GET `/api/v1/nhrc/state/kpis` | nhrc-kpis.html | Internal register (hazards) | Aggregate outcome (anonymous) | yes | no | no | Not audited. |
| GET `/api/v1/nhrc/tenant/{id}/kpis` | nhrc-kpis.html | Internal register (hazards) | Tenant's own outcome | yes | no | no | Operator self-view. |
| GET `/api/v1/spi/state/values` | spi-dashboard.html | Internal register | Aggregate (anonymous) | yes | no | no | Not audited. |
| GET `/api/v1/regulator/industry-averages`, `/top-hazards`, `/risk-trends`, `/risk-register`, `/benchmark`, `/export/{pdf,excel}` | regulator shares | Internal register aggregates | Anonymized `Operator-N` | yes | no | yes | `caan_audit.log_caan_read` (`regulator_dashboard.py:118,132,142,152,163,173,188`). |
| POST `/api/v1/regulator/share/escalate`; GET `/api/v1/regulator/share/escalate/{id}` | regulator drill-down | Internal register | Purpose-bound grant, `scope="full_detail_minus_reporter_identity"` | partial | yes | yes | `caan_audit.log_caan_share` / `log_caan_escalated_read`. In-memory, non-durable (1D.8). |
| GET `/api/v1/reports/` (and legacy `/api/reports/`) | ae-dashboard.html (dead fetch), reports pages | VSR (`report_type=voluntary`) + MOR (`mandatory`) | Cross-tenant list | resolved (1A.7) | no | no | **Fixed in 1A.7:** `_get_reports_async` now excludes `report_type='voluntary'` for cross-tenant callers (`report_service.py:112-126`). MOR/other types remain visible. Same-tenant callers unaffected. |
| GET `/api/v1/reports/{report_id}` | report detail pages | VSR + MOR | Full report (non-VSR) | resolved (1A.7) | no | no | **Fixed in 1A.7:** cross-tenant VSR detail returns `None` → route yields **404** (existence not confirmed) (`report_service.py:127-140,363-376`). Same-tenant VSR access unchanged. |
| PUT `/api/v1/reports/{report_id}/risk-assessment` | report pages | VSR + MOR | Full raw report (returns `_to_report_response`) | **flagged (residual)** | no | no | Not in 1A.7 scope. For a cross-tenant caller this write path still returns the report incl. narrative + `reporter_*` (`report_service.py:231-269`; `occurrence_reports.py:344-367`). Recommend folding into 1D.11. |
| Internal register writes (CAN/CAP/hazard workflow) | operator pages | Internal register — process | Process data stays tenant-side | yes | — | n/a | Confirmed: no state endpoint exposes assignment history/comments/workflow. |

**Resolved (2026-10-08):** the two VSR exposure rows are closed by item **1A.7**. `/api/v1/reports/` excludes VSR rows for cross-tenant callers, and `/api/v1/reports/{report_id}` returns 404 for a VSR to such callers. Reporter metadata remains on the `reports` row (item **1C.1b**, Step 2). One residual path is flagged above (`PUT .../risk-assessment`).

## Counts
- Rows classified correct: 10
- Rows classified partial: 1 (drill-down endpoint)
- Rows flagged (violation): 0 — the two prior VSR rows are resolved by 1A.7; 1 residual flagged (`PUT .../risk-assessment`)
- Audit gaps: 6 state read endpoints un-audited (`/api/v1/dashboard/caan/*`, `/api/v1/state-risk/*`, `/api/v1/nhrc/*`, `/api/v1/spi/state/*`)
