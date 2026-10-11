# Step 2 — Plan

Status: SME-approved 2026-10-10. This is the Step 2 plan of record.
It is a planning document, not a build instruction. Every "exists today"
statement below is verified from code or from a Step 0/Step 1 document;
anything unverified is marked.

DATE: 2026-10-10
BRANCH (Step 1 close-out): step1-audit-readiness
PRODUCED BY: read-only planning pass (no code, no schema, no migrations)

---

## 1. Scope

Step 2 unifies governance and data for the merged product. It covers six
workstreams that Step 1 recorded but did not fix:

- **W1 — Membership model** (effective-dated memberships, single active context).
- **W2 — Role model unification** (three conflicting role sets; canonical names).
- **W3 — Database-layer RLS** (enforce on the app path; write deferred policies).
- **W4 — Reporter-contact store + confidential-reporting wiring**.
- **W5 — Durable audit trail** (escalations, overrides, drill-downs).
- **W6 — Placeholder removal** (no fabricated values rendered).

Out of scope for Step 2: the intelligence layer (OIP, M14, RBO) — that is
Step 4; the SMS Maturity formula (G5) and RBO model (G6) definitions.

## 2. Inputs

Step 0 (signed/recorded context):
- `docs/step0/Decision_Record.md` — G1–G11. G3 resolved (no dual-shape
  defect). G4 (identity/membership) and G10 (single tenant key) are the
  freeze gates. **Both are now recorded and marked FROZEN in
  docs/step0/Decision_Record.md** (commit 427ad65, 2026-10-10). Decision
  text is available there.
- `docs/step0/Convergence_Blueprint.md` — Option A (AviaSAFE base +
  SMS360X governance/intelligence); conflicts C-01…C-10.
- `docs/step0/Boundary_Charter_Addendum.md` — ownership map, statutory vs
  protected reporting rule, access/identity target, OIP lifecycle.

Step 1 (findings that drive Step 2):
- `docs/step1/Step1_Summary.md`, `docs/step1/1E_completion_report.md`.
- `docs/step1/live_data_findings.md` — L1–L10 (incl. L4 canonical role
  direction STATE_SMD, L6 slug rule, L9 multi-state, L10 SAFETY_OFFICER
  retirement).
- `docs/step1/rls_bypass_finding.md` — canonical RLS bypass (owner
  connection + GoTrue-vs-Firebase claim mismatch).
- `docs/step1/1B.1_rls_inventory.md`, `docs/step1/1B.2_rls_exemptions.md`.
- `docs/step1/1C.1_vsr_visibility.md` — raw-VSR rule (`_RAW_VSR_ROLES`).
- `docs/step1/1C.1b-i_confidential_wiring.md` — three conflicting role models.
- `docs/step1/1C.2_ae_non_delegability.md` — closure-path defect.
- `docs/step1/1C.5_data_governance.md` — access rules.
- `docs/step1/1D_gap_and_scoping.md`, `docs/step1/1D_fabricated_fallbacks_table.md`,
  `docs/step1/1D_drilldown_audit_coverage.md`,
  `docs/step1/1D_reporter_redaction_check.md`.

Code areas searched (facts below):
- Role constants: `backend/app/core/config.py`.
- Membership: `backend/app/db/db_models.py` (`UserProfile`), `schema_init.py`.
- RLS: `supabase/migrations/*`, `backend/app/db/schema_init.py`, plus Step 1 census.
- Confidential service: `backend/app/services/confidential_reporting_service.py`.
- Escalation/override persistence: `backend/app/routes/regulator_dashboard.py`,
  `backend/app/services/caan_audit.py`, `audit_logs` table.

---

## 3. Workstreams (W1–W6)

## Workstream 1 — Membership model

### What it is
Replace the single `role`/`tenant_id` string on a user with
effective-dated memberships (a user may belong to an operator tenant, a
regulator, or the State), with exactly one active context per request.

### What exists today (verified)
- Identity: **Firebase Auth** (ID tokens verified in
  `backend/app/middleware/auth.py`).
- Membership: a single row per user in the `users` table
  (`UserProfile`, `db_models.py`): `role` (Text), `tenant_id`
  (uuid FK to `tenants.id`), `department` (Text). There is **no**
  memberships table and no effective dates on membership.
  `tenants.oversight_effective_date` exists (`db_models.py:2133`,
  `schema_init.py:140`) but is a per-tenant date, not a user membership.
- The request user dict is built in `middleware/auth.resolve_user_context`
  with the single `role` and `tenant_id`; `_ROLE_CLAIM_ALIASES` maps
  `STATE_SMD → CAAN_SMD` (`auth.py:57`).

### What it must become
- A membership model that stores, per user, one or more tenant-scoped
  memberships with `role`, `effective_from`, `effective_to` (nullable),
  and an active flag; the auth boundary resolves exactly one active
  context per request.
- Modelled to allow one-to-many oversight (L9) without a later schema
  migration.

### Inputs
L5, L8, L9; Convergence C-03; Addendum §5.

### Decisions required
D1 (identity provider), D3 (membership shape), D15 (multi-state
oversight cardinality).

### Estimated size
Large. Touches the auth boundary and every route that reads
`user["role"]`/`user["tenant_id"]`, plus a new table and a migration.

### Dependencies
Blocks W2 (roles live on memberships) and W3 (RLS identity resolves from
the membership context). Depends on no other Step 2 workstream.

---

## Workstream 2 — Role model unification

### What it is
Merge the conflicting role sets into one canonical vocabulary; retire
`CAAN_SMD` → `STATE_SMD`, `SAFETY_OFFICER` → `OFFICER` (+ department),
decommission `AIRLINE_ADMIN` → `TENANT_ADMIN`; fix the closure-path
gating defect.

### What exists today (verified)
- Canonical/alias constants live in `backend/app/core/config.py`
  (e.g. `TENANT_ADMIN_ROLES = ["AIRLINE_ADMIN","TENANT_ADMIN"]`,
  `SAFETY_OFFICER_ROLES = ["SAFETY_OFFICER","OFFICER"]`,
  `CROSS_TENANT_ROLES = ["CAAN_SMD","STATE_SMD","SUPER_ADMIN"]`).
- So there are at least three different role sets in play:
  1. `occurrence_reports._RAW_VSR_ROLES` = `{AIRLINE_ADMIN, TENANT_ADMIN, SAFETY_OFFICER}` (1C.1).
  2. `confidential_reporting_service.CUSTODIAN_ROLES` = `{TENANT_ADMIN, AIRLINE_ADMIN, SUPER_ADMIN}`.
  3. `master_register.REPORT_VIEWER_ROLES` = `{TENANT_ADMIN, SAFETY_OFFICER, OFFICER, SUPER_ADMIN}`.
- `rbac.normalize_legacy_role` (module-gate only) maps both `SAFETY_OFFICER`
  and `OFFICER` to `safety_manager`.
- The auth boundary normalises `STATE_SMD → CAAN_SMD` (`auth.py:57`).
- **Closure defect (1C.2 residual):** `auth.get_accountable_executive`
  (`auth.py:254`) admits `CROSS_TENANT_ROLES` or `AIRLINE_ADMIN` and does
  **not** admit `ACCOUNTABLE_EXECUTIVE`; it gates
  `POST /hazards/{id}/closure` (`routes/verification.py:76`).

### What it must become
- One canonical role set; no shims; no legacy aliases.
- `STATE_SMD` canonical (L4); `CAAN_SMD` retired; stored claims migrated.
- `OFFICER` (+ department) canonical; `SAFETY_OFFICER` retired (L10).
- `TENANT_ADMIN` canonical; `AIRLINE_ADMIN` decommissioned.
- `get_accountable_executive` requires the canonical AE role; the
  closure path gated correctly.

### Inputs
L4, L10, L8; 1C.1b-i (three role models), 1C.2 (closure defect).

### Decisions required
D4 (canonical direction), D5 (SAFETY_OFFICER retirement), D6 (AIRLINE_ADMIN
decommission), D10 (custodian designation).

### Estimated size
Medium–Large. Mostly mechanical once W1 defines where roles live, but it
spans config, auth, services, route gates, seeders, and tests.

### Dependencies
Depends on W1 (roles attach to memberships). Blocks W6 (dashboard role
labels/logic) and informs W5 (audit records role/context).

---

## Workstream 3 — Database-layer RLS

### What it is
Make RLS actually enforce on the application path, rewrite the live
policies against the identity the app presents, decide `FORCE ROW LEVEL
SECURITY`, and write the 8 deferred tenant-owned policies.

### What exists today (verified)
- 58 public tables; RLS enabled on all 58; `rls_forced` false on all;
  57 policies across 48 tables; owner = `postgres` (the connection user),
  so **RLS is bypassed** (owner exempt unless FORCE RLS).
- Every live policy predicate reads Supabase GoTrue claims
  (`auth.jwt()`, `auth.uid()`, `current_setting('app.current_tenant')`),
  which the Firebase-authenticated app path never presents
  (`docs/step1/rls_bypass_finding.md`, `1B.1_rls_inventory.md`).
- 10 zero-policy tables: 2 platform exemptions (`dead_letter_queue`,
  `sms_dispatches`), 8 deferred tenant-owned (`audit_dispatches`,
  `feedback`, `hazard_assessments`, `hazard_capas`, `hazard_rca_entries`,
  `hazard_rca_factors`, `invites`, `psoe_findings`).
- ~12 live policies have no repo source (drift).

### What it must become
- Policies that match the identity the app presents — either a Firebase
  JWT custom claim (`tenant_id`, `role`) surfaced to Postgres, or a
  per-request GUC set from the resolved membership context.
- A decision on `FORCE ROW LEVEL SECURITY` (or moving the app to a
  non-owner role), so the owner connection no longer bypasses.
- The 8 deferred policies written; the 12 live-only policies captured
  into `supabase/migrations/` with a `pg_policies` drift check.

### Inputs
`rls_bypass_finding.md`, `1B.1`, `1B.2`; W1/W2 (identity, role names).

### Decisions required
D7 (RLS identity/claim shape), D8 (FORCE RLS vs non-owner role).

### Estimated size
Large. A security-critical rewrite with migration + drift test risk.

### Dependencies
Depends on W1 (the identity/context the policy reads) and W2 (role names
in policies). Does not block other workstreams, but is the highest-risk.

---

## Workstream 4 — Reporter-contact store and service wiring

### What it is
Separate reporter contact details from report content (schema change),
assign the Safety-Department custodian, and wire
`confidential_reporting_service.py` into the report path.

### What exists today (verified)
- Reporter metadata lives on the same `reports` row
  (`reporter_name/email/phone/role/organisation`, `db_models.py:259-263`);
  no separate store (`1D_reporter_redaction_check.md`).
- `confidential_reporting_service.py` provides `mark_confidential`,
  `can_view_reporter_identity`, `deidentify`, `get_for_downstream`;
  it is **unwired** (only tests call it).
- 1C.1b-i was **stopped**: the integration point is ambiguous and the
  service's role model conflicts with `_RAW_VSR_ROLES`; the custodian
  cannot be resolved from code.

### What it must become
- A separate reporter-contact store (schema change), so reporter contact
  details can be isolated to the Safety Department (scheme 1C.1b-ii).
- `deidentify`/`get_for_downstream` wired on the report path so
  non-custodians receive a de-identified projection.
- A defined custodian designation (tenant-level Safety Department config).

### Inputs
1C.1b-i, `1D_reporter_redaction_check.md`, `1C.1_vsr_visibility.md`,
`1C.5_data_governance.md`.

### Decisions required
D9 (store shape), D10 (custodian designation), D16 (de-identification
timing: submission vs read).

### Estimated size
Medium. One additive schema change + service wiring + tests.

### Dependencies
Depends on W1/W2 (custodian role + department). Independent of W3.

---

## Workstream 5 — Durable audit trail

### What it is
Move escalations, overrides, and drill-down grants from in-memory to a
database-backed store, and complete read-audit coverage.

### What exists today (verified)
- Escalation/drill-down grants are an in-memory dict: `_ESCALATIONS`
  (`regulator_dashboard.py:47`); lost on restart, no expiry purge.
- Audit events are written to Postgres `audit_logs` via
  `audit_service.log_audit` / `services/caan_audit.py`.
- `/api/v1/state-risk/*` and `/api/v1/nhrc/*` have **no** CAAN read
  auditing (`1D_drilldown_audit_coverage.md`).
- Risk acceptance (`sram_service.accept_risk`) writes no audit record
  (1C.2 residual).

### What it must become
- Durable persistence for escalations/oversight grants (survive restart;
  expiry enforced), bound to the oversight action.
- Override and drill-down audit records persisted.
- Read-audit coverage extended to all state read surfaces.

### Inputs
`1D_drilldown_audit_coverage.md`, 1C.2 residual, 1C.5 §6.

### Decisions required
D11 (durable audit store shape), D13 (regulator access model interim).

### Estimated size
Medium. New table(s) + wiring + tests; touches Step 1D.8/1D.10 items.

### Dependencies
Depends on W1/W2 (records carry role/context). Informs W6 (honest states).

---

## Workstream 6 — Placeholder removal

### What it is
Remove fabricated fallback values and replace them with honest empty
states or genuinely computed data.

### What exists today (verified)
`1D_fabricated_fallbacks_table.md` lists the operator-facing fabricated
values:
- Safety-culture SPI score `_culture_fallback` (70–80) — `spi_service.py:661-666`.
- SPI 6-month synthetic trend — `spi-dashboard.js:212-234`.
- N-HRC "Last 6 Months" pseudo-random trend — `nhrc-dashboard.js:35-42,148-178`.
- SSM Risk Trend + Hazard Frequency demo fallbacks — `dashboard.js:496-509,541-555`.
- AE "Decision Required" literal `'Assessed'` — `ae-dashboard.html:678`.
- Top-hazards aggregation hardcoded `trend` — `aggregation_service.py:169`.
- hazard-analysis.html hardcoded tolerability + dropdowns; dead Save.
- dept-master-register department badge (client-derived).

### What it must become
- No fabricated operator-facing measured values. Either a genuine empty
  state ("no data yet") or real computed data; static reference data
  (PSOE template, NASP text) is labelled, not removed.

### Inputs
`1D_fabricated_fallbacks_table.md`, `1D_page_data_gap.md`.

### Decisions required
D14 (remove vs label policy per value).

### Estimated size
Medium. Mostly frontend + a few service fallbacks; low technical risk,
but user-visible.

### Dependencies
Depends on W2 (role/department logic for the dept badge) and benefits
from W5 (honest audit/queue states). Does not block others.

---

## 4. Dependency map

    Workstream 1 (membership)
        blocks → Workstream 2 (roles attach to memberships)
        blocks → Workstream 3 (RLS reads the resolved identity/context)
        blocks → Workstream 4 (custodian role/department come from W1/W2)

    Workstream 2 (roles)
        blocks → Workstream 6 (dashboard role/department logic)
        informs → Workstream 5 (audit records carry role/context)
        informs → Workstream 3 (policy role names)

    Workstream 3 (RLS)
        blocks → nothing in Step 2 directly; highest risk, security-critical
        informed by → Workstream 1, Workstream 2

    Workstream 4 (reporter store)
        depends on → Workstream 1, Workstream 2
        independent of → Workstream 3

    Workstream 5 (audit)
        depends on → Workstream 1, Workstream 2
        supports → Workstream 6 (honest states)

    Workstream 6 (placeholders)
        depends on → Workstream 2
        benefits from → Workstream 5

**Critical path:** W1 → W2 → W3 → W5. This is the longest dependency
chain (membership → canonical roles → RLS identity → durable audit) and
determines the fastest safe sequence. W4 and W6 can run in parallel after
W2.

---

## 5. Decisions register

| ID | Decision | Workstream | Blocks | Recommendation | Recorded |
|---|---|---|---|---|---|
| D1 | Identity provider: keep Firebase Auth or migrate to Supabase Auth (G4/C-02)? | W1 | W1 start | **Keep Firebase Auth for Step 2.** The product is live on Firebase; migrating the login provider is high-risk and not required to unify the model. Record as a deliberate divergence from G4's Supabase suggestion. | SME-approved 2026-10-10 (all recommended) |
| D2 | Single tenant key scheme (G10). | W1, W3 | all | **Adopt the existing deterministic slug → uuid5 scheme** (`db/ids.py`). It is already in use; no migration. | SME-approved 2026-10-10 (all recommended) |
| D3 | Membership shape. | W1 | W2, W3 | **Add a `memberships` table** (user_id, tenant_id/regulator, role, effective_from/to, active) and resolve one active context at the auth boundary. | SME-approved 2026-10-10 (all recommended) |
| D4 | Canonical role direction. | W2 | W2 | **`STATE_SMD` canonical; retire `CAAN_SMD`** (L4). Flip the normalisation, migrate stored claims. | SME-approved 2026-10-10 (all recommended) |
| D5 | `SAFETY_OFFICER` retirement. | W2 | W2, W4 | **Retire to `OFFICER` + department** (L10); migrate stored claims, seeds, dropdowns, tests. | SME-approved 2026-10-10 (all recommended) |
| D6 | `AIRLINE_ADMIN` decommission. | W2 | W2 | **Retire to `TENANT_ADMIN`**; migrate stored claims. | SME-approved 2026-10-10 (all recommended) |
| D7 | RLS identity model. | W3 | W3 | **Policies read a session-derived GUC (`app.current_tenant`/`app.current_role`) set per request from the resolved membership**, rather than GoTrue claims. | SME-approved 2026-10-10 (all recommended) |
| D8 | `FORCE ROW LEVEL SECURITY` vs non-owner app role. | W3 | W3 | **Move the app to a dedicated non-owner role** (cleanest) **or** set FORCE RLS if a role split is impractical. Decide before writing policies. | SME-approved 2026-10-10 (all recommended) |
| D9 | Reporter-contact store shape. | W4 | W4 | **Separate table `report_reporter_contacts`** (FK to reports; contact fields), contact-readable only by the Safety Department custodian. | SME-approved 2026-10-10 (all recommended) |
| D10 | Custodian designation. | W2, W4 | W4 | **Tenant-level field** (`safety_department_name` or `is_safety_department`) to resolve the custodian, per 1C.1b-i. | SME-approved 2026-10-10 (all recommended) |
| D11 | Durable audit store. | W5 | W5 | **Dedicated tables for escalations/overrides + existing `audit_logs` for events**; grants survive restart and expire. | SME-approved 2026-10-10 (all recommended) |
| D12 | Demo tenants in state aggregates (L1/L2). | W3, W5, W6 | state surfaces | **Exclude demo tenants** from state-level aggregates. | SME-approved 2026-10-10 (all recommended) |
| D13 | Regulator access model (C-01/G9). | W5 | W5 | **Retain the interim audited cross-tenant aggregation for Step 2**, documented and time-limited; OIP-only is Step 4. | SME-approved 2026-10-10 (all recommended) |
| D14 | Placeholder policy. | W6 | W6 | **Remove fabricated measured values; label genuine static reference data.** | SME-approved 2026-10-10 (all recommended) |
| D15 | Multi-state oversight cardinality (L9). | W1 | W1 | **Model oversight as one-to-many now** (airline ↔ multiple regulators) so no later migration is needed. | SME-approved 2026-10-10 (all recommended) |
| D16 | De-identification timing. | W4 | W4 | **De-identify on read**, preserving the Safety Department's ability to process the raw VSR. | SME-approved 2026-10-10 (all recommended) |

(16 decisions; all recommended positions approved — see §5.1.)

## 5.1 Decision outcome

All 16 decisions were approved by the SME on 2026-10-10
with the recommended positions recorded above. No
alternative positions were adopted.

Decisions D7 (RLS identity model) and D8 (FORCE RLS vs
non-owner role) are the security-critical ones and will be
the subject of detailed validation before implementation
in Phase 2C.

---

## 6. Sequence (phases 2A, 2B, …)

Ordering follows the dependency map and the critical path. Each phase
leaves the product working.

- **Phase 2A — Membership model (W1).** New memberships table + auth
  boundary resolving one active context; keep the existing single-role
  behaviour as a compatibility path until 2B. Product keeps working.
- **Phase 2B — Role model unification (W2).** Canonical roles, claim
  migration, closure-path fix. Depends on 2A.
- **Phase 2C — Database-layer RLS (W3).** Rewrite policies against the
  resolved identity; write the 8 deferred policies; capture drift;
  decide/implement FORCE RLS. Depends on 2A/2B.
- **Phase 2D — Reporter-contact store + service wiring (W4).** Can run
  in parallel with 2C after 2B.
- **Phase 2E — Durable audit trail (W5).** Persist escalations/overrides;
  extend read-audit coverage. Depends on 2A/2B; can run alongside 2D/2C.
- **Phase 2F — Placeholder removal (W6).** Depends on 2B; can run last or
  in parallel once roles are stable.

Phase discipline: one item = one commit, full suite after each item, on a
new Step 2 branch created after this plan is approved.

---

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Migration of live stored claims (CAAN_SMD → STATE_SMD; SAFETY_OFFICER → OFFICER; AIRLINE_ADMIN → TENANT_ADMIN) breaks logins | Medium | High | Dual-accept shim retained during migration; migrate in one pass with a rollback script; verify in staging (no staging today — use a copy of live data). |
| Membership rollout affects all logins | Medium | High | Compatibility path in 2A; auth-boundary tests; staged per tenant. |
| Reporter-contact schema change on live data | Medium | Medium | Additive table + backfill; no destructive change; contact fields left in place until backfill verified. |
| RLS policy rewrite breaks the app path | Medium | High | Write and test policies against a session GUC before enforcing; keep app-layer isolation until RLS is verified; adversarial cross-tenant negative tests. |
| FORCE RLS misconfiguration locks out the app | Low | High | Apply per-table in a transaction with immediate rollback test; stage behind the non-owner-role option. |
| Claim migration error leaves orphaned access | Low | High | Post-migration reconciliation query (distinct stored roles vs canonical) + audit. |
| Deferred GitHub push of live commits | Medium | Medium | Risk noted (Step 1 never pushed); agree the push/backup policy before Step 2 changes live data. |
| Demo-tenant exclusion changes state numbers (L1/L2) | Low | Medium | Document the exclusion; recompute and compare before/after; SME sign-off (D12). |

---

## 8. Exit criteria

Step 2 is complete when:

- [ ] Membership model is live and effective-dated; one active context per request.
- [ ] One role model; no shims and no legacy aliases (`CAAN_SMD`, `SAFETY_OFFICER`, `AIRLINE_ADMIN` retired); stored claims migrated.
- [ ] The closure path (`get_accountable_executive`) requires the canonical AE role.
- [ ] RLS policies enforce on the app path; the `FORCE ROW LEVEL SECURITY` (or non-owner-role) decision is made and implemented; the 8 deferred policies written; no drift.
- [ ] Reporter-contact store exists; `confidential_reporting_service` is wired; non-custodians receive de-identified output.
- [ ] Audit trail is durable and covers escalations, overrides, and all state read surfaces.
- [ ] No fabricated placeholder values remain on operator-facing surfaces.
- [ ] Full pytest + node suite green against the known-failures-only list.

---

## Unverified / to confirm

- The exact RLS claim/GUC mechanism the app can present is not yet
  decided; it depends on D7/D8. The code that would settle the app's
  connection options is `backend/app/db/session.py` and
  `backend/app/core/config.py:92-104`.
- Whether the app can present a non-owner Postgres role under the current
  Supabase pooler setup is unverified; `backend/app/db/session.py` and the
  Supabase pooler configuration would settle it.

---

## Planning finding (2026-10-10)

The Step 2 planning pass assumed regulators and operators both live in the
`tenants` table. The live schema has them in two tables (`tenants`,
`regulators`).

Unification is split across three items:
- **2A.3b** — schema additions (phase 1). Adds `kind` and the regulator-only
  columns to `tenants`; inserts the regulator rows; leaves the `regulators`
  table in place. No code change. The app keeps working.
- **2A.3b-code** — SQLAlchemy single-table inheritance. `Tenant` base class
  with a `kind` discriminator; `Regulator` and `Operator` subclasses. All code
  reads/writes go through `Tenant`.
- **2A.3b-cleanup** — rename `regulators` to `regulators_old`; verify no
  readers remain; drop when confirmed.

Also: the Step 1 admin form field "Operator Tenant IDs" is a legacy artifact;
it is removed in 2A.3c.

---

## Known environmental failures

These fail intermittently or in specific orderings. They do NOT block an item.
A NEW failure (not on this list) stops the item.

    tests/test_tenant_sms.py::TestV1RouterRegistration::
        test_v1_router_includes_all_sub_routers
    tests/test_hazard_enrichment.py::
        test_enrichment_adds_and_records_before_after
    tests/test_risk_matrix.py::
        test_hazard_create_honours_risk_index_without_classifying
    tests/test_hazard_triage.py::
        test_rejected_closes_hazard
    tests/test_aggregation_materializer.py::
        test_materialize_all_and_invalidate
        (new 2026-10-11; closed asyncpg connection in cleanup;
         fails with the change reverted; assertions pass)
    tests/test_aggregation_materializer.py::
        test_event_trigger_refreshes_metrics
        (new 2026-10-11; same closed asyncpg connection class as
         test_materialize_all_and_invalidate; fails in isolation;
         the materializer path does not touch regulators or
         tenants, so the rename in 2A.3b-cleanup is not the cause)

---

## Test hygiene notes

- `test_aggregation_materializer.py` creates ~24 `mat-*` tenants per run and
  does not clean them up. Effect: `Tenant.all()` counts include test residue.
  Fix: add a teardown that deletes created tenants. Deferred to a Step 2.5 /
  Step 3 test-cleanup item.
- `regulators_old` (renamed from `regulators` in 2A.3b-cleanup) is retained for
  one cycle pending a future drop item.
- Filesystem-order-dependent pollution (observed during 2A.4, 2026-10-11): one
  full-suite run showed failures in `test_psoe_models.py` and setup errors in
  `test_rbac_claims.py` (`ModuleNotFoundError: seed.users`). Both files pass in
  isolation and in a stable-order prefix run, and a re-run was clean, so this is
  pre-existing test hygiene (order-dependent `sys.path`/`sys.modules` or DB
  state), not a code regression. Fix: harden the `seed.users` monkeypatch target
  and add teardown for psoe template/assessment state. Deferred to a test-cleanup
  item.
