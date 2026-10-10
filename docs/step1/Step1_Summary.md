# Step 1 — What Was Achieved and What Remains

## What Step 1 Did

Step 1 checked whether the safety platform's security, data
visibility, and compliance claims actually hold in the running
software — and then fixed or recorded every gap we found. We read
the code, ran the tests, and produced a written evidence document
for each item. Nothing was deployed as part of Step 1; every
change is a separate, reversible commit on a working branch, not
on production.

## Verified (the boundaries that hold)

Several things we expected to be broken were already correct. We
confirmed them rather than rebuilding them, and added tests so they
stay correct:

- Every SPI and N-HRC reporting endpoint requires a valid login.
- Revoked, expired, or deleted-user tokens are rejected.
- A tenant user cannot read another tenant's data through these
  endpoints.
- The role/permission gate and the tenant-isolation middleware are
  active.

## Closed (the specific gaps fixed)

- Cross-tenant exposure of Voluntary Safety Reports (VSRs) is closed.
- Raw VSRs are now limited to the owning tenant's Safety Manager
  (TENANT_ADMIN) and Safety Department officer (SAFETY_OFFICER).
- The Accountable Executive's risk-acceptance signature cannot be
  delegated.
- A dormant hazard-analysis endpoint was authenticated before it
  could be wired into the running application; it now requires a
  login and uses the session's tenant.
- A stale duplicate regulator option was removed from the admin user
  screen.
- Two small, documented analysis functions were added: one that
  projects future open-hazard counts, and one that recommends actions
  from a fixed rule list.
- A data-governance record (ownership, retention, access) was written.

## Documented (findings recorded, not fixed)

Five findings are recorded with a target phase. Some need decisions
or schema work beyond Step 1:

- **Row-Level Security is switched on but does not actually gate
  queries** because the app connects as the database owner and the
  policies expect a different login system. Today, tenant separation
  is enforced by the application code. Fix → Step 2.
- **The confidential-reporting service is not yet connected** to the
  reporting flow; reporter contact details have no separate store.
  Fix → Step 2.
- **Some dashboard charts and one banner show invented placeholder
  data** when there is nothing real to show. Fix → Step 2.
- **The audit trail is incomplete** and some oversight records are
  only held in memory. Fix → Step 2.
- **The Accountable Executive has no summary view of VSRs** (counts
  only, no narratives). Fix → Step 4.

## Achieved Culturally

- **Validate before acting:** every item first reported what the code
  really does.
- **One item, one commit:** each change is separate and revertible.
- **Known-failures-only:** every test run lists failures by name and
  classifies them; a new failure stops the work.
- **Evidence per item:** a written document with finding, action,
  tests, and result for every closed item.
- **Honesty about limits:** nothing was claimed fixed unless it was.

## What Remains

- **Step 2:** membership/oversight model; real database-layer RLS;
  reporter-contact store; role-model cleanup; durable audit; remove
  placeholder values.
- **Step 3:** the remaining data and process items recorded in the
  plan.
- **Step 4:** the intelligence layer — persist the operator measures,
  aggregate at state level, and add the operator→state intelligence
  contract (OIP).

## What an Auditor Would See

A single evidence pack: an index of every closed item with its
document and commit, a completion report, this summary, and the
individual evidence documents — each showing what was found, what
was done, what was tested, and what remains open.

## What You Would Tell CAAN

"We audited the platform against ICAO Annex 19 and Doc 9859
expectations. The access controls on our reporting endpoints are
enforced and tested; voluntary safety reports are protected and no
longer visible across organisations; the Accountable Executive's
risk acceptance is non-delegable as required. We also documented,
with target phases, the areas still to complete — chiefly enforcing
the database-level access rules and isolating reporter contact
details — and we can show the evidence for each finding."
