# 1D — Gap and Scoping

Read-only. Date: 2026-10-08.

## 6.1 Current-state gap

Requirement chain: **operator register → operator SPI computation → operator SPT comparison → state aggregation → state dashboard rendering.**

| Stage | Implemented | Evidence | Gap |
|---|---|---|---|
| 1. Operator register | yes | Postgres registers `hazards`, `reports`, `cans`, `caps`, `flight_diversions`, `surveys` (`backend/app/db/db_models.py`); routes `backend/app/routes/{hazards,can_cap,occurrence_reports,flight_diversions,surveys}.py` | Register completeness gaps are tracked separately (e.g., SCCAN §2.1 fields, barrier `srm_date`). Registers exist and are queried live. |
| 2. Operator SPI computation | partial | `SPIService` computes 8 SPIs live from the registers (`backend/app/services/spi_service.py:164-224`); rendered by `public/dashboard/spi-dashboard.html` | Not persisted anywhere (no `spi_calculations` table). Re-computed per request. One field fabricated (`_culture_fallback`, `:661-666`). SPI definitions/thresholds are hardcoded constants (`:21-118`), not governed data. |
| 3. Operator SPT comparison | partial | Targets are hardcoded (`SPI_DEFINITIONS`); tenant target update endpoint does not persist — it echoes a count (`backend/app/api/v1/spi.py:228-241`) | No operator SPT table; no stored operator SPI-vs-target history; comparison is transient. National SPTs do persist (`state_safety_performance_targets`, `state_spt_service.py`). |
| 4. State aggregation | partial | `StateRiskService.aggregate_state_risk` + `sync_register_from_aggregation` persist `state_risk_register` (`state_risk_service.py:153,281`); `aggregation_materializer.py` writes `module_c_aggregates`; `DashboardService.get_caan_state` computes live (`dashboard_service.py:537`) | Operators are **named** in `state_risk_register.contributing_tenants` and in the CAAN operator grid; aggregation is a mix of live-computed and persisted; RLS is bypassed on the app path (see `rls_bypass_finding.md`); no OIP boundary. Demo tenants are included (L1/L2). |
| 5. State dashboard rendering | yes | `public/state-oversight.html`, `public/dashboard/{state-sms-maturity,spi-dashboard,nhrc-kpis}.html`, `public/state-risk-register.html` | Renders computed output; some blocks have placeholder fallbacks (SPI/N-HRC trend charts; culture score). |

Supporting findings that bound the gap:
- **Confidentiality is not enforced on the state path**: raw operator rows cross to named state views; the confidential-reporting service is implemented but **not wired to any route**; OIP/"only intelligence leaves" is documentation-only.
- **Audit coverage is partial**: only `/api/v1/regulator/*` writes CAAN read/drill-down audit rows; `/api/v1/state-risk/*` and `/api/v1/nhrc/*` do not.
- **RLS is bypassed on the app path** (owner connection + Supabase-JWT policies). Isolation currently rests on application code.

---

## 6.2 Step 4 scoping (ordered by dependency)

Step 4 (intelligence layer: OIP → M14 → RBO) cannot be built on transient operator measures. Prerequisites, in order:

1. **Persist operator SPI computations.**
   - What: a durable `spi_calculations` table written on a schedule/event, keyed (tenant, spi, period); services read persisted rows instead of recomputing.
   - Why: OIP/state aggregation and audit reproducibility require stable per-period numbers.
   - Depends on: nothing (Builds on `SPIService`).

2. **Govern SPI definitions and persist operator SPTs.**
   - What: move hardcoded `SPI_DEFINITIONS` targets/thresholds into `metric_definitions` (already exists); add an operator SPT table (or per-tenant target rows) and make `POST /spi/tenant/{id}/targets` persist.
   - Why: comparison of actual vs target must be stored and versioned; the current endpoint is a no-op.
   - Depends on: 1.

3. **Operator SPI → SPT comparison (persisted).**
   - What: compute and store per-period SPI-vs-SPT status; render from stored rows.
   - Why: this is the operator-level "safety performance" product the state layer consumes.
   - Depends on: 1, 2.

4. **State aggregation from persisted operator measures.**
   - What: state aggregates computed from persisted SPI/SPT (and registers), stored in `module_c_aggregates` (national scope, `tenant_id NULL`); exclude demo tenants scheduled for removal (L1/L2).
   - Why: one number per measure, reproducible for the reporting period.
   - Depends on: 1, 3.

5. **State dashboard rendering from persisted aggregates.**
   - What: state pages render the persisted aggregates; remove/flag placeholder trend and culture fallbacks.
   - Why: a subscriber-facing state product must not display synthesized series.
   - Depends on: 4.

6. **Confidentiality and the operator→state boundary.**
   - What: wire `confidential_reporting_service` to the reporting routes; make the state surface aggregate/anonymous by default with purpose-bound, time-limited, audited drill-down; extend CAAN read auditing to `/api/v1/state-risk/*` and `/api/v1/nhrc/*`.
   - Why: protects safety-report confidentiality and operator trust; required before OIP.
   - Depends on: 4 (and the Step 2 membership/oversight model for enforcement).

7. **OIP boundary (Step 4 proper).**
   - What: define and implement the Operator Intelligence Pack as the only operator→state path, consuming the persisted operator measures from items 1–5.
   - Why: this is the Step 4 intelligence layer's input contract.
   - Depends on: 4, 6, and the Step 2 membership/tenant-key decisions.

Note: items 1–3 are operator-side and can proceed within Step 1's "State SPI/SPT persistence" theme (Phase 1D). Items 4–7 depend on the Step 2 governance model and are Step 4 scope.
