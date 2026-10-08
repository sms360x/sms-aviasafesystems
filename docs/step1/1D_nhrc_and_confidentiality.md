# 1D — N-HRC Linkage and Confidentiality

Read-only. Date: 2026-10-08.

## 7.1 N-HRC linkage

**Where N-HRCs are defined (code):**
- Enum/model: `backend/app/models/nhrc.py:16-25` (`NHRCCategory`: CFIT, LOC-I, MAC, RE, RI, ARC, WS).
- Runtime rules and names: `backend/app/services/nhrc_service.py` — `NHRC_MAPPING_RULES` (`:171-221`), `NHRC_NAMES` (`:156`).
- Per-hazard stored column: `hazards.nhrc_category` (`backend/app/db/db_models.py:86-88`), auto-derived with manual CAAN override.

**How the NASP benchmark/reference is stored:** three stores, no dedicated benchmark table.
1. Python constant (canonical runtime source): `NHRC_REFERENCE_DATA` (`nhrc_service.py:22-154`) — SEIs + contributing factors; served by `get_nhrc_seis`/`get_contributing_factors` (`:292-308`). The code notes it is an initial draft to validate against the official NASP (`:18-19`).
2. Firestore seed (derived copy): `backend/seeders/ssp/ssp_seeder.py:338-369` writes `state/ssp/nhrcs/{code}` (imports `NHRC_REFERENCE_DATA`, `:37`).
3. Postgres reference mapping: `taxonomy_mappings` (`db_models.py:2059-2087`) maps ICAO/ADREP/HFACS → `nhrc_category`; seeded from `data/hfacs_nanocodes.csv` and `data/icao_adrep_taxonomies.csv`.
- SSP/state "benchmark" targets live in `state_risk_categories` (`db_models.py:2396`) and `state_risk_register.ssp_target` (`:945`), with constant defaults in `state_risk_service.py:43-58`.

**How operator data is aggregated against N-HRCs:**
- Per-tenant: `NHRCService.calculate_nhrc_kpis(tenant_id)` → `_calculate_kpis_async` → `_compute_kpis` (`nhrc_service.py:271,345,364`).
- State: `calculate_state_nhrc_kpis()` → same engine with `tenant_id=None`; query `select(Hazard)` excluding the `demostate` pseudo-tenant (`:280,352-359`).
- Mapping: `map_hazard_to_nhrc` (`:241-265`); auto-derivation via `nhrc_derivation_service.py:36-85`.
- API: `backend/app/api/v1/nhrc.py` — `/nhrc/tenant/{id}/kpis` (`:21`), `/nhrc/state/kpis` (`:34`), `/nhrc/mapping-rules` (`:45`), `/nhrc/seis/{code}` (`:55`), `/nhrc/contributing-factors/{code}` (`:67`).

**Is the state view anonymous or named?**
- N-HRC state KPIs are **anonymous/aggregate** — `calculate_state_nhrc_kpis` emits only per-category KPIs, no operator identifiers (`nhrc_service.py:408-421`; model `models/nhrc.py:38-49`).
- Contrast: `StateRiskService.aggregate_state_risk` attaches `contributing_tenants` slugs (`state_risk_service.py:272`, persisted `:306`) and `DashboardService.get_caan_state` returns a **named** operator grid (`dashboard_service.py:719-730`). Anonymization is therefore **inconsistent across state surfaces**.

---

## 7.2 Confidentiality at the state surface (corrected model, 2026-10-08)

The prior version of this document characterised named-row exposure as a violation. **That interpretation was corrected by the SME on 2026-10-08.** The correct rule reflects ICAO Annex 19 and Doc 9859.

The corrected rule:
- **SDCPS sources** have different state-visibility rules: VSR is anonymous by design and reaches the state only as **aggregate intelligence**; MOR, audit reports, and accident/investigation reports are **named** and delivered to the state.
- **Internal registers** (hazard, risk, barrier, findings, CAPs): the state sees the operator's **OUTCOME** (which hazard, category, evaluated risk, barriers, acceptance status), **not PROCESS** (who did what, internal comments, assignment history, workflow, personnel names). Process is the airline's administrative work.
- **Drill-down** is the state's regulatory right: purpose-bound to a specific oversight action and **audited**. VSR anonymity is preserved even under drill-down.
- **OIP** is a commercial mechanism for aggregate intelligence, not a legal constraint on the state's right to know.

What crosses to the state, viewed through the corrected model:

| Source | Data crossing | Named? | Per model | Citation |
|---|---|---|---|---|
| `AggregationService` | Survey maturity (pillars/level), hazards (title ≤50 chars, risk level/index, ADREP) | Anonymized `Operator-N`; min 3 tenants | correct (aggregate) | `aggregation_service.py:35-118,206-211` |
| `StateRiskService.aggregate_state_risk` | Category counts + `contributing_tenants` slugs | Named by operator | correct (outcome) | `state_risk_service.py:153-279,272,361-375` |
| `DashboardService.get_caan_state` | Per-operator outcome counts (reports/hazards/responses) | Named by operator | correct (outcome) | `dashboard_service.py:614-730` |
| `SPIService.get_state_values` | Aggregate SPI | Anonymous | correct (aggregate) | `spi_service.py:303-320,493-551` |
| `NHRCService.calculate_state_nhrc_kpis` | Aggregate N-HRC KPIs | Anonymous | correct (aggregate) | `nhrc_service.py:280-286` |

Named operator **outcome** is permitted by the corrected model; only **process** exposure would be a violation, and no state endpoint was found exposing assignment history/comments/workflow.

**Implementation status of each rule in current code:**
- Outcome visibility — present (state-risk, N-HRC aggregate, SPI state, CAAN dashboards). Correct per model. See `docs/step1/1D_confidentiality_exposure_table.md`.
- Process visibility — not exposed by any state endpoint found; process stays tenant-side. Correct.
- **VSR aggregate-only — NOT enforced.** `backend/app/services/confidential_reporting_service.py` exists but is not wired to any route; reporter metadata is stored on the `reports` row itself. Whether a cross-tenant caller can read **raw** voluntary rows via `/api/v1/reports/` is undetermined and must be verified. See `docs/step1/1D_reporter_redaction_check.md` and the flagged row in `1D_confidentiality_exposure_table.md`.
- Drill-down — partially implemented: purpose-declared and audited on `/api/v1/regulator/*`, but in-memory/non-durable and not extended to state-risk/N-HRC reads. See `docs/step1/1D_drilldown_audit_coverage.md`.
- Audit coverage — partial: only `/api/v1/regulator/*` writes CAAN read audits; `/api/v1/state-risk/*` and `/api/v1/nhrc/*` do not (item 1D.10).
- OIP — not enforced; documentation-only (no `oip` code exists).

---

## Summary
- N-HRC KPI computation is real (from `hazards`) and its state view is anonymous; the NASP reference is a hardcoded draft constant plus seeds.
- The corrected confidentiality model: the state sees the operator's **outcome**, not process; **VSR is aggregate-only**; drill-down is a purpose-bound, audited state right; OIP is a commercial aggregate-intelligence mechanism, not a legal limit.
- Remaining enforcement gaps: VSR redaction/custodian isolation is unwired; drill-down is non-durable and audit coverage is partial; the OIP boundary is documentation-only. These are confidentiality items (1C.1b, 1D.7–1D.10), not new unauthenticated-access findings.

