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
| GET `/api/v1/reports/` (and legacy `/api/reports/`) | ae-dashboard.html (dead fetch), reports pages | VSR (`report_type=voluntary`) + MOR (`mandatory`) | Raw rows; fields include `reporter_name/email/phone/organisation` (`db_models.py:259-263`) | **partial / flag** | no | no | Tenant-scoped, but cross-tenant roles (`CAAN_SMD`/`STATE_SMD`/`SUPER_ADMIN`) bypass scoping. If a cross-tenant caller receives raw VSR rows (with reporter fields), that violates "VSR = aggregate only". Verify whether `report_service.get_reports` filters/redacts voluntary rows for cross-tenant callers — file to read: `backend/app/services/report_service.py` and `backend/app/routes/occurrence_reports.py`. |
| Internal register writes (CAN/CAP/hazard workflow) | operator pages | Internal register — process | Process data stays tenant-side | yes | — | n/a | Confirmed: no state endpoint exposes assignment history/comments/workflow. |

Undetermined: whether a cross-tenant caller can retrieve **raw** voluntary report rows (and reporter metadata) through `/api/v1/reports/`. This is the one row that may be a live violation; it must be confirmed by reading `report_service.py`/`occurrence_reports.py` at implementation time. All other rows are either correct-by-model or an audit-coverage gap.

## Counts
- Rows classified correct: 10
- Rows classified partial: 2 (drill-down endpoint; `/api/v1/reports/` VSR path)
- Rows flagged (potential violation): 1 (VSR raw via `/api/v1/reports/`, undetermined until code read)
- Audit gaps: 6 state read endpoints un-audited (`/api/v1/dashboard/caan/*`, `/api/v1/state-risk/*`, `/api/v1/nhrc/*`, `/api/v1/spi/state/*`)
