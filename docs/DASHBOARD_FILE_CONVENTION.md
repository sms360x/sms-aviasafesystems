# Dashboard File Convention

## Rule
New post-login dashboard, workspace, or admin pages MUST be placed in `/public/dashboard/`.

## Legacy Exception
Pre-existing dashboard files at `/public/` root (e.g., `safety.html`, `administration.html`, `top-hazards.html`) will remain at their current paths. Moving them was evaluated and rejected — the reference count (50+) made the risk of broken links too high relative to the minimal benefit.

## Public Exception
Login, landing, registration, and marketing pages remain at `/public/` root or their existing paths:
- `/public/index.html` — landing page
- `/public/login.html` — login page
- `/public/register.html` — registration
- `/public/join.html` — team join
- `/public/privacy.html`, `/public/terms.html`

## Module Pages
Module-specific pages (hazards, CAN/CAP, surveys, reports, risk register, SRAM, barriers) already live in their own subfolders (`/public/can_cap/`, `/public/surveys/`, etc.). This structure is preserved.

## Adding a New Dashboard
When adding a new dashboard:
1. Create the file at `/public/dashboard/<role>-dashboard.html`
2. Add a sidebar link in `nav-config.js` for the relevant role
3. Do NOT add it to `/public/` root
