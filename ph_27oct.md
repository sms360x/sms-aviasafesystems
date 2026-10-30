# SMS360X — Project Handoff (Oct 27)

## Current State (As of Oct 27 EOD)
- **Auth & Routing:** Fixed. `safety@` users now correctly redirect to `/dashboard/safety-manager.html` instead of legacy `/safety.html`. A Logout button was added to the sidebar.
- **Backend Performance:** Fixed. Auth lookups (User & Tenant) are now cached, dropping API load times from 60s to ~2s.
- **Data Wiring:** T4a (CAP KPI fix) and T5-minimal (Donut segment fix) are live. The dashboard populates correctly with existing dummy data.
- **UI/UX:** LongCat overhauled the layout. The dashboard now uses the "bento grid" layout, light theme sidebar, new vibrant matrix colors, and includes placeholder cards for missing sections (S7, S9, S10, S11, S12, S13).
- **Deployment:** Render and Firebase auto-deployments were flaky today. The SME deployed manually. Investigate webhook triggers tomorrow.

## Immediate Next Task: The Hash Router
The sidebar links (Reports, Hazards & Risks, etc.) currently point to `#` and do nothing. We must implement a **hash-based client-side router** in `dashboard-safety-manager.js` (or a new `router.js`).
1. Clicking a nav item (e.g., `#reports`) should hide the current `<div id="pageContent">` and show a new container `#reportsContent`.
2. Clicking "Dashboard" (`#dashboard`) should show the main dashboard grid.
3. Do not reload the page. Do not build the actual views yet — just build the router and stub out `Reports` with a `<div>Reports Coming Soon</div>`.

## Upcoming Tasks (Priority Order)
1. **Hash Router:** Wire up the sidebar links to swap views.
2. **Action Completion KPI Data:** The KPI shows `—` because the tenant has 0 CAPs. Fix `metrics_service.py` to render `0%` (or `N/A`) when the denominator is zero.
3. **SMS Health KPI Data:** Shows `—` because no surveys exist. Add an empty state handler.
4. **S7 (My Tasks) & S9/S10/S12/S13 Endpoints:** Build the backend endpoints and frontend renderers for these placeholder cards.

## OpenCode Setup (Critical for Budget)
- **Do NOT use Kimi K3.1 Pro.** It costs $0.63 per commit/push.
- Use **GLM-5.3-Flash** or **LongCat 2.5 Preview** (which is currently free/unlimited).
- Keep instructions precise. Do not ask the AI to "rewrite the whole file" if it can just patch lines.

## Guardrails (Do Not Violate)
- **Repo Path:** `E:\Projects\sms360x`
- **Live URL:** `https://sms360x.com/dashboard/safety-manager.html`
- **No CAAN:** Use STATE or ICAO in code.
- **CAP Closure:** Human-in-the-loop only. Never auto-close.
- **Server Math:** All logic (tolerability, risk index, CAP buckets) stays in Python, not JS.
