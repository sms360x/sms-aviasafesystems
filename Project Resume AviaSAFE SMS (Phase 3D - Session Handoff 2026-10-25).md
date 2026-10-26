# Project Resume: AviaSAFE SMS (Phase 3D — Session Handoff)

**Session Date:** 2026-10-25
**Session Status:** Master Logsheet backend VERIFIED WORKING end-to-end. Frontend wizard and promote endpoint are next.
**Commit state:** `main` branch, working tree clean.

---

## ✅ Master Logsheet Backend — VERIFIED WORKING

### What works
- `POST /api/v1/imports/master-logsheet` — accepts .xlsx/.csv, parses via pandas, stages rows, routes by classification checkbox
- `GET /api/v1/imports/{batch_id}/preview` — returns staged rows filtered by tenant
- `POST /api/v1/imports/{batch_id}/promote` — **stub** (marks rows as promoted, does not insert into target tables yet)
- `DELETE /api/v1/imports/{batch_id}` — discards batch

### Smoke test result (verified 2026-10-25)
- Logged in as `safety@sitaair.com.np` (TENANT_ADMIN, sita-air)
- Uploaded 3-row CSV with one occurrence, one hazard, one diversion
- Result: `200 OK, staged_rows: 3, unmapped_columns: []`
- Routing verified: occurrence → `occurrences`, hazard → `hazards`, diversion → `flight_diversions`

### Verified architecture
- Auth: `get_safety_manager` (requires TENANT_ADMIN or STATE_SMD role)
- Column mapping: `auto_map_columns` in `import_service.py` matches aliases to canonical fields
- Routing: `route_row` in `import_service.py` maps classification checkboxes to destination tables
- Staging: `master_logsheet_staging` table in Supabase (11 columns, migration `20261027000000`)
- Schema: `MasterLogsheetStaging` ORM model in `db_models.py`

### Known gaps / follow-ups
1. **`promote` endpoint is a stub** — currently marks `validation_status='promoted'` but does NOT insert into `occurrences`/`hazards`/`flight_diversions`. Real implementation needs to be written. **This is the #1 remaining backend task.**
2. **`promote` bug** — updates by `batch_id` only (no `tenant_id` filter). Should be fixed when implementing real promote logic.
3. **`unmapped_columns` returned but no UI** — when a user's file has columns that don't match any alias, they're reported but not actionable. Frontend wizard needs to show a mapping UI.
4. **No frontend wizard** — endpoint only works via console/curl right now.
5. **DEPT_ADMIN users get 403** — `tacn2080@gmail.com` (DEPT_ADMIN) is rejected. Only TENANT_ADMIN and STATE_SMD can upload. This may be intentional, or may need relaxing to allow Department Managers to upload their department's data.

---

## Phase 3C — Complete ✅
- Domain migration to `sms360x.com` (old `sms.aviasafesystems.com` retired)
- Split-screen login with SMS360X branding
- Custom logo, custom branded modal
- Password reset (admin + self-service)
- Root domain routing works (no per-tenant subdomain required)

## Phase 3D — Foundation Complete ✅
- `public/css/executive-ui.css` (211 lines) — design system
- `public/js/executive-shell.js` (99 lines) — sidebar + topbar
- **Not yet used by any dashboard** — all 5 dashboards still on old layout

---

## CAAN SRM Compliance — Audited (Not Yet Addressed)

Platform is ~85% aligned with CAAN SRM Procedure Manual (Jan 2026).

**Implemented (in `srm_engine.py`):**
- ✅ 7 Impact Area weighted severity
- ✅ Barrier Strength Value (BSV)
- ✅ CBSV→Likelihood (5 severity tables)
- ✅ 5×5 Risk Matrix with tolerance zones
- ✅ Bow-Tie structure
- ✅ Risk Register + Barrier Register schemas

**Missing (deferred per Path B):**
- ⚠️ ERC Matrix (4×4 → H/M/L priority) — Critical
- ⚠️ 4 hazard fields (area_operation_equipment, threat, unsafe_top_event, hazard_taxonomy enum) — Major
- ⚠️ Risk acceptance authority mapping — Major

---

## Next Session Priorities

**Priority 1 — Build the frontend import wizard:**
- `/dashboard/historical-import.html` (new page, uses executive shell)
- File upload + preview table
- Column mapping UI for `unmapped_columns`
- Approve button → calls `promote`
- Success summary

**Priority 2 — Implement real `promote` endpoint:**
- Fetch staged rows where `validation_status='pending'` AND `promoted_at IS NULL`
- For each row, insert into `occurrences` / `hazards` / `flight_diversions` based on `destination_tables`
- Handle cross-table linking (same event in multiple tables shares a `source_row_id`)
- Compute derived fields (priority via ERC matrix — but ERC not yet built, so skip for now)
- Update staging rows to `validation_status='promoted'`, `promoted_at=NOW()`

**Priority 3 — CAAN compliance:**
- ERC Matrix (Critical for CAAN audit)
- 4 hazard field extensions
- Risk acceptance authority mapping

**Priority 4 — Dashboard migrations (5 dashboards, in order):**
1. `spi-dashboard.html` (7 DOM IDs, standalone) — needs re-do after earlier rollback
2. `my-tasks.html` (9 DOM IDs, Department Manager)
3. `production-setup.html` (~10 DOM IDs, different auth pattern)
4. `safety.html` (34 DOM IDs, high coupling)
5. `ae-dashboard.html` (38 inline DOM IDs, highest coupling)

Migration approach: complete redesign using `.exec-*` classes. New HTML, new JS. Preserve API calls and business logic, not DOM IDs. Build `ExecutiveModal` component first for hybrid drill-down (modal for KPIs/charts, dedicated pages for tables).

---

## Test Credentials
- **SUPER_ADMIN:** `ezondiza.dhf@gmail.com` (no tenant_id — cannot upload, only manage)
- **TENANT_ADMIN (sita-air):** `safety@sitaair.com.np` (password in your records — was working 2026-10-25)
- **DEPT_ADMIN (saurya-airlines):** `tacn2080@gmail.com` / `4yOq4!cI$osEwjYS`
- **Tenants in system:** `caan`, `sita-air`, `saurya-airlines`, `air-dynasty`
- **Seeded data:** only `sita-air` has demo data

## Test Files
- **Sita Air Master Logsheet:** `Master Logsheet-2026.xlsx` (on your local machine) — not yet tested, only synthetic CSV was tested. Testing the real file is a Priority 1 validation.

---

## Architecture Facts
- **Backend:** Render (`aviasafe-unified-platform.onrender.com`) — auto-deploys from `main`
- **Frontend:** Firebase Hosting (`aerosafety-sms-prod` site) — auto-deploys via GitHub Actions on push to `main`
- **Database:** Supabase (RLS enforced, SUPER_ADMIN bypass via `app.current_role`)
- **Repo:** single `main` branch, `DHFactors/sms-aviasafesystems`
- **Latest commit:** check `git log --oneline -1` — should be the import commit `3a1b3c2` or later

## Working Rules
- Never edit code directly — all code written by OpenCode
- Verify before fix — read-only audits first
- Commit only after SME confirms — never push without "push approved"
- One commit = one logical change
- Markdown code blocks for OpenCode dispatches
- OpenCode writes code, SME reviews, commit after confirmation

## What to Avoid
- Don't try to preserve old DOM IDs during dashboard migration — complete redesign is the goal
- Don't move files from `public/` root to `public/dashboard/` (documented decision, cost > benefit)
- Don't touch `aviasdcps*` files (dead module)
- Don't rebuild srm_engine.py — it already works
- Don't test import as SUPER_ADMIN — requires TENANT_ADMIN or STATE_SMD
- Don't forget to apply migrations (`supabase db push`) after pushing code that adds schema

---

## How to Resume Next Session

Paste this resume and say:

> **"Continue Phase 3D — build the frontend import wizard, then the real promote endpoint."**

The AI should:
1. Acknowledge the Master Logsheet backend is verified working
2. Run a read-only audit of the current `promote` stub and `imports.py` before writing real promote logic
3. Then write the dispatch to build `/dashboard/historical-import.html` (frontend wizard)
4. Test with Sita Air's real Master Logsheet
5. Then implement the real promote endpoint

---

## Session Accomplishments (2026-10-25)

**Verified:**
- Master Logsheet backend working end-to-end (smoke test passed: 3 rows correctly routed)

**Deployed:**
- `POST /api/v1/imports/master-logsheet` (parses Excel/CSV, stages, routes by classification)
- `master_logsheet_staging` migration applied to production Supabase

**Committed this session:**
- `3a1b3c2` — feat(import): add Master Logsheet backend with routing (Phase 1)

**Not addressed (deferred to next session):**
- Frontend wizard
- Real promote endpoint (current is a stub)
- `unmapped_columns` UI
- Dashboard migrations
- CAAN compliance (ERC matrix, hazard extensions, authority mapping)
