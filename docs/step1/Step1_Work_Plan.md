# Step 1 Work Plan — Audit Readiness

Status: For SME confirmation. No code written. Work starts only after this plan is confirmed.

## 0.1 Ground-truth facts from HANDOFF_GUIDE.md (2026-10-08)

The following facts from HANDOFF_GUIDE.md materially affect this plan and are now binding context:

- Role names in the code are:
    TENANT_ADMIN, DEPT_ADMIN, OFFICER (SAFETY_OFFICER shimmed), ACCOUNTABLE_EXECUTIVE, CAAN_SMD, SUPER_ADMIN.
  Step 1 tests must use these names or the constants the code defines. Do NOT use "CAAN" as a role name. Regulator roles: STATE_SMD (canonical) and CAAN_SMD (legacy alias, still emitted by current code).
- RLS is largely bypassed on the app path. The backend connects as the Supabase owner (rls_forced = false), and live policies read Supabase JWT, not Firebase claims. Enabling RLS on a table does NOT currently enforce isolation on the app path.
- 10 tables have RLS enabled with zero policies: audit_dispatches, dead_letter_queue, feedback, hazard_assessments, hazard_capas, hazard_rca_entries, hazard_rca_factors, invites, psoe_findings, sms_dispatches.
- ~12 live RLS policies have no repo source.
- `/api/v1/dashboard*` is not in the RBAC middleware map (rbac_middleware.py ENDPOINT_MODULE_MAP). The four dashboard hubs render module-tagged data without a module-gate check. This is a pre-existing gap, now in scope for 1A.4.
- Known test failures: see §0.3 (known-failures-only gate). Only failures listed there are acceptable; any new failure stops the item.
- Authenticated frontend changes cannot be verified on localhost. App Check is domain-bound. Verification is only on the deployed site.
- The SAFETY_OFFICER -> OFFICER shim exists. Do NOT remove either role name in Step 1.
- Role list (authoritative for Step 1): SUPER_ADMIN, STATE_SMD, TENANT_ADMIN, DEPT_ADMIN, ACCOUNTABLE_EXECUTIVE, SAFETY_OFFICER (OFFICER is the canonical rename via the shim).
- Role canonical direction: STATE_SMD is canonical; CAAN_SMD is a legacy alias to retire. Current code normalises STATE_SMD inward to CAAN_SMD (`backend/app/middleware/auth.py:57`). Step 2 refactor. Step 1 records. Step 1 tests use whichever name the code emits.
- Role naming rule: role names encode function, not department. OFFICER + department field replaces SAFETY_OFFICER.
- Regulator slug pattern: authority-specific acronym, lowercased, no separators (`caan`, `caam`, `dgcai`).
- Slug visibility policy: admin tooling shows both display name and slug; end-user surfaces show display name only; audit evidence and API responses include both. Rule: never expose a slug to an end user.
- Tenant model: one tenant object. Both state regulators and airlines are tenants; role and tenant kind distinguish them.
- Module 3 governance: login path determines governance; the user's tenant and role separate state-audit from airline-self-assessment. A state regulator tenant must exist before any airline tenant. The reporting relationship is set at airline-tenant creation.
- Multi-state: architecturally supported (slugs `caan`, `caam`, `dgcai`); not yet provisioned; live data is Nepal-only.
- Confidentiality / state visibility (corrected model, 2026-10-08 — see §0.4):
    SDCPS sources carry different state-visibility rules: VSR is anonymous by design (state sees aggregate intelligence only); MOR, audit reports, and accident/investigation reports are named and delivered to the state.
    Internal registers (hazard, risk, barrier, findings, CAPs): the state sees the operator's OUTCOME (which hazard, category, evaluated risk, barriers, acceptance status), not the operator's PROCESS (who did what, internal comments, assignment history, workflow, personnel names).
    Drill-down is the state's regulatory right, purpose-bound to a specific oversight action and audited; VSR anonymity is preserved even under drill-down.
    OIP is a commercial mechanism for aggregate intelligence, not a legal constraint on the state's right to know.

## 0.2 Live data state (2026-10-08)

Regulators (2):
    caan — Civil Aviation Authority of Nepal, Module 3 active
    test-regulator — Test Regulator, Module 3 active

Tenants (5):
    sita-air, air-dynasty, saurya-airlines — real for Nepal
    hzcons-5542802ee5, trirev-e770db8407 — scheduled for removal

Users (19): see production-setup.html User Management.
    One SUPER_ADMIN; two STATE_SMD; one TENANT_ADMIN;
    three ACCOUNTABLE_EXECUTIVE; three SAFETY_OFFICER;
    the remainder are DEPT_ADMIN per tenant department.

See docs/step1/live_data_findings.md for L1–L10.

## 0.3 Known test failures

The "certify deterministic" gate is redefined as
"known-failures-only". Every run must list failures by name and
classify each as known or new. A new failure stops the item.

Pytest environmental failures (live-DB state dependent):
    tests/test_hazard_enrichment.py::
        test_enrichment_adds_and_records_before_after

Pytest pre-existing failures (from HANDOFF_GUIDE):
    tests/test_tenant_sms.py::TestV1RouterRegistration::
        test_v1_router_includes_all_sub_routers
    (may or may not appear in a given run)

Node test failures (separate suite, not collected by pytest):
    frontend-tests/test_nav_config.js::
        test_ae_narrow_menu

Rules:
    - A failure on the known list is reported but does not block.
    - A failure not on the list stops the item and is investigated.
    - The list is updated only when the SME confirms a new
      environmental failure.

Note: the node test path is frontend-tests/test_nav_config.js, not
public/frontend-tests/test_nav_config.js.

## 0.4 Confidentiality is a classification problem

The Boundary Charter's original OIP-only wording was too strict. The correct rule reflects ICAO Annex 19 and Doc 9859: SDCPS sources (VSR, MOR, audit, accident investigation) have different state-visibility rules; internal registers are visible to the state as OUTCOME, not PROCESS; drill-down is a state right, purpose-bound and audited; VSRs are anonymous by design and reach the state only as aggregate intelligence.

See docs/step1/1D_nhrc_and_confidentiality.md and the corrected exposure table (docs/step1/1D_confidentiality_exposure_table.md).

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
| 1A.6 Create User dropdown duplicate regulator option | Two options set the same effective role | Remove or relabel the stale "CAAN SMD (Regulator)" option at `public/admin/setup/step3-manage.html:235-236` (and `:299-300`); keep State SMD. Fix scheduled after 1A.5. Do NOT implement in the current item | `public/admin/setup/step3-manage.html` | manual: exactly one regulator option |

**Business decision needed (1A.4):** Is a cross-tenant (CAAN) role allowed to select which operator tenants it reads via a query parameter? Step 0 adopted OIP-only as the long-term regulator model; Step 1 must not entrench direct browsing. Proposed Step 1 position: allow CAAN scope selection to continue (it is the current working behaviour) but require it to be explicit and audited; Step 2 replaces it with the membership/oversight model. Confirm before implementing.

**Also in scope (1A.4) — module-gate leak on `/api/v1/dashboard*`.** The RBAC middleware gates only paths whose prefix is in `rbac_middleware.py` `ENDPOINT_MODULE_MAP`; `/api/v1/dashboard*` is absent, so the four dashboard hubs render module-tagged data without a module gate. Current state: not in the map. Action: add `/api/v1/dashboard` to the map so the four dashboard hubs are gated. If adding it would break a live dashboard that has not been tested against the module gate, document that as a stop condition and report instead of forcing the change.

---

## 2. Phase 1B — RLS gaps, module boundary, and schema hygiene

1B.1  Confirm current RLS state on all 6 originally-listed tables plus the 10 zero-policy tables from HANDOFF_GUIDE. Record the full list with RLS status and policy count.
1B.2  For each table with no RLS: enable RLS, or record a written exemption with justification. Platform-wide tables (dead_letter_queue, sms_dispatches, audit_dispatches) are exempted.
1B.3  Coverage test: assert that each tenant-owned table has RLS AND that the app path enforces it. Where enforcement is bypassed by the owner connection (a known pre-existing condition), the test must skip with a reason and a reference to docs/step1/rls_bypass_finding.md. Do not silently pass.
1B.4  Additive hygiene: add missing barrier_register.srm_date column (CAAN SRM Manual §2.3.4).
1B.5  Document the RLS bypass finding in docs/step1/rls_bypass_finding.md. This is a finding for Step 2 to fix, not Step 1. Step 1's job is to make it visible.

---

## 3. Phase 1C — The 5 unique Missing compliance requirements

| Item | Current state | Action | Files to touch | Test |
|---|---|---|---|---|
| 1C.1 Confidential / voluntary reporting + `VSR_VISIBILITY_RULE=A` | Schema + service exist: `reports.is_confidential`/`confidential_custodian_id` (`schema_init.py:869-884`); `backend/app/services/confidential_reporting_service.py`; ingestion wiring deferred (Phase-2 P2-25 note) | Enforce exactly: Safety Manager → raw report; AE → aggregate counts only; no other role → raw. Any override logged + audited | `backend/app/services/confidential_reporting_service.py`; `backend/app/routes/reporting.py` / `backend/app/api/v1/tenant_reports.py`; audit writer | SM 200 raw; AE aggregate-only (no narrative); other roles 403; override writes `audit_logs` |
| 1C.1b Confidential reporting service wiring | `confidential_reporting_service.py` exists but is not wired into the report submission path | (a) Redact the reporter's identity before report content enters any register; (b) isolate reporter contact details so only the airline's Safety Department sees them; (c) preserve any self-identified names in the report body as report content, not reporter metadata. Wire the service, or document the schema gap that prevents wiring | `backend/app/services/confidential_reporting_service.py`; report submission path; `docs/step1/1D_reporter_redaction_check.md` | redaction check; contact-isolation check |
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
| 1D.7 Confidentiality classification table | Corrected ICAO model (§0.4) | Produce the SDCPS / internal-register / drill-down classification table and apply it to the traced endpoints | `docs/step1/1D_confidentiality_exposure_table.md` | table present; each row classified |
| 1D.8 Escalation persistence | Escalations are in-memory (`regulator_dashboard.py:_ESCALATIONS`) | Persist drill-down/oversight grants durably; bind to the oversight action; purge on expiry | `backend/app/routes/regulator_dashboard.py` (Step 2 work) | grant survives restart; expiry enforced |
| 1D.9 Fabricated fallback values | Synthetic values exist (SPI `_culture_fallback`; safety demo charts; SPI/N-HRC placeholder trends; AE "Decision Required" literal) | Remove or explicitly label every fabricated/placeholder value | `docs/step1/1D_fabricated_fallbacks_table.md` | no unlabeled synthetic value rendered |
| 1D.10 Drill-down audit coverage | Only `/api/v1/regulator/*` writes CAAN read audits; `/api/v1/state-risk/*` and `/api/v1/nhrc/*` do not | Extend purpose-bound, audited drill-down/read coverage to all state read surfaces | `docs/step1/1D_drilldown_audit_coverage.md` | every state read/drill-down audited |

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
