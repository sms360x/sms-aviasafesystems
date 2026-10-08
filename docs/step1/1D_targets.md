# 1D — Targets (computed measures and where they live)

Read-only. Date: 2026-10-08.
A "target" = a computed value/measure rendered by one or more dashboards. Classification key: computed-from-registers / demo-seeded / cached / placeholder / undetermined.

---

## T1 — Operator reporting KPIs (Total Reports, VSR, MOR, Open, Closed, Anon Rate)
- Where computed: `DashboardService.get_airline_overview` + `MetricsService.calculate_kpis` (`backend/app/services/dashboard_service.py:107`; `backend/app/services/metrics_service.py:25`)
- Where stored: not persisted; in-memory repo cache 60s (`backend/app/services/repository.py:110-111`)
- Where rendered: `public/safety.html`
- Data inputs: Postgres `reports`
- Classification: computed-from-registers (+cached)

## T2 — Reporting / monthly trends (VSR/MOR/Diversion)
- Where computed: `DashboardService.get_monthly_trends` + `MetricsService.calculate_monthly_trends` + `_merge_diversion_trends` (`dashboard_service.py:337,360`; `metrics_service.py:102`)
- Where stored: not persisted; `pg_cache` 45s for diversions
- Where rendered: `public/safety.html`, `public/risk-trends.html`
- Data inputs: Postgres `reports`, `flight_diversions`
- Classification: computed-from-registers (+cached)

## T3 — Risk distribution / SSP risk trends / hazard frequency
- Where computed: `MetricsService.calculate_risk_distribution` (`:87`), `calculate_ssp_risk_trends` (`:313`), `calculate_hazard_frequency` (`:134`); via `DashboardService` (`:332,414,409`)
- Where stored: not persisted
- Where rendered: `public/safety.html`, `public/risk-trends.html`, `public/top-hazards.html`, `public/state-oversight.html`
- Data inputs: Postgres `reports` (occurrence_type/severity)
- Classification: computed-from-registers

## T4 — SPI values / status / trend (8 SPIs incl. diversion rate, CAN/CAP closure, safety culture)
- Where computed: `SPIService.calculate_all_spis` and helpers (`backend/app/services/spi_service.py:164-224`)
- Where stored: not persisted (no `spi_calculations` table; the purge script references a non-existent one)
- Where rendered: `public/dashboard/spi-dashboard.html`
- Data inputs: Postgres `hazards`, `reports`, `cans`, `caps`, `surveys`, `flight_diversions`
- Classification: computed-from-registers; **one field is placeholder**: `_culture_fallback` fabricates a 70–80 culture score when no surveys (`spi_service.py:661-666`)

## T5 — SPI/SPT targets (thresholds)
- Where computed: hardcoded `SPI_DEFINITIONS` (`spi_service.py:21-118`)
- Where stored: not persisted at tenant level — `POST /spi/tenant/{id}/targets` echoes a count without writing (`backend/app/api/v1/spi.py:228-241`); national SPTs persist in `state_safety_performance_targets` (`state_spt_service.py`)
- Where rendered: `public/dashboard/spi-dashboard.html`
- Data inputs: constants + table `state_safety_performance_targets`
- Classification: demo-seeded (constants) / persisted (national only)

## T6 — N-HRC KPIs (per category: active hazards, avg/max risk index, trend, status)
- Where computed: `NHRCService.calculate_nhrc_kpis` / `calculate_state_nhrc_kpis` (`backend/app/services/nhrc_service.py:271,280`)
- Where stored: not persisted
- Where rendered: `public/dashboard/nhrc-kpis.html`
- Data inputs: Postgres `hazards` (+ static `NHRC_MAPPING_RULES`/`NHRC_REFERENCE_DATA`)
- Classification: computed-from-registers (KPI); demo-seeded/static (SEIs, contributing factors)

## T7 — State risk register categories (risk index, tolerability, trend, contributing tenants)
- Where computed: `StateRiskService.aggregate_state_risk` (`state_risk_service.py:153`); persisted by `sync_register_from_aggregation` (`:281`)
- Where stored: Postgres `state_risk_register` (`db_models.py:931`); reference/targets from `state_risk_categories`
- Where rendered: `public/state-risk-register.html`, `public/state-oversight.html`
- Data inputs: Postgres `hazards`, `reports`
- Classification: computed-from-registers (+persisted); **named** contributing_tenants

## T8 — State SSP targets
- Where computed/set: `StateRiskService.update_ssp_target` (`:335`, SUPER_ADMIN); `StateSPTService.set_state_spt` (`state_spt_service.py:53`)
- Where stored: `state_risk_register.ssp_target`; `state_safety_performance_targets`
- Where rendered: `public/state-risk-register.html`
- Data inputs: CAAN-authored values + `state_risk_categories` defaults
- Classification: persisted (authoritative input, not computed from registers)

## T9 — State oversight KPIs + operator profiles
- Where computed: `DashboardService.get_caan_state` (`dashboard_service.py:537`)
- Where stored: not persisted
- Where rendered: `public/state-oversight.html`
- Data inputs: Postgres `tenants`, `hazards`, `reports`, `survey_responses`, `surveys`
- Classification: computed-from-registers; **named** operators

## T10 — SMS Maturity (pillar scores, overall, tier, history)
- Where computed: `DashboardService._aggregate_surveys` + `_sms_maturity_model` + `_survey_history` (`dashboard_service.py:865,193,273`); state variant `get_caan_survey_maturity` (`:474`)
- Where stored: not persisted (live aggregation of `surveys`)
- Where rendered: `public/dashboard/ae-dashboard.html`, `public/dashboard/sms-maturity.html`, `public/dashboard/state-sms-maturity.html`, `public/state-oversight.html`
- Data inputs: Postgres `surveys`, `survey_responses`
- Classification: computed-from-registers

## T11 — SMS Maturity recommendations / priority actions (LLM)
- Where computed: `sms_maturity_service.analyze_sms_maturity` (`backend/app/services/sms_maturity_service.py:154`) via `gemini.recommend_sms_maturity_actions`
- Where stored: Postgres `sms_maturity` cache table (`db_models.py:2364`), TTL
- Where rendered: `ae-dashboard.html`, `sms-maturity.html`, `state-sms-maturity.html`
- Data inputs: survey aggregation
- Classification: cached

## T12 — Master register task counts (Total Actionable, Total Hazards, Active CANs, Overdue/Escalated)
- Where computed: `build_master_register` (`backend/app/services/master_register.py:130`, filtering/aggregation `:838-990`)
- Where stored: not persisted
- Where rendered: `public/dashboard/master-register.html`, `public/dashboard/dept-master-register.html`, `public/dashboard/my-tasks.html`
- Data inputs: Postgres `hazards`, `cans`, `caps` (+ `reports`)
- Classification: computed-from-registers

## T13 — PSOE assessment scores (overall + component)
- Where computed: `psoe_service.score_assessment` / `compute_component_scores` (`backend/app/services/psoe_service.py:154,97`)
- Where stored: Postgres `psoe_assessments` (`db_models.py:983`)
- Where rendered: `public/psoe-audit.html`
- Data inputs: `psoe_assessments` responses + static template `data/psoe_appendix10.json`
- Classification: computed-from-registers (scores); demo-seeded (template)

## T14 — Aggregated industry averages / benchmarking / anonymized operator intelligence
- Where computed: `AggregationService.calculate_industry_averages` etc. (`backend/app/services/aggregation_service.py:124,150,172,195,220`); materialized by `aggregation_materializer.py` into `module_c_aggregates`
- Where stored: `module_c_aggregates` (TTL 24h) when materialized; otherwise computed
- Where rendered: regulator shares (`public/js` consumers), state surfaces
- Data inputs: Postgres `surveys`, `hazards`, `tenants`
- Classification: computed-from-registers (anonymized `Operator-N`, min 3 tenants) / cached; **one placeholder**: `get_top_hazards` trend hardcoded (`aggregation_service.py:169`)

---

## Where the computation happens (summary)
Computation is concentrated in the Postgres-backed service layer: `dashboard_service.py` + `metrics_service.py` (operator KPIs/trends), `spi_service.py` (SPI), `nhrc_service.py` (N-HRC), `state_risk_service.py` (state risk), `state_spt_service.py` (targets), `master_register.py` (task counts), `psoe_service.py` (PSOE), `aggregation_service.py`/`aggregation_materializer.py` (cross-tenant aggregation), `sms_maturity_service.py` (cached LLM recommendations). Only the `sms_maturity` LLM output and materialized `module_c_aggregates` are persisted/cached; the rest are computed per request from live registers.
