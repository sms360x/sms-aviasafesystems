# Project Resume: AviaSAFE SMS (Phase 3D — Dashboard Data & Refinement)

## 1. Project State & Context
- **Repository:** `DHFactors/sms-aviasafesystems` (single `main` branch only)
- **Deployments:**
  - Frontend: Firebase Hosting (`aerosafety-sms-prod` site) — auto-deploys via GitHub Actions from `main`
  - Backend: Render (`aviasafe-unified-platform`) — auto-deploys via GitHub from `main`
- **Domains:**
  - `sms360x.com` — SaaS landing page + login
  - `sita.sms360x.com`, `tara.sms360x.com`, etc. — Tenant-scoped login
  - `sms.aviasafesystems.com` — RETIRED (removed from Firebase and Cloudflare)
- **Database:** Supabase (RLS + Phase 3A security verified)
- **Marketing:** The old `sms360x-site` repo is retired. The Astro marketing page content is now baked into `aviasafesms/public/index.html`.

## 2. What Was Just Accomplished (Phase 3C)
- **Domain Migration:** Full cutover from `sms.aviasafesystems.com` to `sms360x.com` and `*.sms360x.com` subdomains.
- **Login Page:** Split-screen layout with SMS360X branding. Custom circular logo. Helpful left panel. "Forgot Password" link. Mobile-responsive.
- **Landing Page:** Replicated the Astro marketing design in plain HTML/Tailwind. "Who it is for" section now uses 4 icon cards (Airlines, ATO, MRO, State Regulators).
- **Dashboard Header:** Custom `sms360x` logo, lowercase branding, nav wrapping fixed.
- **Backend CORS:** Allowed `sms360x.com` and `*.sms360x.com` origins.
- **Repo Cleanup:** Deleted all stale branches. Only `main` remains. All work consolidated. Dormant Astro/Tailwind/archive removed.

## 3. Immediate Next Steps (Phase 3D)
1. **Dashboard Data Refinement:**
   - Populate KPIs and charts with realistic dummy data (currently showing "Loading..." or "0").
   - Fix the per-page KPI grid responsiveness (tenant-dashboard.css, caan-oversight.css, aviasdcps.css).
2. **Hazard Management Table:** Populate the hazard list with realistic sample entries.
3. **Recent Activity Feed:** Populate with realistic activity.
4. **Survey Module (Module A):** Verify the `/survey/?tenant=<slug>` flow end-to-end.

## 4. How to Resume
The SME will start the next session by pasting this prompt.
The AI should:
1. Acknowledge that Phase 3C is complete.
2. Begin Phase 3D with a verification dispatch (read-only audit of the dashboard data rendering).
3. Only after the audit, issue a fix dispatch based on real facts.

## 5. Working Rules (Established This Session)
- **Never edit code directly.** All code is written by OpenCode.
- **Verify before fix.** Always issue a read-only audit first.
- **Commit only after SME confirms.** Never push without explicit "push approved."
- **Use Markdown code blocks for OpenCode dispatches.** No raw shell scripts in the SME's path.
- **One commit = one logical change.**
