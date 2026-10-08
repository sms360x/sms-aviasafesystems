# Step 1 Handoff — Pause Point 2026-10-08

Pause after 1A.4. Branch `step1-audit-readiness`. Working tree
clean. Commit `cb00744` at HEAD. Not merged to main. Not pushed
(GitHub write access for the local SSH account is pending; the
SME will resolve it separately).

## Where We Are

Step 1 of the "Finish AviaSAFE First" plan. Phase 1A (security
verification and small fixes) is nearly complete.

### Commits on the branch (oldest first)

    98a5987  Step1-0: add confirmed Step 1 work plan
    e55d3a7  Step1-1A.1: verify RBAC middleware registered
    1b7d7c9  Step1-docs: HANDOFF_GUIDE ground truth; RLS bypass finding
    88e9447  Step1-1A.1: RBAC middleware evidence; stale-test rewrite
    e3f647d  Step1-1D: Phase 1D findings; ICAO confidentiality model
    feb9cf5  Step1-1D: resolve flagged VSR row; refine 1C.1b and 1D.10
    af7ab71  Step1-docs: note on expected empty department registers
    56c0326  Step1-1A.7: close VSR cross-tenant exposure
    fbca608  Step1-1A.7-ext: close residual VSR exposure in PUT
    4189f15  Step1-1A.2-followup: fold SPI tenant gap into 1A.4
    5da4b2d  Step1-1A.2: SPI authentication regression tests
    420c99e  Step1-1A.2 (corrective): restore original tests + additions
    a31876f  Step1-1A.3: extend existing N-HRC authentication tests
    cb00744  Step1-1A.4: close middleware map gaps (HEAD)

(The handoff commit itself will follow cb00744.)

### Items closed

    1A.1  RBAC middleware verified + stale test rewritten
    1A.2  SPI authentication verified; residual folded into 1A.4
    1A.3  N-HRC authentication verified; residual folded into 1A.4
    1A.4  Middleware map gaps closed (3 paths added)
    1A.7  VSR cross-tenant exposure closed (3 endpoints)
    1D    Data-completeness findings documented (5 deliverables)
    Phase 1F  Not added — findings resolved as correct behaviour

### Items remaining in Phase 1A

    1A.5  Token revocation — verify + regression test
    1A.6  Create User dropdown — remove stale CAAN SMD option
    1A.8  Authenticate hazard_analysis.py; derive tenant from session

(1A.9 and 1A.10 are lower priority; may fold into Phase 1B.)

### Items recorded but not yet implemented

    1A.8   Authenticate hazard_analysis.py (currently trusts
           X-Tenant-Id header with no auth)
    1A.9   Rename /api/v1/dashboard/caan to /state
    1A.10  Public tenant-lookup (survey gateway): trim response,
           remove sandbox fallback, enforce tenant active status
           and survey window server-side
    1C.1b  Wire confidential_reporting_service.py; add separate
           reporter-contact store (schema change; Step 2)
    1D.7   Named-row exposure at state views — classification table
    1D.8   Escalation persistence (in-memory; Step 2)
    1D.9   Fabricated fallback values — table
    1D.10  Drill-down audit coverage (in-memory + unaudited
           state-risk/nhrc routes; Step 2)
    1D.11  VSR cross-tenant exposure — closed by 1A.7

### Test-suite state

    Full suite: ~1076 passed, 1 known environmental failure,
    79 deselected.
    Known failure: tests/test_hazard_enrichment.py::
        test_enrichment_adds_and_records_before_after (live-DB)
    Gate: known-failures-only. A new failure stops the item.

## Key Decisions Recorded

    G4    Keep Firebase Auth; layer SMS360X membership model.
    G10   Deterministic slug as tenant identity key; UUID derived
          via uuid5('tenant:'+slug) as storage key.
    G3    No dual-shape defect. CAAN SRM registers are distinct.
          Both tables stay. No migration.
    L4    STATE_SMD is canonical; CAAN_SMD is legacy. Code
          currently normalises inward to CAAN_SMD. Fix is Step 2.
    L6    Never expose slug to end users. Admin tooling excepted.
    L9    Both state and airline are tenants. Role distinguishes.
    L11   SAFETY_OFFICER to be retired to OFFICER; role encodes
          function, not department.

    Confidentiality model (corrected 2026-10-08):
        SDCPS sources: VSR (anonymous), MOR, audit, accident.
        State sees operator OUTCOME, not PROCESS.
        Drill-down is a purpose-bound, audited regulatory right.
        VSR reaches the state as aggregate intelligence only.

## Pending SME Decisions (before specific items run)

    Before 1A.10:
        - Is the ?tenant= sandbox fallback removed or env-gated?
        - Is the survey window enforced server-side today?
        - Is tenant active status enforced server-side today?

    Before 1A.9:
        - Confirm target path: /api/v1/dashboard/state (recommended)

    Before 1C.1b (Step 2):
        - Confirm reporter-contact store design

## Environment Notes

    Local repo:   D:\Projects\aviasafesms
    Branch:       step1-audit-readiness
    Remote:       git@github.com:sms360x/sms-aviasafesystems.git
                  (SSH key belongs to account "Ezondiza";
                   push denied — access pending)
    main:         local at 31db628; origin/main at 733fb77.
                  Branches have NOT diverged in code;
                  step1-audit-readiness is a linear descendant.

    Deploy pipelines:
      - Render auto-deploy watches main. Not triggered by branch
        pushes.
      - Firebase Hosting GitHub Actions watches main. Not triggered
        by branch pushes.

## When Work Resumes

    First action: confirm state.
        git status              # should be clean
        git log --oneline -5    # expect the handoff commit at HEAD
        git branch --show-current  # step1-audit-readiness

    Then pass the 1A.5 instruction to Opencode. 1A.5 is token
    revocation — verify + regression test, same shape as 1A.2/1A.3.

    After 1A.5, 1A.6, and 1A.8, Phase 1A closes. Phase 1B begins:
    RLS gaps, module-gate residuals, barrier_register column
    addition.

## Files That Exist Where

    Authoritative Step 0 documents:  docs/step0/
    Step 1 plan and evidence:        docs/step1/
    Archived (historical):           _archive/historical/
    Archive index:                   _archive/INDEX.md
    Step 1 work plan:                docs/step1/Step1_Work_Plan.md

## What the SME Knows That Is Not in Code Comments

    - Sita Air maintains a composite six-sheet Excel register
      system; Tara Air follows the CAAN manual directly. Both
      are CAAN-compliant (§2.2 permits other approaches).
    - Module 3 (PSOE Audit) is a shared capability: state uses
      it for oversight, airline uses it for self-assessment.
    - Survey links are distributed internally by web link or QR
      code; the survey window is set by the Tenant Admin.
    - The safety manager dashboard has an "Anon Rate" KPI that
      currently shows 0% because redaction is not wired (1C.1b).
    - The "Master CAP Register" title at can_cap/caps.html
      refers to the CAP hub, not to a tenant-wide master view.
      Department users see a scoped subset.
    - The demo environment has two tenants with auto-generated
      slugs (hzcons-5542802ee5, trirev-e770db8407) scheduled
      for removal.
    - production-setup.html is the live data-generation path;
      the backend seed scripts are retired.

## Stop Conditions Observed (honest record)

    - 1A.2: test_spi_auth.py was overwritten; detected via
      commit diff stat; restored from HEAD~1 in commit 420c99e.
      No tests lost. Lesson: validate-before-acting pattern
      adopted for 1A.3 onward.
    - 1A.4: two stale "not mapped" assertions surfaced as new
      test failures after the map change. Extended the commit
      to flip both assertions. No regressions.
    - 1A.4 sub-task 4.1: public tenant-lookup flagged against
      a stop condition. Opencode stopped and reported rather
      than acting. Correct behaviour; recorded as item 1A.10.

## End of Handoff
