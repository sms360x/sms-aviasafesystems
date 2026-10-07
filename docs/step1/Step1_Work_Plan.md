# Step 1 Work Plan — Audit Readiness

Status: For SME confirmation. No code written. Work starts only after this plan is confirmed.
Date: 2026-10-07
Project: Finish AviaSAFE First — Step 1 of 4
Working dir: `D:\Projects\aviasafesms` · Branch to create: `step1-audit-readiness` (not yet created)
Evidence location: `docs/step1/`

Environment: `STAGING_ENV=no`, `LIVE_OPERATORS=yes`, `VSR_VISIBILITY_RULE=A`. No staging, product is live → one item = one commit, each revertible, full suite after every item, no deploy, no push.

---

## 0. Critical finding before planning: `SECURITY_REVIEW.md` is stale

`SECURITY_REVIEW.md` is dated 2026-09-18, before the Phase 2 implementation (2026-09-22). Direct inspection of the current code shows several listed findings are **already remediated**:

| Finding | Stated in `SECURITY_REVIEW.md` | Actual current code | Effect on Step 1 |
|---|---|---|---|
| M5 RBAC middleware dead | "not imported or added in `main.py`" | **Registered**: `backend/app/main.py:126-127` (`from app.middleware.rbac_middleware import RBACMiddleware`; `app.add_middleware(RBACMiddleware)`), commented "P2-26" | 1A.1 = verify + test, not build |
| M1 token revocation | `check_revoked=False` (`firebase.py:105`) | **Fixed**: `backend/app/firebase.py:105` is `auth.verify_id_token(token, check_revoked=True)` | 1A.5 = verify + test |
| H1 unauth SPI | "no auth dependency" | **Auth present**: every route in `backend/app/api/v1/spi.py` uses `Depends(get_current_user)` / `Depends(get_caan_user)` + `require_tenant_access` | 1A.2 = verify + regression test |
| H1 unauth N-HRC | "no auth dependency" | **Auth present**: every route in `backend/app/api/v1/nhrc.py` uses `Depends(get_current_user)` / `Depends(get_caan_user)` + `require_tenant_access` | 1A.3 = verify + regression test |
| H2 regulator role | "uses `get_current_user`, not `get_caan_user`" | **Mostly fixed**: `backend/app/routes/regulator_dashboard.py` uses `get_caan_user` on `industry-averages`, `top-hazards`, `risk-trends`, `risk-register`, `benchmark`, `export/pdf`, `export/excel`, `share/escalate`; `share/benchmark` uses `get_current_user` **with an explicit tenant-match check** (`:59-62`) | 1A.4 = residual review + caller-`tenant_ids` policy |

Consequence: Phase 1A is primarily **verification with regression tests**, not new code. This plan does not inflate scope to "close" already-closed findings; it produces evidence and tests so the closure is auditable.

---

## 1. Phase 1A — Security holes

| Item | Current state | Action | Files to touch | Test |
|---|---|---|---|---|
| 1A.1 RBAC middleware | Registered (`main.py:126-127`) | Verify module-gate + tenant-isolation behaviour; document state | (test only) `backend/tests/test_rbac_middleware.py` (new) | module-disabled tenant → 403; cross-tenant path param → 403 |
| 1A.2 H1 SPI auth | Auth present (`spi.py`) | Add regression test asserting 401 without token on all SPI routes | `backend/tests/` (new test) | unauth 401; own-tenant 200; other-tenant 403 |
| 1A.3 H1 N-HRC auth | Auth present (`nhrc.py`) | Add regression test asserting 401 without token on all N-HRC routes | `backend/tests/` (new test) | unauth 401; own-tenant 200 |
| 1A.4 H2 caller `tenant_ids` | `regulator_dashboard.py` gated; `_default_tenant_ids` defaults to 3 tenants when query absent | Enforce: non-cross-tenant roles cannot supply `tenant_ids`; cross-tenant (CAAN) scope selection allowed but explicit. Review sibling routes (`api/v1/state_risk.py`, `api/v1/tenant_reports.py`) for the same pattern | `backend/app/routes/regulator_dashboard.py`; any sibling with caller tenant ids | non-CAAN supplying foreign `tenant_ids` → 403 |
| 1A.5 M1 revocation | `check_revoked=True` (`firebase.py:105`) | Verify + regression test | (test only) `backend/tests/` (new test) | revoked token → 401 |

**Business decision needed (1A.4):** Is a cross-tenant (CAAN) role allowed to select which operator tenants it reads via a query parameter? Step 0 adopted OIP-only as the long-term regulator model; Step 1 must not entrench direct browsing. Proposed Step 1 position: allow CAAN scope selection to continue (it is the current working behaviour) but require it to be explicit and audited; Step 2 replaces it with the membership/oversight model. Confirm before implementing.

---

## 2. Phase 1B — RLS gaps and schema hygiene

### 1B.1–1B.2 The RLS-disabled tables

`DB_VERIFICATION.md` (2026-09-16) listed **6** disabled: `caan_reports`, `sms_maturity`, `state_risk_categories`, `dead_letter_queue`, `sms_dispatches`, `audit_dispatches`. Later DDL adds RLS to three of them:
- `sms_maturity` — `supabase/migrations/20260917090000_sms_maturity_rls.sql`
- `caan_reports` — `backend/app/db/schema_init.py:886-899`
- `state_risk_categories` — `backend/app/db/schema_init.py:901-912`

Likely remaining disabled (to be confirmed against the live catalog by the new test): `dead_letter_queue`, `sms_dispatches`, `audit_dispatches`. These three are **platform-wide, not tenant-owned** tables, so the likely outcome is a documented exemption rather than RLS.

| Item | Action | Files to touch | Test |
|---|---|---|---|
| 1B.1 | Confirm the exact current disabled set from `pg_tables` | (evidence only) `docs/step1/` | catalog query result recorded |
| 1B.2 | For each remaining table: enable RLS, or record a written exemption with justification (platform tables are candidates for exemption) | `scripts/supabase_rls.sql` or new migration; `backend/app/db/schema_init.py`; `docs/step1/rls_exemptions.md` (new) | cross-tenant read denied (or exemption justified) |
| 1B.3 | Test that fails if any tenant-owned table lacks RLS and lacks a recorded exemption | `backend/tests/test_rls_coverage.py` (new) + exemption list | test fails on an unguarded tenant table |
| 1B.4 | Add additive `barrier_register.srm_date` (CAAN SRM Manual §2.3.4 "SRM Date") | new `supabase/migrations/<ts>_barrier_register_srm_date.sql`; `backend/app/db/schema_init.py`; `backend/app/db/db_models.py` (Barrier register model ~`:1567`) | column exists; nullable round-trip (table empty) |

**Business decision needed (1B.2):** whether `dead_letter_queue`, `sms_dispatches`, `audit_dispatches` are exempted as platform-wide tables or given RLS. Proposed: exempt with written justification (they are not tenant-owned operational registers). Confirm.

---

## 3. Phase 1C — The 5 unique Missing compliance requirements

| Item | Current state | Action | Files to touch | Test |
|---|---|---|---|---|
| 1C.1 Confidential / voluntary reporting + `VSR_VISIBILITY_RULE=A` | Schema + service exist: `reports.is_confidential`/`confidential_custodian_id` (`schema_init.py:869-884`); `backend/app/services/confidential_reporting_service.py`; ingestion wiring deferred (Phase-2 P2-25 note) | Enforce exactly: Safety Manager → raw report; AE → aggregate counts only; no other role → raw. Any override logged + audited | `backend/app/services/confidential_reporting_service.py`; `backend/app/routes/reporting.py` / `backend/app/api/v1/tenant_reports.py`; audit writer | SM 200 raw; AE aggregate-only (no narrative); other roles 403; override writes `audit_logs` |
| 1C.2 AE non-delegability (`CAAN §2.3.3`) | Partial: authority-tier in `sram_service.accept_risk` (`backend/app/services/sram_service.py:542`); process/two-signature `process_sign_acceptance` (`:515`); CAP AE decision in `can_cap_service` | Enforce that the AE signature cannot be delegated/substituted; reject non-AE signer; immutable after signature | `backend/app/services/sram_service.py`; `backend/app/services/can_cap_service.py`; `backend/app/api/v1/endpoints/sram.py:242`; `backend/app/routes/verification.py` | non-AE signer rejected; AE signature immutable; one AE per tenant |
| 1C.3 Predictive analysis | **No code** (Doc 10159 AL-3 missing) | Minimum viable documented forward-looking function over existing registers (no new data sources, no new external services) | existing service (e.g. `backend/app/services/aggregation_service.py` or `state_risk_service.py`) + doc `docs/step1/` | function returns forward-looking output; unit test |
| 1C.4 Prescriptive analysis | **No code** (Doc 10159 AL-4 missing) | Minimum viable documented recommended-action function over existing registers | existing service + doc | function returns recommendations; unit test |
| 1C.5 Data governance | Code exists: `backend/app/services/data_governance.py` | Produce the written governance record (owner / retention / access rule) | `docs/step1/data_governance_record.md` (new) | document present; references the code |

**Business decision needed (1C.3/1C.4):** the minimum viable definition (in-scope/size of the predictive and prescriptive functions). The Phase-7 item (P7-4) defers vendor-vs-in-house; Step 1 proposes an in-house, documented, register-derived function only. Confirm the acceptance bar.

---

## 4. Phase 1D — State SPI/SPT persistence

| Item | Current state | Action | Files to touch | Test |
|---|---|---|---|---|
| 1D.1 | Table `state_safety_performance_targets` exists (`schema_init.py:752-765`); `backend/app/services/state_spt_service.py` persists SPT; state SPI inputs may be computed (cache) | Ensure State SPI values/trends are persisted durably (not cache-only) | `backend/app/services/spi_service.py`; `backend/app/services/state_spt_service.py`; `module_c_aggregates` reuse | persist then read back without recompute |
| 1D.2 | — | Add RLS + tenant-boundary tests for the state tables | new test; `scripts/supabase_rls.sql` as needed | CAAN-only national rows; cross-tenant denied |
| 1D.3 | — | Document that this was a **Partial** compliance row, not one of the 7 Missing | `docs/step1/` | note present |

---

## 5. Phase 1E — Verification

- 1E.1 Run the full suite (baseline: 1062 collected → 1061 passed, 1 pre-existing unrelated failure `test_tenant_sms.py::TestV1RouterRegistration::test_v1_router_includes_all_sub_routers`). Report pass/fail after every item.
- 1E.2 Audit evidence pack: one file per closed item in `docs/step1/` (change, test, evidence).
- 1E.3 `docs/step1/Step1_Completion_Report.md`.

---

## 6. Sequencing and commits

1A.1 → 1A.2 → 1A.3 → 1A.4 → 1A.5 → 1B.1/1B.2 → 1B.3 → 1B.4 → 1C.1 → 1C.2 → 1C.3 → 1C.4 → 1C.5 → 1D.1 → 1D.2 → 1D.3 → 1E. One item = one commit, message `Step1-<item>: <description>`, on branch `step1-audit-readiness`. Full suite after each item; a phase is reported before the next begins.

---

## 7. Stop-condition flags (must be confirmed before starting)

1. **1A.4** — cross-tenant (CAAN) caller-supplied `tenant_ids` in Step 1: allow (explicit + audited) or restrict now? (Business decision.)
2. **1B.2** — exemption vs RLS for `dead_letter_queue`, `sms_dispatches`, `audit_dispatches`. (Decision.)
3. **1C.3/1C.4** — acceptance bar for the minimum-viable predictive/prescriptive functions. (Decision.)
4. **1C.1** — confirm the exact "aggregate counts only" shape the AE may see (which fields), since the rule forbids raw narrative.

Everything else in this plan is implementable within the stated constraints (AviaSAFE-only, no auth-provider change, no tenant-key change, no schema migration beyond 1B.4 and 1D).

---

*End of Step 1 Work Plan. Awaiting SME confirmation before creating the branch and starting 1A.*
