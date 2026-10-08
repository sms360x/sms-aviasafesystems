# 1D — Computed Data Trace (Priority 1 pages)

Read-only trace. Date: 2026-10-08. Branch: step1-audit-readiness.
Classification key: computed-from-registers / demo-seeded / cached / placeholder / undetermined.

Cross-cutting: all pages load `public/js/api/client.js` (transport) and `public/js/shell.js`, which calls `GET /api/v1/tenants/{tenantId}` (`shell.js:268` → `backend/app/routes/tenants.py:145` → table `tenants`). Register reads apply `is_demo == demo_scope()` (`backend/app/db/isolation.py:13`), so in non-production the same computed path reads demo-seeded rows.

---

## Page: public/safety.html

Purpose: operator Safety Manager dashboard — reporting KPIs, trends, and recent registers.

Endpoints called (from `public/js/dashboard.js` + `public/js/api/dashboard.js`):

| URL | Route | Service | Data source | Classification |
|---|---|---|---|---|
| GET `/api/dashboard/overview` | `routes/dashboard.py:79` `get_dashboard_overview` | `DashboardService.get_airline_overview` (`dashboard_service.py:107`) + `MetricsService.calculate_kpis` | Postgres `reports`; 60s repo cache | computed-from-registers (+cached) |
| GET `/api/v1/dashboard/recent` (VSR + MOR + activity) | `routes/dashboard.py:115` `get_recent_reports` | `DashboardService.get_recent_reports` (`:326`) | Postgres `reports` | computed-from-registers |
| GET `/api/dashboard/trends` | `routes/dashboard.py:146` `get_monthly_trends` | `DashboardService.get_monthly_trends` (`:337`) + `_merge_diversion_trends` (`:360`) | Postgres `reports` + `flight_diversions` (45s `pg_cache`) | computed-from-registers (+cached) |
| GET `/api/dashboard/risk-trends` | `routes/dashboard.py:158` `get_ssp_risk_trends` | `DashboardService.get_ssp_risk_trends` (`:414`) + `MetricsService.calculate_ssp_risk_trends` (`metrics_service.py:313`) | Postgres `reports` | computed-from-registers |
| GET `/api/dashboard/hazards` | `routes/dashboard.py:175` `get_hazard_frequency` | `DashboardService.get_hazard_frequency` (`:409`) + `MetricsService.calculate_hazard_frequency` (`:134`) | Postgres `reports` (`occurrence_type`) | computed-from-registers |
| GET `/api/v1/cans/` | `routes/can_cap.py:52` `list_cans` | `CanCapService.list_cans` (`can_cap_service.py:520`) | Postgres `cans` JOIN `hazards` | computed-from-registers |
| GET `/api/v1/cans/caps` | `routes/can_cap.py:105` `list_all_caps` | `CanCapService.list_all_caps` (`:806`) | Postgres `caps` JOIN `cans` JOIN `hazards` | computed-from-registers |
| GET `/api/v1/hazards/` | `routes/hazards.py:270` `list_hazards` | `HazardService.list_hazards` (`hazard_service.py:441`) | Postgres `hazards` | computed-from-registers |
| GET `/api/v1/tenants/{slug}/config` | `routes/tenants.py:99` | (direct `pg.fetch_by(Tenant)`) | Postgres `tenants` | computed-from-registers |
| GET `/api/v1/tenants/{id}` | `routes/tenants.py:145` | (shell) | Postgres `tenants` | computed-from-registers |

Targets rendered:
- Name: KPI strip (Total Reports, VSR, MOR, Open, Closed, Anon Rate). Value source: `/api/dashboard/overview` + `/recent`. Confidence: high.
- Name: Reporting Trends (VSR/MOR/Diversion) chart. Value source: `/api/dashboard/trends`. Confidence: high.
- Name: Corrective Action Trends (CAN/CAP) chart. Value source: `/api/v1/cans/` + `/api/v1/cans/caps` bucketed client-side (`dashboard.js:332-385`). Confidence: high.
- Name: Last 5 Reports / Top 4 Hazards / Last 5 CANs / Last 5 CAPs cards. Value source: `/recent`, `/hazards/`, `/cans/`, `/cans/caps`. Confidence: high.
- Name: SSM Risk Trend chart, Hazard Occurrence Frequency chart. Value source: `/risk-trends`, `/hazards`. **Placeholder fallback**: hardcoded demo series for demo tenants when the API returns empty (`dashboard.js:496-509`, `:541-555`). Confidence: high.

---

## Page: public/dashboard/ae-dashboard.html

Purpose: Accountable Executive dashboard — SMS health, action queue, executive decisions.

Endpoints called:

| URL | Route | Service | Data source | Classification |
|---|---|---|---|---|
| GET `/api/v1/cans/` | `routes/can_cap.py:52` | `CanCapService.list_cans` (`:520`) | Postgres `cans` JOIN `hazards` | computed-from-registers |
| GET `/api/v1/cans/caps` | `routes/can_cap.py:105` | `CanCapService.list_all_caps` (`:806`) | Postgres `caps` JOIN `cans` JOIN `hazards` | computed-from-registers |
| GET `/api/v1/hazards/` | `routes/hazards.py:270` | `HazardService.list_hazards` | Postgres `hazards` | computed-from-registers — **result stored but never rendered (dead fetch)** (`ae-dashboard.html:217,255`) |
| GET `/api/v1/reports/` | `routes/occurrence_reports.py:241` | `ReportService.get_reports` (`report_service.py:352`) | Postgres `reports` | computed-from-registers — **dead fetch** |
| GET `/api/v1/dashboard/airline/sms-maturity` | `routes/dashboard.py:371` | `DashboardService.get_airline_sms_maturity` (`dashboard_service.py:119`) | Postgres `surveys` (score/pillars/history) + `sms_maturity` cache (recommendations) | computed-from-registers + cached |
| GET `/api/v1/cans/caps/{cap_id}` | `routes/can_cap.py:265` | `CanCapService.get_cap` (`:891`) | Postgres `caps` | computed-from-registers |
| GET `/api/v1/cans/caps/{cap_id}/decision.pdf` | `routes/can_cap.py:400` | `CanCapService.get_cap_for_decision_record` (`:904`) + `pdf_canvas.render_ae_decision_pdf` | Postgres `caps` (signature JSONB) | computed-from-registers |
| POST `/api/v1/cans/caps/{cap_id}/ae-decision` | `routes/can_cap.py:351` | `CanCapService.ae_decide` (`:1086`) | writes Postgres `caps`/`cans` | computed-from-registers (write) |
| GET `/api/v1/tenants/{id}` | `routes/tenants.py:145` | shell | Postgres `tenants` | computed-from-registers |

Targets rendered:
- Name: 4 scenario banners (SMS Health, High Exposure, Action Queue, Decision Required). Value source: `gMaturity` / `gCans` / `gCaps` computed client-side (`ae-dashboard.html:669-677`); **Decision Required = literal `'Assessed'`** (`:678`) → placeholder. Confidence: high.
- Name: SMS Maturity card (score, tier, component, recommendation). Value source: `/dashboard/airline/sms-maturity`; recommendations from `sms_maturity` cache. Confidence: high.
- Name: SMS Maturity chart. Value source: same (`history[]`). Confidence: high.
- Name: Executive Decisions queue + Recent Decisions ledger. Value source: `/api/v1/cans/caps` filtered `escalated_to_ae` / `ae_signed_at` + per-row `/caps/{id}`. Confidence: high.
- Name: CAP review modal / decision modal / export CSV+PDF. Value source: `/caps/{id}`, `/decision.pdf`, `/ae-decision`. Confidence: high.

---

## Page: public/state-oversight.html

Purpose: State regulator (CAAN) oversight overview.

Endpoints called:

| URL | Route | Service | Data source | Classification |
|---|---|---|---|---|
| GET `/api/v1/dashboard/caan/state` | `routes/dashboard.py:456` `get_caan_state` | `DashboardService.get_caan_state` (`dashboard_service.py:537`) | Postgres `tenants` (`:577`), `hazards` (`:617`), `reports` (`:643`), `survey_responses` (`:836`), `surveys` (`:799`); trend via `MetricsService.calculate_ssp_risk_trends` (`metrics_service.py:313`) | computed-from-registers |
| GET `/api/v1/tenants/{id}` | `routes/tenants.py:145` | shell | Postgres `tenants` | computed-from-registers |

Regulator scope: `operator_tenant_ids_for_regulator('caan')` (`regulator_service.py:126`, reads `regulators` + `tenants`).

Targets rendered:
- Name: KPI cards (State-wide MORs, Aggregated High-Risk Hazards, Avg State SMS Maturity + tier, Active Domestic Operators). Value source: `/dashboard/caan/state` (`kpis.*`, `sms_maturity.state.*`). Confidence: high.
- Name: Hazard level chips + State Hazard Matrix heatmap (severity×probability). Value source: same (`hazard_matrix.*`). Confidence: high.
- Name: Operator Profiles grid (**named**: tenant_id/name/icao/country + per-tenant MOR/hazard/response counts). Value source: same (`operators[]`, `dashboard_service.py:719-730`). Confidence: high — **named, not anonymized**.
- Name: Macro Trend chart (Avg Risk Index by SSP category). Value source: same (`spi_trend`, from `reports`). Confidence: high.

No placeholders on the success path; failure writes `'—'` + error banner (`state-oversight.html:366-375`).

---

## Page: public/dashboard/my-tasks.html

Purpose: department task list (assigned CAN/CAP work).

Endpoints called:

| URL | Route | Service | Data source | Classification |
|---|---|---|---|---|
| GET `/api/v1/dashboard/master-register` | `routes/dashboard.py:199` `get_master_register` | `build_master_register` (`services/master_register.py:130`) | Postgres `hazards`, `cans`, `caps` (+ `reports` for report-viewer roles) via `db/pg_query.py:33-37` | computed-from-registers |
| GET `/api/v1/tenants/{id}/config` | `routes/tenants.py:99` | `tenant_context.js:362` | Postgres `tenants` | computed-from-registers |
| GET `/api/v1/tenants/{id}` | `routes/tenants.py:145` | shell | Postgres `tenants` | computed-from-registers |

Targets rendered:
- Name: KPI cards (Total Actionable Tasks, Total Hazards, Active CANs, Overdue/Escalated). Value source: `/master-register` rows counted client-side (`my-tasks.html:270-296`). Confidence: high. Note: backend skips the assignee filter for hazards (`master_register.py:398-408`), so "Total Hazards" is tenant/department-wide.
- Name: Task table (Reference, Title, Type, Status, Priority, Target Date). Value source: same endpoint (rows filtered client-side to CAN/CAP). Confidence: high.
- Name: Status filter. Value source: `data.by_status` computed only from the current page of rows (`master_register.py:951-955`). Confidence: high.

---

## Notable corrections / caveats
- **Diversions are PostgreSQL, not Firestore.** `FlightDiversionService._fetch_all_for_scope` uses `pg.fetch_all(FlightDiversion)` → table `flight_diversions` (`flight_diversion_service.py:7-8,24-31`). The "Firestore-hosted" comments in `spi_service.py:488,528,574-577` are stale.
- **Dead fetches** on `ae-dashboard.html`: `/api/v1/hazards/` and `/api/v1/reports/` results (`gHazards`, `gReports`) are never rendered (`:217,255`).
- **Legacy prefix**: `public/js/api/dashboard.js` uses `/api/dashboard` (legacy), served by the same `dashboard.py` handler mounted at `settings.API_PREFIX_DASHBOARD_LEGACY` (`config.py:68`, `main.py:256`).
