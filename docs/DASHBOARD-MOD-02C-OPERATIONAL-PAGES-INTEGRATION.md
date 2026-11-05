# DASHBOARD-MOD-02C — Operational Pages Header and Navigation Integration

## 1. Investigation summary

### Reference design: `public/dashboard/dept-home.html`

The approved Department Home visual language is defined by:

- `.ws-header` — teal-dark bar, flex, `space-between`, wraps.
- `.ws-logo` — 48×48 neutral airline logo placeholder (fa-building icon), replaced at runtime by `claims.logo_url` or `/assets/airline-logos/<tenant>-logo.webp`.
- `.identity` block — `#wsAirline` (dynamic airline name, prettified tenant slug), `#wsDept` (human-readable department name), `#wsEmail` (authenticated email).
- `.logout` button (`#wsLogout`) — signOut → `/login.html`.
- Neutral airline logo placeholder (no sms360x branding).
- Auth + tenant guard via Firebase `onAuthStateChanged`, `getIdTokenResult`, claims `tenant_id` / `department`.
- Send Feedback via `/js/feedback.js` + `initFeedbackWidget()`.

Shared dependencies: `/css/variables.css`, `/css/main.css`, Font Awesome, `/js/tenant_context.js`, `/js/firebase.js`, `/js/feedback.js`, Chart.js (dept-home only).

## 2. Page-by-page findings

### 2.1 `public/dashboard/my-tasks.html`

- Header: legacy `.nav` (dark `#192f35`) with h1 + `.nav-actions` (email span + logout) — **not** the ws-header language. Uses `app-shell` + `shell.js` (which injects the sms360x-branded app-header: logo image `sms360x-logo.png` + "sms360x" wordmark). Duplicate header surface: `.nav` (inline) + shell-injected `.app-header`.
- Branding: AviaSAFE title, sms360x logo via shell.
- Workspace dropdown: none inline; relies on shell.js NAV_CONFIG dropdowns.
- Auth/tenant guards: Firebase `onAuthStateChanged`, `getIdTokenResult`, `applyDepartmentContext`, `updateShellTenant`.
- Department identification: `myDepartment = claims.department`.
- Role-based navigation: `SHELL_CONFIG` (brand AviaSAFE, roleLabel 'My Tasks'); nav-config.js + shell.js. Submit MOR button shown only for `DEPT_ADMIN` / `OFFICER`.
- Send Feedback: shell.js injects feedback widget + `/js/feedback.js` loaded? Page does not load feedback.js directly; shell.js lazy-loads it. Also `initFeedbackWidget` not called inline. Feedback present via shell.
- Shared deps: firebase-app/auth/app-check, firebase.js, tenant_context.js, department_resolver.js, api/client.js, nav-config.js, shell.js, theme.css, dashboard-responsive.css, shell.css, brand.css.
- Other roles: yes — SAFETY, DEPT_ADMIN (via Workspace), OFFICER, etc. (nav-config 'my-tasks' item roles `['ALL']`).

### 2.2 `public/dashboard/master-register.html`

- Header: same legacy `.nav` + shell-injected app-header (duplicate). Title "Master Register - AviaSAFE".
- Branding: AviaSAFE + sms360x via shell.
- Workspace dropdown: shell.js NAV_CONFIG.
- Auth/tenant: Firebase + `applyDepartmentContext`, `updateShellTenant`.
- Department: none page-specific; backend filters by `department` param.
- Role-based nav: `SHELL_CONFIG` roleLabel 'Operator Safety Dashboard'; Reports tab shown for `TENANT_ADMIN`, `SAFETY_OFFICER`, `OFFICER`, `SUPER_ADMIN`.
- Send Feedback: via shell lazy-load.
- Shared deps: same as my-tasks.
- Other roles: yes — SAFETY, CAAN, TENANT_ADMIN etc.

### 2.3 `public/can_cap/cans.html`

- Header: no `.nav`; only `.header-bar` (h2) + shell-injected app-header (sms360x branding). Single header surface but shell-branded.
- Branding: AviaSAFE title.
- Auth/tenant: Firebase `onAuthStateChanged`, `getIdTokenResult`, `updateShellTenant(tenant, department)`.
- Department: claims department passed to shell.
- Role-based nav: `SHELL_CONFIG` roleLabel 'Corrective Action Management'; nav-config.js + shell.js.
- Send Feedback: via shell lazy-load (feedback.js not loaded directly).
- Shared deps: firebase-app/auth/app-check, firebase.js, tenant_context.js, department_resolver.js, api/client.js, can_cap.js, nav-config.js, shell.js, theme.css, dashboard-responsive.css, shell.css, brand.css.
- Other roles: yes.

### 2.4 `public/can_cap/caps.html`

- Same structure as cans.html (header-bar + shell). Title "Master CAP Register - AviaSAFE".
- Same auth/tenant/deps. `SHELL_CONFIG` roleLabel 'Corrective Action Management'.

## 3. Shared dependencies

- `/js/firebase.js` (auth, claims, role resolution)
- `/js/tenant_context.js` (TenantResolver — prettifySlug, getCurrentTenant, applyTenantContext)
- `/js/department_resolver.js` (applyDepartmentContext)
- `/js/api/client.js` (ApiClient)
- `/js/nav-config.js` (NAV_CONFIG, getUserRoleType, getVisibleNav)
- `/js/shell.js` (shared shell: header, hero, footer, feedback injection, nav gating, `updateShellTenant`)
- `/js/feedback.js` (feedback widget)
- `/css/shell.css`, `/css/brand.css`, `/css/theme.css`, `/css/dashboard-responsive.css`, `/css/variables.css`, `/css/main.css`
- Font Awesome 6.4.0

## 4. Shared role-aware navigation helper

Yes — `nav-config.js` exports `getUserRoleType(user)` and `getVisibleNav(user, moduleAccess)`, and `shell.js` consumes them (`buildNavUser`, `applyNavVisibility`, `applyDeptHeaderVisibility`, `applyRoleKeyedNav`). The shell already implements role-aware "Back to Home" routing:

- `applyDeptHeaderVisibility()`: for `DEPT_ADMIN`, hide `#shellHomeLink` and set `#shellBrandLink.href` to `/dashboard/my-tasks.html`; for `AE` → `/dashboard/ae-dashboard.html`; otherwise `/dashboard/safety-workspace.html`.
- `applyRoleKeyedNav()` selects the nav set by role type.

However, this helper is coupled to the shell's sms360x-branded header (logo image + "sms360x" wordmark) and the `app-shell` wrapper, which conflicts with the dept-home ws-header visual language (neutral logo placeholder, no sms360x branding).

## 5. Proposed header/navigation behavior

Adopt the dept-home ws-header language on all four operational pages:

- `.ws-header` teal-dark bar with `.ws-logo` neutral placeholder (fa-building), `#wsAirline`, `#wsDept`, `#wsEmail`, `#wsLogout`.
- Dynamic airline name via `TenantResolver.prettifySlug(tenant)` (fallback: prettify slug).
- Human-readable department name from claims.department (prettified, + " Department" if not already).
- Authenticated email from `user.email`.
- Logout → signOut → `/login.html`.
- Neutral airline logo placeholder replaced at runtime by claims.logo_url / tenant logo path.
- No sms360x branding, no sms360x-logo.png, no "sms360x" wordmark.
- Remove duplicate headers: drop the inline `.nav` (my-tasks, master-register) and stop using shell.js app-header on these pages (or disable shell header injection). Keep `app-shell`/`.page` content layout.

Back to Home routing (role-aware, reuse existing helper logic):

- For `DEPT_ADMIN` → `/dashboard/dept-home.html` (Department Home).
- For other roles → preserve existing destination: SAFETY/AE/etc. keep `/dashboard/safety-workspace.html` (or their role landing). AE → `/dashboard/ae-dashboard.html`.
- Do not hardcode departmental navigation for all users. Reuse `getUserRoleType` from nav-config.js to decide. The existing `applyDeptHeaderVisibility` pattern can be generalized: add a "Back to Home" link whose href is set based on role type:
  - DEPT_ADMIN → `/dashboard/dept-home.html`
  - AE → `/dashboard/ae-dashboard.html`
  - others → `/dashboard/safety-workspace.html` (or safety-manager as appropriate).
- Also add a "Back to Home" affordance (link or brand click) in the ws-header since ws-header has no nav dropdowns; dept-home currently has none. Could make the logo/airline name clickable for DEPT_ADMIN → dept-home.

Send Feedback: preserve on every page. Either keep shell.js (which lazy-loads feedback.js) but suppress its header/hero/footer injection, or explicitly load `/js/feedback.js` and call `initFeedbackWidget()`. Recommended: explicit load + init to guarantee feedback widget without shell's sms360x header.

## 6. Recommended implementation strategy

Compare:

A. Reusing a shared header/navigation component.
- Pros: single source of truth, consistent visual language, easy future updates.
- Cons: requires refactoring shell.js to support a "ws-header mode" (neutral logo, no sms360x branding, ws-header markup) and a role-aware Home route; touches all shell consumers → high regression risk across unrelated dashboards.

B. Applying bounded page-specific header changes.
- Pros: lowest risk; only the 4 operational pages change; no impact on other dashboards; functional code untouched.
- Cons: some markup duplication (ws-header block ×4) but bounded and identical to dept-home; acceptable given no shared component abstraction exists for ws-header today.

Recommendation: **B (bounded page-specific header changes)**, with reuse of existing helpers (TenantResolver, getUserRoleType from nav-config.js, firebase auth) to avoid duplicating logic. Do not modify shell.js. Optionally extract a tiny shared snippet later if duplication becomes a maintenance burden, but out of scope for this mod.

Rationale: The ws-header visual language is currently only in dept-home.html as inline markup + inline script. There is no shared ws-header component. Creating one (option A) would require touching shell.js and risk regressions across all dashboards. Bounded changes keep risk localized.

## 7. Exact files requiring changes (implementation, future)

1. `public/dashboard/my-tasks.html` — replace legacy `.nav` + suppress shell header; add ws-header block + inline auth/tenant script; load feedback.js + initFeedbackWidget; keep all functional code (stats, filters, tables, Submit MOR).
2. `public/dashboard/master-register.html` — same header swap; keep filters/search/records/role-gated Reports tab.
3. `public/can_cap/cans.html` — add ws-header; remove shell sms360x header (suppress shell header or drop shell.js header injection); keep CAN functionality.
4. `public/can_cap/caps.html` — same for CAP.
5. Optional: create `public/js/ws_header.js` helper to render ws-header + auth/tenant + role-aware Home routing, reducing duplication. (Recommended as a follow-up, not required.)

Files NOT to change: shell.js, nav-config.js, tenant_context.js, feedback.js, firebase.js, all backend/API files, database, Firebase claims.

## 8. Regression risks

- Removing shell.js entirely would lose NAV_CONFIG dropdown navigation on these pages. Mitigation: keep shell.js for nav but suppress its header/hero injection, OR keep a minimal nav. Actually shell.js always builds header+hero+footer. Options:
  - Keep shell.js (nav + feedback injection) but hide `.app-header` via CSS and not rely on it for branding; risk: duplicate hidden header, layout offset.
  - Better: drop shell.js, load nav-config.js for `getUserRoleType`, and implement a simple "Back to Home" link in ws-header based on role. Nav dropdowns are not strictly needed on operational pages? They are useful. 
  - Compromise: keep shell.js but override its header branding? shell.js hardcodes sms360x logo + wordmark in buildHeader. Can't easily override without editing shell.js (out of scope).
  - Recommended: keep shell.js for navigation dropdowns and feedback injection, but visually neutralize the sms360x brand by hiding the brand link text/image via CSS on these pages? That still leaves duplicate headers.
  - Cleanest bounded approach: remove shell.js usage on these 4 pages; retain nav-config.js (for role type) and feedback.js (explicit). Add a single "Back to Home" link in ws-header. Lose dropdown nav but gain clean ws-header. Acceptable trade-off per mod objective (header/nav integration, not full nav parity). Owner to decide.
- Auth/tenant guards must remain; ensure `applyDepartmentContext` still called where needed (my-tasks, master-register, dept scope).
- `updateShellTenant` calls become unnecessary if shell.js removed; replace with direct `#wsAirline`/`#wsDept` population (as in dept-home).
- Feedback widget: ensure `/js/feedback.js` loaded and `initFeedbackWidget()` called (dept-home pattern) since shell no longer lazy-loads it.
- Role-based Submit MOR (my-tasks) and Reports tab (master-register) logic must remain untouched.

## 9. Recommended implementation sequence

1. Owner review & approval of this proposal + decision on nav dropdown retention (shell.js keep vs drop).
2. Prototype on `my-tasks.html` first (lowest complexity, clear role gating).
3. Apply same pattern to `master-register.html`.
4. Apply to `cans.html` and `caps.html`.
5. Verify: auth/tenant isolation, role-based Home routing, feedback widget, no sms360x branding, no duplicate headers, functional parity (stats/filters/tables/APIs).
6. Regression sweep on unrelated dashboards (ensure shell.js untouched).

## 10. Open questions for owner

1. Should the 4 pages retain the shell.js dropdown navigation (requiring a shell.js "neutral/ws-header mode" change — option A subset), or drop it for a clean ws-header with a single Back-to-Home link (option B as proposed)?
2. Should a shared `ws_header.js` helper be created now (reduces duplication) or deferred?
3. For non-DEPT_ADMIN roles on these pages, should "Back to Home" go to `/dashboard/safety-workspace.html` or `/dashboard/safety-manager.html`? (Current shell default is safety-workspace; dept-home has no Home link.)
4. Confirm neutral logo placeholder asset path (dept-home uses fa-building icon in `.ws-logo`; is a real neutral placeholder image preferred?).

STOP — findings delivered for owner review. No code changes made.
