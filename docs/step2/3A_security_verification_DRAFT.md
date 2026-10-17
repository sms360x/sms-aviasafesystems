# Phase 3A — Security Verification (DRAFT, uncommitted)

DATE: 2026-10-15 | BRANCH: step2-governance | LOCAL HEAD: `b19682d`
SCOPE: C1, C2, H1, H2 only. Read-only audit + local existing-test runs.
No app code, DB data, prod config, secrets, or deployed services were touched.
No secret values are printed in this document.
Prior review statements were treated as hypotheses; only evidence below counts.

## 1. Commit identity (local vs deployed)

- Local code audited: `b19682d` (Phase 2C.6 close). Fixes under review:
  `a92e7f2` (C1+C2, 2026-09-18), `6383452` (H1+H2, auth gaps).
- Ancestry confirmed 2026-10-15: BOTH fixes are ancestors of local HEAD
  (`merge-base --is-ancestor` True/True). They are ALSO ancestors of `main`
  (True/True) — i.e. the fixes predate the `step2-governance`/`main` split,
  so any recent deploy built from `main` contains them in its lineage.
- Branch gap: `step2-governance` is 64 commits ahead of `main`; the Phase 2C
  RLS-enforcement work is NOT on `main`. (Relevant context, not a security gap.)
- Deployment config (read-only, `render.yaml`): single service
  `aviasafe-api`, `autoDeploy: true` (`:24`), `ENVIRONMENT=production`
  (`:30-31`), `BETA_ACCESS_KEY sync: false` (`:85-86`, dashboard-backed).
  The blueprint pins NO branch — the Render dashboard's connected branch
  governs what gets deployed. Frontend deploys on `main` pushes
  (`.github/workflows/deploy-hosting.yml`).
- Deployed RUNNING version: still **not verified** — only the Render
  dashboard's deployment list (commit SHA + date) can confirm it. See the
  owner checklist (§8).

## 2. Verdicts

| Finding | Classification | Basis |
|---|---|---|
| C1 unauth `/tenants/onboard` | VERIFIED FIXED (local) | `Depends(get_admin_user)` + caller-key `compare_digest` + 5/hr rate limit present; 36/36 local tests green incl. unauth→401/403, wrong-role→403, wrong-key→403 |
| C2 `BETA_ACCESS_KEY` bypass | PARTIALLY VERIFIED | Code fix verified + tests green, BUT prod secret rotation / `ENVIRONMENT` / boot-guard status is unverifiable from the repo, and the pre-fix value lives in git history |
| H1 unauth NHRC/SPI | VERIFIED FIXED (local) | All 17 endpoints declare `get_current_user`/`get_caan_user` + tenant gates; 29/29 local tests green |
| H2 regulator cross-tenant leak | VERIFIED FIXED (local) | All `/api/v1/regulator/*` gated by `get_caan_user` except one `get_current_user` route with explicit tenant-pin check; 19/19 local tests green |

Beta-ready is NOT declared by this task (out of scope by design).

## 3. Evidence matrix

### C1 — Unauthenticated `/tenants/onboard`
- Original risk: `POST /api/v1/tenants/onboard` had no auth dependency and
  self-supplied the configured key, so anyone could create tenant+admin+seed
  (`SECURITY_REVIEW.md:37-42`, pre-fix `onboarding_service.py:71`
  satisfying `tenant_registration.py:338`).
- Current handler: `backend/app/api/v1/endpoints/tenants.py:50-75` —
  `Depends(get_admin_user)` (`:55`), `@rate_limit("register_tenant")`
  (`:51`, 5/hr/IP per `middleware/rate_limit.py:51,74,220`),
  `beta_access_key` forwarded caller-supplied (`:47,73`).
- Auth chain: `middleware/auth.py:195-203` (`get_admin_user` → 403 unless
  `SUPER_ADMIN`); `get_current_user` `:129-170` (401 invalid token, 403
  suspended). No second/legacy onboard route exists
  (`app/routes/tenants.py` has none; mount `api/v1/router.py:8,17` +
  `main.py:298`).
- Service gate: `services/onboarding_service.py:67-75`
  (`compare_digest`, never self-supplies); downstream
  `services/tenant_registration.py:318-334` (prod strict).
- Fix commit: `a92e7f2` (diff confirms auth+key+rate-limit+tests).
- Tests run (local, 2026-10-15): `test_onboard_auth.py` +
  `test_self_service_registration.py` → **36 passed**. Cases covered:
  no-auth→401/403, wrong-key→403, `AIRLINE_ADMIN`+valid-key→403,
  `SUPER_ADMIN`+valid-key→201 with key-forwarding asserted,
  prod-boot-guard `RuntimeError` when key unset.
- Uncertainty left: deployed SHA/prod behavior unprobed (constraint §3).

### C2 — `BETA_ACCESS_KEY` bypass
- Original risk: hardcoded default (`config.py:196`, since removed) + no
  `render.yaml` entry → gate bypassable.
- Current: `core/config.py:242-251` (`Optional[str] = None`, no fallback;
  rotation note re 2026-09-18 exposure); `render.yaml:82-86` (`sync: false`,
  dashboard-backed); `main.py:46-58` refuses production boot when unset
  (called in `lifespan:63`).
- Fail-closed (production): boot guard + `tenant_registration.py:324-334`
  strict compare + `onboarding_service.py:67-75` pre-check. Fail-open ONLY in
  beta/staging/development by design (`tenant_registration.py:320-323`,
  blank-key allowed, sandbox-tagged `:357-361`).
- Fix commit: `a92e7f2` (same as C1; stat covers config/main/service/render/tests).
- Tests run: same 36 (wrong-key→403, beta-blank→200 sandbox, prod
  blank/wrong→403, correct→200, boot-guard unit tests).
- Uncertainty left (drives PARTIALLY VERIFIED): (a) whether the exposed
  pre-fix value was rotated in the Render dashboard — unknowable from repo,
  must be assumed compromised until ops confirms; (b) prod `ENVIRONMENT`
  value (a non-production value would silently degrade the gate to lenient);
  (c) deployed boot-guard status unprobed.

### H1 — Unauthenticated NHRC/SPI
- Original risk: tenant/state NHRC + SPI reads and SPI target writes with no
  `Depends` (pre-fix signatures took bare `tenant_id`).
- Current: 5/5 `api/v1/nhrc.py:21-70` + 12/12 `api/v1/spi.py:41-240` endpoints
  declare auth — tenant reads/writes `get_current_user` +
  `require_tenant_access` (`spi.py:23-38`, shared), state reads/writes
  `get_caan_user` (`auth.py:184-192`, roles `CAAN_SMD/STATE_SMD/SUPER_ADMIN`
  per `config.py:156`). Mount `api/v1/router.py:18-19`.
- Fix commit: `6383452` (diff shows bare→gated signatures).
- Tests run (local): `test_spi_auth.py` + `test_nhrc_auth.py` → **29 passed**
  (unauth reject, own-tenant allow, cross-tenant 403, CAAN-only state,
  invalid-token, module-map pins).
- Uncertainty left: deployed SHA unprobed; tests use auth overrides/mocks,
  not live tokens (see §4 M1).

### H2 — Regulator dashboard leak
- Original risk: all `/api/v1/regulator/*` on `get_current_user` with
  caller-controlled `tenant_ids` → any airline user reads other operators.
- Current (`app/routes/regulator_dashboard.py`, mounted `main.py:293`):
  every endpoint gated by `get_caan_user` EXCEPT
  `GET /share/benchmark/{tenant_id}` (`:50-70`), which uses
  `get_current_user` + explicit pin (`:59-62`: non-cross-tenant roles 403
  unless `user.tenant_id == tenant_id`). Reads audited via
  `caan_audit.log_caan_read`.
- Fix commit: `6383452` (+ `test_regulator_auth.py`, 175 lines).
- Tests run (local): `test_regulator_auth.py` +
  `test_regulator_share_api.py` + `test_regulator_dashboard.py` →
  **19 passed** (airline→403+CAAN message, CAAN/SUPER_ADMIN→200,
  operator air1:200/air2:403, unauth 401/403).
- Residual (minor, not the original leak): the benchmark comparison pool
  `tids` remains caller-controlled (`:63-65`) — affects baseline choice, not
  row access. See §4 M3.

## 4. Missing regression tests (none block the verdicts; all are hardening)

- M1 (all four): no live-token negative tests over real HTTP for
  onboard/spi/nhrc/regulator (cf. RLS smoke T25–T27 pattern). Existing suites
  mock/override auth layers, so a wiring regression between the real
  dependency and the route would not be caught.
- M2 (C1): no rate-limit test for `/onboard` (5/hr/IP) — limit is declared
  but unpinned by any test.
- M3 (H2): no test pinning that the `/share/benchmark` comparison pool cannot
  widen row access (documents the §3 residual).
- M4 (C2): no test for `ENVIRONMENT`-misconfiguration degradation (non-prod
  value in a prod deploy silently leniens the gate).

## 5. Remediation plan (prioritized)

- P0 (ops, before any beta): confirm Render-dashboard rotation of the
  pre-2026-09-18 exposed key; confirm prod `ENVIRONMENT=production`;
  confirm running deploy includes `a92e7f2`+`6383452` (safe version probe or
  deploy-SHA check). Owner: platform/SME.
- P1: non-disruptive deployed-behavior probe for the four areas (auth-only
  negative cases: no-auth → 401/403; wrong-tenant → 403). No writes, no real
  data access.
- P2: add M1 live-token regression tests (extend the RLS smoke pattern).
- P3: add M2/M3/M4 unit tests (rate limit, benchmark pool, env-degradation).
- P4: apply §6 doc updates, close this audit.

## 6. Proposed `SECURITY_REVIEW.md` updates (DRAFT ONLY — not applied)

```diff
- C1 (L37-40): "POST /api/v1/tenants/onboard ... no authentication dependency"
+ C1: FIXED in code (`a92e7f2`): `Depends(get_admin_user)` + caller-key
+ `compare_digest` + 5/hr rate limit (`endpoints/tenants.py:50-55`,
+ `onboarding_service.py:67-75`). Verified local 2026-10-15 (36 tests green:
+ `test_onboard_auth.py`, `test_self_service_registration.py`). Deploy
+ confirmation pending (Phase 3A P0/P1).
- C2 (L41): 'BETA_ACCESS_KEY="AVIA…26" ... not set in render.yaml'
+ C2: FIXED in code (`a92e7f2`): `Optional[str] = None`, no fallback
+ (`config.py:242-251`); `render.yaml:82-86 sync:false`; production boot guard
+ (`main.py:46-58`). PARTIALLY VERIFIED: prod rotation of the exposed
+ pre-fix value + ENVIRONMENT value unconfirmed — treat old value as
+ compromised until P0 done.
- H1 (L48-50): "no auth ... IDOR read + unauth target write"
+ H1: FIXED in code (`6383452`): all 17 nhrc/spi endpoints gated
+ (`nhrc.py`, `spi.py` + `require_tenant_access`). Verified local 2026-10-15
+ (29 tests green: `test_spi_auth.py`, `test_nhrc_auth.py`). Deploy
+ confirmation pending.
- H2 (L52-54): "get_current_user not get_caan_user, caller-controlled tenant_ids"
+ H2: FIXED in code (`6383452`): all `/api/v1/regulator/*` on `get_caan_user`
+ except `/share/benchmark/{tenant_id}` (explicit tenant pin,
+ `regulator_dashboard.py:59-62`). Verified local 2026-10-15 (19 tests
+ green). Minor residual: benchmark comparison pool caller-controlled
+ (baseline choice only). Deploy confirmation pending.
```

## 7. Test evidence (local runs, 2026-10-15, backend/, `-p no:cacheprovider`)

- `test_onboard_auth.py + test_self_service_registration.py`: 36 passed (5.8 s)
- `test_spi_auth.py + test_nhrc_auth.py`: 29 passed (3.1 s)
- `test_regulator_auth.py + test_regulator_share_api.py + test_regulator_dashboard.py`: 19 passed (20.8 s)
- Total: 84 passed, 0 failed. No prod contact; no data modified.

## 8. Render operational checklist (for the product owner — no code needed)

Do these in order, in the Render dashboard (Services → aviasafe-api).
Write down what you see; never paste secrets or user data anywhere.

**Step 1 — Which code is running (owner does this; 5 min).**
1. Open Services → aviasafe-api → Events (or Deploys). Find the newest entry
   marked Live / Successful.
2. Write down its date/time and its commit code (the short mix of letters and
   numbers, e.g. `b19682d`). This is the running version.
3. Check which branch it was built from (shown next to the deploy). Write it down.
4. Send the commit code + branch + date to the tech team.

**Step 2 — Do the security fixes reach the running version (tech team checks
what you send; you do nothing here).**
- The fixes went into the code on 2026-09-18. Any deploy built after that date
  from a branch containing them is covered. Both fixes are in the shared
  history of `main` AND `step2-governance`, so a recent deploy of either
  branch contains them — but ONLY the SHA you record in Step 1 proves it.
- Rule: running SHA must be dated after 2026-09-18 AND its branch history must
  include the fixes. If the running deploy is older, redeploy (a normal dashboard
  "Manual Deploy", no settings change) and re-record the SHA.

**Step 3 — Replace the beta access key (owner does this; 10 min).**
Why: an old key value was once visible in the project history, so treat it as
public. Replacing it is routine hygiene, like changing a lock.
1. In the dashboard go to Services → aviasafe-api → Environment. Find the entry
   named `BETA_ACCESS_KEY`. Do NOT open, copy, or share its current value.
2. Click Edit on that entry. Type a NEW long random value (use a password
   manager's generator, 32+ characters). Save.
3. The service will restart/redeploy by itself. Wait until it shows Live again.
4. Confirm it stays Live for a few minutes (the app refuses to start if the key
   were ever blank — staying Live proves the new key is active).
5. Tell the tech team "key rotated, service Live". Never send the key itself
   to anyone or paste it into chat, email, or documents.

**Step 4 — Confirm the production setting (owner does this; 2 min).**
1. In the same Environment page, find the entry named `ENVIRONMENT`.
2. It must read exactly `production`. If it reads anything else, STOP and tell
   the tech team before changing anything (the wrong value silently weakens
   the registration gate).
3. Record "ENVIRONMENT = production confirmed" with today's date.

**Step 5 — Record results (owner does this).**
- Write down: deploy SHA + branch + date; "key rotated" + date; "ENVIRONMENT
  confirmed" + date. Keep this note with the project records.
- What NOT to record: the key value itself, any tokens, any user/tenant data.

**Automatable later (not owner work):** deploy-SHA-vs-fix check (CI job),
key-presence boot check (already in code), periodic re-probe of the four
negative auth cases.
