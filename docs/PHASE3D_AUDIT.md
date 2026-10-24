# Phase 3D Full Audit Report (Read-Only)

## Section 1 — Dashboard data rendering (tenant user)
- `public/js/dashboard.js` fetches KPIs via `ApiClient.get('/api/v1/dashboard/recent?...')` and CAN/CAP trends via `/api/v1/cans/` and `/api/v1/cans/caps`. Endpoints exist in `backend/app/routes/dashboard.py` (`/recent`, `/hazards`, `/actions`) and `can_cap.py` (`/`, `/caps`). All backed by Supabase and tenant-scoped via RLS (`app.current_tenant`).
- With the seeded sita-air data, KPIs/charts should render real values. No "Loading..." stuck states found in the JS (all fetches have `.catch` fallbacks).
- Gap: No dedicated `/api/v1/dashboard/kpis` endpoint — KPIs are derived client-side from `/recent` + `/hazards` + `/cans`. If any of those 404 or return empty, KPIs show 0.

## Section 2 — Hazard & Risk Management (Module B)
- Pages: `public/hazard-analysis.html` (127 lines), `public/top-hazards.html` (288 lines), `public/hazards/detail.html`, `public/can_cap/caps.html`, `can_cap/cap_review.html`, `can_cap/cap_submit.html`.
- Data flow: hazards from `/api/v1/dashboard/hazards` (Supabase, tenant-scoped); CANs/CAPs from `/api/v1/cans/` and `/api/v1/cans/caps`.
- 5x5 Risk Matrix is display-only (rendered from hazard data). CANs/CAPs are linked to hazards via `hazard_id` foreign key.
- All endpoints exist. No obvious TODOs in the hazard pages.

## Section 3 — PSOE Audit (Module C)
- `public/admin/psoe-audit.html` (271 lines) calls `/api/v1/admin/psoe` (POST) and `/api/v1/admin/psoe/purge` (POST). Both exist in `backend/app/routes/psoe.py`.
- Purpose: PSOE (Public Safety Occurrence Evaluation) baseline assessment and surveillance audit. Supports create, list, and purge.
- No obvious incomplete states found in the HTML.

## Section 4 — User onboarding & password reset
- `public/login.html` has a "Forgot Password?" link (added in Phase 3C) that calls `alert('Please contact your system administrator...')` — no actual password reset flow exists.
- No backend endpoint for password reset (`/api/v1/auth/forgot-password` not found).
- Step 3 (`step3-manage.html`) has "Create User" but no "Reset Password" action.
- Firebase email/password reset is not configured in code — this is a manual SME-only step (Firebase Console → Authentication → Templates → Password Reset).
- Gap: Users who forget their password have no self-service recovery path. Admin can create users but cannot reset passwords.

## Section 5 — Mobile responsiveness and layout
- `public/css/shell.css` has `@media (max-width: 768px)` for nav wrapping (added in Phase 3C). KPI grids in `tenant-dashboard.css`, `caan-oversight.css`, `aviasdcps.css` use `white-space: nowrap` and `min-width` values that may overflow on mobile.
- `safety.html` and `hazard-analysis.html` use the shared shell (header collapses via shell.css). Individual KPI cards may still overflow.
- Gap: KPI grids need per-file mobile media queries to drop to 1 column.

## Section 6 — Known gaps and TODOs
Grep for `TODO`, `FIXME`, `XXX`, `HACK` in `public/` and `backend/` returned zero matches in the frontend. Backend has a few `TODO` comments in service files (not blocking).

Ranked gaps:
1. Important: No password reset flow (self-service or admin) — users locked out if they forget password.
2. Important: KPI grids on mobile may overflow (per-file CSS fixes needed).
3. Cosmetic: `console.error` in `dashboard.js` is expected error handling, not a bug.

No changes made.
