# 1D — Page Data Gap (all 16 pages)

Read-only. Date: 2026-10-08.
For each page: page state, data blocks (endpoint → service → source → classification). Classification key: computed-from-registers / demo-seeded / cached / placeholder / broken.

---

## Priority 1 — SME-confirmed computed renderers

### public/safety.html — state: complete
- KPI strip, trends, recent cards → `/api/dashboard/overview`, `/recent`, `/trends`, `/risk-trends`, `/hazards`; `/api/v1/cans/`, `/api/v1/cans/caps`, `/api/v1/hazards/` → `dashboard_service.py` / `metrics_service.py` / `can_cap_service.py` / `hazard_service.py` → `reports`, `flight_diversions`, `cans`, `caps`, `hazards` → **computed-from-registers (+cached 60s)**.
- SSM Risk Trend + Hazard Frequency charts: **placeholder** fallback for demo tenants when API empty (`dashboard.js:496-509,541-555`).

### public/dashboard/ae-dashboard.html — state: complete
- SMS Maturity card/chart → `/api/v1/dashboard/airline/sms-maturity` → `dashboard_service.py` → `surveys` (computed) + `sms_maturity` (cached).
- Decisions queue/ledger, CAP review, decision PDF/CSV → `/api/v1/cans/`, `/api/v1/cans/caps`, `/caps/{id}`, `/decision.pdf`, `/ae-decision` → `can_cap_service.py` → `cans`/`caps`/`hazards` → **computed-from-registers**.
- `/api/v1/hazards/` and `/api/v1/reports/` fetched but **not rendered** (dead fetch).
- "Decision Required" banner = literal `'Assessed'` → **placeholder**.

### public/state-oversight.html — state: complete
- KPIs, hazard matrix, operator profiles, macro trend → `/api/v1/dashboard/caan/state` → `dashboard_service.py` → `tenants`, `hazards`, `reports`, `surveys`, `survey_responses` → **computed-from-registers; named operators**.

### public/dashboard/my-tasks.html — state: complete
- Task KPIs + table + status filter → `/api/v1/dashboard/master-register` → `master_register.py` → `hazards`, `cans`, `caps` (+`reports`) → **computed-from-registers**.

---

## Priority 2 — other state and safety pages

### public/state-risk-register.html — state: complete
- Register stats/table → `/api/v1/state-risk/register` → `state_risk_service.py` → `state_risk_register` (persisted; empty until synced) → **computed-from-registers (persisted)**.
- Aggregation tables → `/api/v1/state-risk/aggregate` → `state_risk_service.py` → `hazards`, `reports`, `state_risk_categories` → **computed-from-registers; named contributing_tenants**.
- Sync button → `POST /state-risk/sync` (writes `state_risk_register`); SSP target → `PUT .../ssp-target` (writes).
- Reference: `/api/v1/regulators/{id}` → `regulator_service.py` → `regulators`, `tenants`.

### public/state-safety-trends.html — state: complete (navigation only)
- Pure nav hub (3 static links). **No data blocks.** Only the inherited shell `GET /api/v1/tenants/{id}`.

### public/dashboard/spi-dashboard.html — state: complete
- SPI summary, leading/lagging cards, comparison → `/api/v1/spi/tenant/{id}/values|status`, `/spi/state/values` → `spi_service.py` → `hazards`, `reports`, `cans`, `caps`, `surveys`, `flight_diversions` → **computed-from-registers**.
- SPI trend chart: **placeholder** when API empty (client synthetic 6-month series, `spi-dashboard.js:212-234`).

### public/dashboard/nhrc-kpis.html — state: complete
- N-HRC stat/grid cards, distribution, comparison → `/api/v1/nhrc/tenant/{id}/kpis`, `/nhrc/state/kpis` → `nhrc_service.py` → `hazards` → **computed-from-registers**.
- SEI/contributing-factor modal → `/nhrc/seis/{code}`, `/nhrc/contributing-factors/{code}` → static `NHRC_REFERENCE_DATA` → **demo-seeded/static**.
- N-HRC trend chart: **placeholder** (client pseudo-random derived from hazard counts, `nhrc-dashboard.js:35-42,148-178`).

### public/dashboard/state-sms-maturity.html — state: complete
- Aggregate stats, radar, operator bars/grid → `/api/v1/dashboard/caan/survey-maturity`, `/caan/state` → `dashboard_service.py` → `surveys`, `survey_responses`, `tenants` → **computed-from-registers**.
- Assessment narrative + Top Recommended Actions → `/api/v1/dashboard/caan/sms-maturity-assessment` → `surveys` (computed) + `sms_maturity` cache (cached).
- 70% / 3.8 benchmark rings are static chart constants.

### public/dashboard/sms-maturity.html — state: complete
- Tenant selector → `/api/v1/admin/tenants` (SUPER_ADMIN only) → `production_seed.py` → `tenants`, `regulators` (+ counts) → **computed-from-registers**.
- Overview/components/strengths/actions/history → `/api/v1/dashboard/airline/sms-maturity` → `dashboard_service.py` → `surveys` (computed) + `sms_maturity` cache (cached).

### public/dashboard/master-register.html — state: complete
- KPI cards + register table → `/api/v1/dashboard/master-register` → `master_register.py` → `hazards`, `cans`, `caps`, `reports` → **computed-from-registers**.

### public/dashboard/dept-master-register.html — state: complete
- KPI cards + table (CAN/CAP only; hazards dropped client-side) → same endpoint/service/source → **computed-from-registers**.
- Department badge → client-derived from claims/email → **placeholder**.

### public/hazard-analysis.html — state: partial (form only)
- No inline API calls. Hazard form with hard-coded tolerability index (`:79`) and hard-coded HFACS/nanocode `<option>` lists (`:88-102`); "Save" button has no handler (`:108`) → **placeholder / non-functional**.
- Only inherited shell `GET /api/v1/tenants/{id}`.

### public/risk-trends.html — state: complete
- Risk Distribution + Monthly Trends charts → `/api/dashboard/risk`, `/api/dashboard/trends` → `dashboard_service.py`/`metrics_service.py` → `reports` (+`flight_diversions`) → **computed-from-registers**.

### public/top-hazards.html — state: complete
- Hazard stat cards → `/api/v1/hazards/stats` → `hazard_service.py` → `hazards` → **computed-from-registers**.
- Occurrence Frequency chart → `/api/dashboard/hazards` → `metrics_service.py` → `reports.occurrence_type` → **computed-from-registers** (note: report-derived, not the `hazards` table, despite the page title).

### public/psoe-audit.html — state: complete
- Checklist + maturity dashboard → `/api/v1/psoe/template` (static `data/psoe_appendix10.json`, cached) → **demo-seeded**.
- Assessment load/save/complete/export → `/api/v1/psoe/assessments[...]` → `psoe_service.py` → `psoe_assessments` → **computed-from-registers** (scores computed client-side over template + stored responses).

---

## Grouping

Pages that render real computed data (SME-confirmed 4):
- `public/safety.html`, `public/dashboard/ae-dashboard.html`, `public/state-oversight.html`, `public/dashboard/my-tasks.html`.

Pages that render real computed data (additional — found in this pass):
- `state-risk-register.html`, `spi-dashboard.html`, `nhrc-kpis.html`, `state-sms-maturity.html`, `sms-maturity.html`, `master-register.html`, `dept-master-register.html`, `risk-trends.html`, `top-hazards.html`, `psoe-audit.html`, and `state-oversight.html`/`ae-dashboard.html` (SMS maturity blocks).

Pages that render demo data (as the primary source):
- `psoe-audit.html` (static PSOE Appendix-10 template is demo-seeded; the assessment data itself is live).
- Any surface in a non-production environment reads `is_demo=True` seeded rows (same code path as production).

Pages that render placeholders:
- `hazard-analysis.html` (form-only; static tolerability + hard-coded dropdowns; non-functional Save).
- Placeholder *blocks* elsewhere: safety.html demo fallback charts; spi-dashboard trend fallback; nhrc-kpis trend chart; ae-dashboard "Decision Required" banner; dept-master-register department badge.

Pages that render a mix:
- `ae-dashboard.html` (computed + cached + one placeholder banner + dead fetches).
- `sms-maturity.html` / `state-sms-maturity.html` (computed scores + cached recommendations).
- `spi-dashboard.html` / `nhrc-kpis.html` (computed KPIs + placeholder trend charts).

Pages with no data blocks:
- `state-safety-trends.html` (navigation hub).

---

## Empty department registers — expected in demo

Department-scoped pages (`public/dashboard/my-tasks.html`, `public/can_cap/caps.html`, `public/can_cap/cans.html`) show empty registers when the current user's department has no assigned items. This is correct behaviour, not a scoping bug.

The demo environment does not currently seed CAMO-assigned or QA-assigned items. An auditor viewing these pages in the demo environment should be told this before the session.

The MOR form (`public/report/mor.html`) is correctly placed on the CAMO workspace: MORs are derived from the aircraft technical log, and the CAMO officer transcribes the log into the MOR form. The "Reporter Details" fields are the filing officer's details, not the witness's. This is standard practice under ICAO Doc 9859 and Annex 13.
