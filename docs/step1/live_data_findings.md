# Live Data Findings — Step 1

Recorded 2026-10-08. Read-only findings from the live environment and
from SME clarification. None of these are Step 1 fixes; they are
records for Step 2 and for audit visibility.

---

## L1 — Demo tenants with auto-generated slugs

Tenants `hzcons-5542802ee5` and `trirev-e770db8407` have slugs that
combine a name fragment and a UUID fragment. They are Demo status in
production-setup.html.

SME ruling (2026-10-08): they are scheduled for removal. They are
not fixtures. Phase 1D (State SPI/SPT) must exclude them from state
aggregates because they will not exist at pilot.

---

## L2 — State-level aggregates must exclude demo tenants

The State Regulator dashboard is a subscriber-facing product. State
SPI/SPT persistence must decide whether demo tenants contribute to
state-level aggregates.

SME recommendation on record: exclude demo tenants from state-level
aggregates unless explicitly included for testing. Final decision
belongs to the SME at Phase 1D.

---

## L3 — Create User dropdown presents two regulator options with the same role

`public/admin/setup/step3-manage.html:235` and `:236` (also at
`:299-300`) present:

- "CAAN SMD (Regulator)" — value `CAAN_SMD`
- "State SMD (Regulator)" — value `STATE_SMD`

Because backend code normalises `STATE_SMD` inward to `CAAN_SMD`
(see L4 below), these two options set the same effective role.

Recorded as Step 1 item 1A.6. Fix (remove or relabel) is scheduled
after 1A.5.

Note: the dropdown lives in `setup/step3-manage.html`, not directly
in `production-setup.html`.

---

## L4 — Role canonical direction: STATE_SMD is canonical

SME ruling (2026-10-08):
    STATE_SMD is the canonical regulator role.
    CAAN_SMD is a legacy alias to be retired.

Current code treats CAAN_SMD as the internal canonical and
normalises STATE_SMD inward:
    backend/app/middleware/auth.py:57
        _ROLE_CLAIM_ALIASES = {"STATE_SMD": "CAAN_SMD"}
    backend/app/core/config.py:30-35
        comment: STATE_SMD normalised to CAAN_SMD
    backend/seed/config.py:1017
        regulator seed stores role: "CAAN_SMD"

This is a Nepal-specific assumption. For a multi-state product
(Nepal CAAN, Maldives CAAM, India DGCAI, etc.) the role must be
state-neutral. Using CAAN_SMD as the canonical encodes one state
into the role name.

The refactor is Step 2 work: flip the normalisation direction,
migrate stored claims, remove the CAAN_SMD alias.

Step 1 records this finding. Step 1 does not perform the refactor.
Step 1 tests use whichever name the code emits for authenticated
regulator users — verify from code, not intent.

Affected files (for Step 2 planning):
    backend/app/middleware/auth.py:57
    backend/app/core/config.py:30-35
    backend/seed/config.py:1017

Note on STATE_SMD scope:
    STATE_SMD = State Safety Management role.
    The corresponding department or division inside the authority
    is per-state and is not encoded in the role name. For Nepal it
    is the Safety Management Division; another state may have a
    Safety Management Department.

### L4 evidence — user-visible consequence (2026-10-09)

Item 1A.6 removed the redundant CAAN_SMD option from the Edit User
and Create User dropdowns. The residual is that existing accounts
stored with role CAAN_SMD open blank in the Edit modal's role select
until re-selected.

This confirms that the L4 mismatch is not only a naming preference:
the stored value and the UI value disagree, and the disagreement has
a user-visible effect. The Step 2 refactor is required to resolve it.

---

## L5 — Both state and airline are tenants; role distinguishes them

The data model has one `tenant` object. Both a state regulator and
an airline are tenants. They differ by the user's role
(`STATE_SMD` vs `TENANT_ADMIN` / `DEPT_ADMIN` / `OFFICER` /
`ACCOUNTABLE_EXECUTIVE`) and by the tenant's kind.

The regulator tenant oversees airline tenants.
The airline tenant operates and reports.

This is the correct model. It scales to multi-state and to the
ICAO cross-border oversight case (L9).

---

## L6 — Slug visibility policy

Admin tooling (`production-setup.html`, setup pages) shows both the
display name and the slug. The slug is operationally useful for
error-catching: if a wrong slug was entered, the Super Admin sees
it.

End-user surfaces (dashboards, reports, menus) show the display
name only.

Audit evidence and API responses include both.

Rule: never expose a slug to an end user.

Regulator slug pattern (SME-confirmed):
    Regulator slug is authority-specific, not generic:
        caan   = Civil Aviation Authority of Nepal
        caam   = Civil Aviation Authority of Maldives
        dgcai  = DGCA India
    Pattern: authority acronym, lowercased, no separators.

Note: the slug is currently free-form in production-setup.html.
Step 2 will decide whether to enforce the pattern. In the interim,
note that "test-regulator" and any hyphenated slug do not match the
pattern; this is acceptable for test fixtures but should not be
used for real regulators.

---

## L7 — Multi-state is architectural but not provisioned

The application is architecturally multi-state (regulator slugs
`caan`, `caam`, `dgcai`). No second state is currently provisioned.
Live data is Nepal-only.

The CAAN_SMD → STATE_SMD rename (L4) is required precisely because
the role must be state-neutral when the second state is added.

---

## L8 — Module 3 governance and access model

Module 3 is PSOE Audit. It measures whether an SMS's internal
organs are present, suitable, operating, and effective, using audit
instruments at `psoe-dashboard.html`.

Module 3 is a shared capability. It is an add-on product for
tenants. The two uses are separated by which tenant the user
belongs to and which role they hold, not by separate schemas:

    - A state regulator tenant uses Module 3 for oversight audits
      of airlines under its jurisdiction.
    - An airline tenant uses Module 3 for self-assessment.

Login path determines governance. At login, RBAC and Firebase
claims determine which dashboard the user reaches. A user with
Module 3 access on the airline tenant side cannot write to the
state database; a user with Module 3 access on the state tenant
side conducts oversight audits on airlines.

Creation order: a state regulator tenant must exist before any
airline tenant is created. An airline cannot exist without a
state.

Reporting relationship is set at airline-tenant creation. When an
airline tenant is created, if two or more state regulators exist,
the Super Admin selects which state the airline reports to. That
choice is fixed at tenant creation time.

Access enforcement: the backend must prevent an airline user from
writing to a state database and vice versa. Mechanism is RBAC at
the route level combined with the tenant the user's role is bound
to. Whether this is enforced today or needs strengthening is a
Step 2 question.

Property to verify (Step 2): a user with Module 3 access on an
airline tenant cannot write to any state-owned table or endpoint.
Conversely, a state user cannot write to an airline's operational
data (only read through the oversight relationship). Verification
is a Step 2 test.

Super Admin toggle: the Super Admin makes Module 3 available or
unavailable per tenant via the production-setup tenant table.

---

## L9 — ICAO multi-state oversight

Under ICAO, an airline operating flights in two states is subject
to oversight by both. The product does not provision multi-state
operation today. It must not be designed in a way that prevents it.

Implication for Step 2: the membership model must allow a user (or
an oversight relationship) to be scoped to multiple regulators if
the airline operates in multiple states. The reporting relationship
is one-to-one today but should be modelled so it can become
one-to-many without a schema migration.

---

## L10 — SAFETY_OFFICER retirement rationale

`SAFETY_OFFICER` is a legacy role name that implies Safety is a
distinct department. It is not: CAMO, Maintenance, Operations, and
Safety all have officer-level staff. The correct role is `OFFICER`,
scoped by the department field.

Retirement is Step 2 work: migrate stored claims, remove the shim,
update dropdowns, tests, and seed scripts.

Role model refinement: a role name encodes the person's function,
not their department. A user in CAMO with officer-level function
has role `OFFICER` and department `CAMO`. A user in Safety
Management with officer-level function has role `OFFICER` and
department `Safety Management`.

---

End of live data findings.
