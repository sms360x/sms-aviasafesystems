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
| GET `/api/v1/reports/` (and legacy `/api/reports/`) | ae-dashboard.html (dead fetch), reports pages | VSR (`report_type=voluntary`) + MOR (`mandatory`) | Cross-tenant list of **all** reports (no type filter) | **flagged** | no | no | `get_reports` (`occurrence_reports.py:241-255`) uses `get_current_user`; cross-tenant roles get `cross_tenant=True`, and `_get_reports_async` selects **all** tenant rows with no `report_type` filter (`report_service.py:112-124,352-358`). The list projection `_to_list_item` omits narrative and `reporter_*` (`:410-434`), but VSR rows are still returned to cross-tenant callers — violates "VSR = aggregate only". |
| GET `/api/v1/reports/{report_id}` | report detail pages | VSR + MOR | Full raw report incl. **narrative** + **reporter metadata** | **flagged** | no | no | `_to_report_response` includes `narrative` and `reporter_name`, `reporter_role`, `reporter_email`, `reporter_phone`, `reporter_organisation` (`occurrence_reports.py:376-404`). Cross-tenant `get_report_by_id` uses no tenant filter (`report_service.py:363-375`). A cross-tenant caller can read a VSR's raw narrative and reporter metadata. |
| Internal register writes (CAN/CAP/hazard workflow) | operator pages | Internal register — process | Process data stays tenant-side | yes | — | n/a | Confirmed: no state endpoint exposes assignment history/comments/workflow. |

**Resolved (2026-10-08):** the previously undetermined VSR row is **flagged**. `/api/v1/reports/` does **not** exclude VSR rows for cross-tenant callers, and `GET /api/v1/reports/{report_id}` returns the raw VSR narrative plus reporter metadata. No filter, no redaction step exists on either response path. Recorded as item **1D.11** (fix deferred to Step 2, pending the reporter-contact store from 1C.1b).

## Counts
- Rows classified correct: 10
- Rows classified partial: 1 (drill-down endpoint)
- Rows flagged (violation): 2 (`/api/v1/reports/` list exposes VSR rows; `/api/v1/reports/{id}` exposes raw VSR narrative + reporter metadata)
- Audit gaps: 6 state read endpoints un-audited (`/api/v1/dashboard/caan/*`, `/api/v1/state-risk/*`, `/api/v1/nhrc/*`, `/api/v1/spi/state/*`)
