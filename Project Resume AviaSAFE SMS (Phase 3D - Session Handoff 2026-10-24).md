# Project Resume: AviaSAFE SMS (Phase 3D — Session Handoff)

**Session Date:** 2026-10-24
**Session Status:** Phase 3D foundation complete. Master Logsheet backend built, committed, deployed. Not yet tested end-to-end.
**Next Session Goal:** Test Master Logsheet import + build frontend wizard.

---

## Repository State
- **Branch:** `main` only
- **Latest commit:** `feat(import): add Master Logsheet backend with routing (Phase 1)` (or latest)
- **Working tree:** clean
- **Remotes:** `DHFactors/sms-aviasafesystems` (also mirrored at `sms360x/sms-aviasafesystems`)

## Deployments
- **Backend:** Render — `aviasafe-unified-platform.onrender.com` — auto-deploys from `main`
- **Frontend:** Firebase Hosting (`aerosafety-sms-prod` site) — auto-deploys via GitHub Actions on push to `main`
- **Database:** Supabase (RLS enforced; SUPER_ADMIN bypass via `app.current_role`)

## Domains
- `sms360x.com` — landing + login + dashboards
- `sita.sms360x.com`, `tara.sms360x.com`, etc. — tenant subdomains work but not required (root domain routing handles tenant resolution)
- `sms.aviasafesystems.com` — **RETIRED**

---

## Phase 3C — Complete ✅
- Domain migration to `sms360x.com`
- Split-screen login with SMS360X branding
- Custom logo, lowercase `sms360x`
- Password reset (admin-triggered + self-service both working)
- Custom branded modal on login page (replaced native alerts)
- Root domain routing verified (no per-tenant subdomain required for login)

## Phase 3D — Foundation Complete ✅
- `public/css/executive-ui.css` (224 lines) — design system foundation
- `public/js/executive-shell.js` (110 lines) — sidebar + topbar component
- Mobile KPI grid fixes on live dashboards
- File convention documented in `docs/DASHBOARD_FILE_CONVENTION.md`
- Dead `aviasdcps` rewrites removed from `firebase.json`
- Executive layout foundation committed but not yet used by any dashboard

---

## Master Logsheet Import — Built, Not Yet Tested ⚠️

### What was built this session
Backend endpoint for uploading airline Master Logsheets (xlsx/csv), auto-mapping columns, routing rows to correct tables based on classification checkboxes, and staging for preview/approval before promotion.

### Files created/modified
- `backend/requirements.txt` — added `pandas>=2.0.0`
- `backend/app/db/db_models.py` — added `MasterLogsheetStaging` model
- `backend/app/services/import_service.py` — column mapping + row routing
- `backend/app/routes/imports.py` — 4 endpoints
- `backend/app/main.py` — registered `imports.router`
- `supabase/migrations/20261027000000_master_logsheet_staging.sql` — staging table

### Endpoints
- `POST /api/v1/imports/master-logsheet` — accepts file, stages rows, returns `batch_id` + `unmapped_columns` + preview
- `GET /api/v1/imports/{batch_id}/preview` — returns staged rows for review
- `POST /api/v1/imports/{batch_id}/promote` — **stub** — marks rows as promoted, does NOT yet insert into `occurrences`/`hazards`/`flight_diversions` (that's a follow-up dispatch)
- `DELETE /api/v1/imports/{batch_id}` — discards the batch

### Routing logic (in `import_service.py`)
Based on classification checkboxes in the Master Logsheet:
- **Occurrence** → routes to `occurrences`
- **Hazard** → routes to `hazards`
- **Safety Deficiency** → routes to `hazards` (same table, will differentiate later)
- **Diversion** → routes to `flight_diversions`
- Multiple checkboxes = row inserted into multiple tables

### Known gaps / follow-ups
1. **`promote` endpoint is a stub** — it marks rows but doesn't insert into production tables. Next dispatch needs to:
   - Fetch staged rows with `promoted_at IS NULL`
   - For each destination table in `destination_tables`, insert a row
   - Handle cross-table linking (e.g., an occurrence that's also a hazard shares a `source_row_id`)
2. **`unmapped_columns`** — returned in response, needs frontend UI to let user map them
3. **Not tested** — no smoke test run yet.

---

## CAAN SRM Compliance — Audited, Not Yet Addressed

### What's already implemented (in `srm_engine.py`)
- ✅ 7 Impact Area weighted severity (Pax ×4, Employee ×3, Product ×2, others ×1)
- ✅ Barrier Strength Value (BSV) — 7 quality elements weighted
- ✅ CBSV→Likelihood — all 5 severity-specific tables
- ✅ 5×5 Risk Matrix with tolerability zones
- ✅ Bow-Tie structure (analyses, threats, consequences, controls)
- ✅ Risk Register schema (current + resultant risk, ALARP, acceptance)
- ✅ Barrier Register schema (all 7 BSV elements)

### What's missing (deferred — Path B: ship import first)
1. **ERC Matrix** (Critical) — 4×4 event risk classification → H/M/L initial priority
2. **4 hazard fields** (Major) — `area_operation_equipment`, `threat`, `unsafe_top_event`, `hazard_taxonomy` enum
3. **Risk acceptance authority mapping** (Major) — 5-level authority table

**Estimated effort:** ~1 session to reach full CAAN compliance after import ships.

---

## Dashboard Migration — Audited, Not Yet Started

### Five dashboards to migrate (order confirmed by coupling audit)
1. `spi-dashboard.html` (7 DOM IDs, standalone, low coupling)
2. `my-tasks.html` — 9 DOM IDs, Department Manager dashboard
3. `production-setup.html` — ~10 DOM IDs, different auth pattern
4. `safety.html` — 34 DOM IDs, 18 script tags — high coupling
5. `ae-dashboard.html` — 38 inline DOM IDs, inline auth — highest coupling

### Migration approach (decided this session)
**Complete redesign, not shell swap.**
- New HTML using `.exec-*` classes (from `executive-ui.css`)
- New JS renders into new structure
- Preserve API endpoints, data shapes, business logic
- Do NOT preserve DOM IDs
- Hybrid drill-down UX: KPI cards → modal, charts → modal, tables → dedicated pages

### `ExecutiveModal` component (not yet built)
Needed for the hybrid UX. New file `public/js/executive-modal.js`.

---

## Test Credentials
- **SUPER_ADMIN:** `ezondiza.dhf@gmail.com`
- **Department Admin (saurya-airlines):** `tacn2080@gmail.com` — password was reset to `4yOq4!cI$osEwjYS`
- **TENANT_ADMIN (sita-air):** `safety@sitaair.com.np`
- **Tenants in system:** `caan`, `sita-air`, `saurya-airlines`, `air-dynasty`
- **Seeded data:** `sita-air` has demo data; others are empty after the earlier purge

---

## Build Sequence (Path B — agreed this session)

1. **Test Master Logsheet backend** ← NEXT SESSION
2. **Build Master Logsheet frontend wizard** — `/dashboard/historical-import.html`
3. **Implement `promote` endpoint** (insert into `occurrences`, `hazards`, `flight_diversions`)
4. **Test with Sita Air data** — confirm dashboard populates
5. **ERC Matrix** — CAAN compliance Phase 2
6. **Hazard field extensions** — 4 columns
7. **Risk acceptance authority mapping** — lookup + UI
8. **Dashboard migrations** (in order above) + build `ExecutiveModal`
9. **Barrier + Risk Register imports** (CAAN-format for regulators, later)

---

## Working Rules (established this session)
- **Never edit code directly.** All code written by OpenCode.
- **Verify before fix.** Read-only audits first.
- **Commit only after SME confirms.** Never push without "push approved."
- **One commit = one logical change.**
- **Markdown code blocks for OpenCode dispatches.** No raw shell scripts.
- **OpenCode writes code; SME reviews; commit after confirmation.**

---

## What to Avoid
- Don't migrate dashboards before the import works (empty dashboards = no visible value to tenants)
- Don't move files from `public/` root to `public/dashboard/` (documented decision — cost > benefit)
- Don't touch `aviasdcps*` files (dead module, cleanup deferred)
- Don't rebuild things that already work in `srm_engine.py`
- Don't try to preserve DOM IDs during dashboard migration — complete redesign is the goal

---

## How to Resume Next Session

Paste this resume and say:

> **"Continue Phase 3D — test Master Logsheet backend, then build frontend wizard."**

The AI should:
1. Acknowledge state (backend built, deployed, untested)
2. Guide the smoke test with Sita Air's `Master Logsheet-2026.xlsx`
3. Based on test result: fix + retest, OR proceed to frontend wizard dispatch
4. Then build the `promote` endpoint (the stub → real insert)

---

## Session Accomplishments Summary

**Shipped:**
- Phase 3C fully closed (domain migration, branding, password reset)
- Executive UI foundation (design system + shell component)
- Master Logsheet backend (parser, column mapping, routing, staging)

**Analyzed:**
- CAAN SRM compliance gap (85% aligned, 3 specific gaps identified)
- Dashboard migration order (5 dashboards, coupling levels mapped)
- File consolidation decision (rejected — cost > benefit, documented convention)

**Deferred to next session:**
- Master Logsheet smoke test
- Frontend import wizard
- `promote` endpoint implementation
- ERC matrix + hazard extensions (CAAN compliance)
- Dashboard migrations (5 dashboards)

**Commits this session:** ~8-10 (password reset, modal, foundation, KPI fixes, cleanup, import backend)

---

## Break time

Save the file. Close the laptop. You've earned it.

What you shipped today:
- **Phase 3C completely closed** — the whole domain migration that was blocking everything
- **Executive UI foundation** — the design system that will power the entire future of the product
- **Master Logsheet backend** — the import that makes tenant onboarding actually possible
- **CAAN compliance mapped** — you now know exactly what's missing (3 items) and how much work it is (~1 session)
- **Dashboard migration planned** — the path forward is clear

That's a full day of high-leverage work, not busywork. Every commit today moved the product closer to being sellable.

When you come back, paste the resume and we pick up at the smoke test. Sleep well. 🛫
