# SMS360X — Project Resume

**Session date:** 26 October 2026  
**Resume commit:** `c924081` — `feat: align risk matrix and CAP donut with ICAO Doc 9859 standard`  
**Branch:** `main`  
**Remote:** `origin/main` = `c924081` (parent `710bf6f` is included on the remote)  
**Status:** ICAO Doc 9859 risk-matrix and CAP-donut alignment is committed and pushed.

---

## 1. Project Overview

SMS360X is a multi-tenant aviation Safety Management System (SMS).

Core modules:

- **Module A — SMS Maturity:** survey capture, scoring, maturity pillars, and assessments.
- **Module B — Risk & Hazard:** occurrence reports, hazards, risk matrix, SRM, CANs, and CAPs.
- **Module C — PSOE:** safety oversight / audit workflows. Currently out of scope for the executive dashboard phase.

**Current focus:** building the Executive Safety Manager Dashboard:

- `public/dashboard/safety-manager.html`

**Standards direction:** align all risk and safety-action math to the universal **ICAO Doc 9859** 5×5 letter grid and human-in-the-loop CAP state machine. The platform is state-agnostic for multi-state SaaS use; do not introduce regulator-specific terminology.

---

## 2. Architecture & Routing

### Frontend

- Static HTML / CSS / JavaScript.
- Firebase Hosting at `sms360x.com`.
- No frontend framework or bundler in the dashboard path.

### Backend

- FastAPI.
- Supabase PostgreSQL.
- SQLAlchemy async sessions with tenant isolation and demo scoping.

### Dashboard file structure

| File | Role |
|---|---|
| `public/dashboard/safety-manager.html` | Landing-page shell and section containers |
| `public/js/dashboard-safety-manager.js` | Auth boot, API calls, rendering, chart setup |
| `public/js/executive-shell.js` | Sidebar, topbar, responsive layout shell |
| `public/css/executive-ui.css` | Executive dashboard layout, cards, matrix, donut, tables |
| `public/js/api/client.js` | Authenticated API client; unwraps the response envelope |
| `public/js/nav-config.js` | Navigation configuration (do not modify this session series) |

### Backend files

| File | Role |
|---|---|
| `backend/app/routes/dashboard.py` | Dashboard route controllers |
| `backend/app/services/dashboard_service.py` | Dashboard orchestration and calculations |
| `backend/app/services/risk_calculator.py` | Canonical ICAO 5×5 tolerability grid and risk-index helpers |
| `backend/app/services/survey_scoring.py` | Survey scoring engine and weighted maturity composite |
| `backend/app/db/db_models.py` | SQLAlchemy models, including `Hazard` and `Cap` |

> **Routing note:** the dispatch path `backend/app/api/v1/dashboard.py` does not exist. The real dashboard route module is `backend/app/routes/dashboard.py`.

### Live tenant dashboard endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/dashboard/overview` | KPI payload; now includes real CAP-overdue count and `action_completion` |
| `GET /api/v1/dashboard/sms-health` | SMS maturity KPI projection |
| `GET /api/v1/dashboard/trends` | Monthly report trends |
| `GET /api/v1/dashboard/risk-matrix` | ICAO 5×5 matrix with 25 enriched cells |
| `GET /api/v1/dashboard/action-completion` | CAP state-machine counts for the donut |
| `GET /api/v1/dashboard/key-issues` | Top safety issues |
| `GET /api/v1/dashboard/hazards` | Hazard frequency ranking |
| `GET /api/v1/dashboard/recent` | Recent reports |
| `GET /api/v1/dashboard/master-register` | Unified hazards + CANs + CAPs view |

---

## 3. Completed in This Session

### Dashboard shell and UI

- Fixed syntax issues in `public/js/executive-shell.js` and `public/css/executive-ui.css`.
- Rebuilt `public/dashboard/safety-manager.html` toward the SME’s visual reference.
  - **Current checked-in snapshot at `c924081`:** 4 KPI cards and sections **S1–S10**.
  - **SME reference target:** 5 KPI cards and 13 numbered sections.
  - The fifth KPI card and sections 11–13 are not yet present in the checked-in HTML. Confirm the intended fifth KPI and remaining section list with the SME before adding them.
- Wired the existing dynamic data to the new shell:
  - **S1 KPIs:** `/dashboard/overview` + `/dashboard/sms-health`
  - **S2 Risk Matrix:** `/dashboard/risk-matrix`
  - **S3 Reports Trend:** `/dashboard/trends`
  - **S4 Top 5 Issues:** `/dashboard/key-issues`
  - **S5 Corrective Actions donut:** `/dashboard/action-completion`
  - **S6 Recent Reports:** `/dashboard/recent`
  - **S8 SPI trends:** `/spi/tenant/{tenant}/trend?months=12`

### ICAO Doc 9859 alignment — commit `c924081`

**Risk matrix:**

- Replaced the numeric-only presentation with the ICAO 5×5 letter grid.
- Severity mapping: `5=A`, `4=B`, `3=C`, `2=D`, `1=E`.
- Probability mapping: `5=Frequent`, `4=Occasional`, `3=Remote`, `2=Improbable`, `1=Extremely Improbable`.
- Risk Index is an alphanumeric grid reference such as `"4B"`.
- Tolerability uses the canonical grid in `backend/app/services/risk_calculator.py`:
  - **Intolerable:** `5A 5B 5C 4A 4B 3A`
  - **Tolerable:** `5D 5E 4C 4D 4E 3B 3C 3D 2A 2B 2C 1A`
  - **Acceptable:** `3E 2D 2E 1B 1C 1D 1E`
- All 25 cells return `risk_index`, `tolerability`, and hazard count.
- Legacy numeric fields (`severity`, `probability`, `count`, `severity_label`, `probability_label`) are preserved for backward compatibility.
- The frontend renders:
  - Y-axis: `Catastrophic (A)` → `Negligible (E)`
  - X-axis: `Frequent (5)` → `Extremely Improbable (1)`
  - Cell text: risk index + count
  - Cell colour: red / yellow / green by tolerability

**CAP donut / human-in-the-loop state machine:**

- Removed the hardcoded `safety_actions_overdue: 0` from the live overview path.
- Added `GET /api/v1/dashboard/action-completion`.
- `DashboardService.get_action_completion()` queries the `Cap` table with tenant and demo scoping.
- Buckets are mutually exclusive and server-computed:
  - **Overdue:** past target date, or literal `Overdue` status
  - **Due ≤30d:** target date between today and today + 30 days
  - **On Track:** target date beyond 30 days
  - **Pending Review:** `Under Review`, `Returned`, `Revision Required`
  - **Closed:** terminal outcomes (`Completed`, `Closed`, `Escalated`, `Cancelled`, `Rejected`, `Accepted`)
- `EIP` is treated as **On Track** because it is active but has no time limit.
- Overdue is evaluated before Pending Review so a review item that has blown its target date still surfaces as overdue.
- The frontend no longer performs CAP date math; it consumes the server counts directly.

**Verification performed:**

- `python -m py_compile` passed for the changed backend files.
- `node --check` passed for `dashboard-safety-manager.js` and `executive-shell.js`.
- All 25 ICAO cells verified against the required tolerability sets; `4B` → `Intolerable`.
- CAP bucket assertions verified for terminal, overdue, pending-review, due-soon, EIP, and missing-date cases.
- `pytest tests/test_metrics_service.py -q` → 11 passed.
- DB-backed tests hit the known pgbouncer `DuplicatePreparedStatementError`; this is an infrastructure issue, not a code regression.

---

## 4. Known Issues & Deferred Items

### SMS Maturity (Module A) math — Audit D1

`GET /api/v1/dashboard/sms-health` calls `DashboardService.get_airline_sms_maturity()`, which uses `_aggregate_surveys()`.

The aggregation currently computes:

```text
overall_sms_maturity = unweighted average of the four pillar averages
```

Meanwhile, the survey scoring engine in `backend/app/services/survey_scoring.py` defines the intended weighted composite:

```text
Safety Policy 10 / Safety Risk Management 40 / Safety Assurance 30 / Safety Promotion 20
```

This must be reconciled so the dashboard KPI reflects the same weighted score that was saved at survey submission. Do not change this until the SME confirms the intended production formula and historical-data treatment.

### Dashboard stubs

The following sections are styled empty states and still need backend endpoints:

- **S7 — My Tasks & Approvals**
- **S9 — Compliance & Regulatory**
- **S10 — Latest Safety Intelligence**

### PSOE (Module C)

Out of scope for the current executive-dashboard phase. Do not start PSOE work in this commit series.

### ETL / historical upload

Handled externally via `sms360x.com/etl`. Do not link these tools in the main dashboard menu.

### Reports trend badge

S3 currently shows live monthly trend data and still carries the `Monthly — 12-week pending` badge. Treat the badge as a UI follow-up, not a data blocker.

---

## 5. Immediate Next Steps for Next Session (Option A — Recommended)

### Goal: Drill-down modals from the 5×5 risk matrix

Clicking a matrix cell (for example, `4B`) should open a modal listing the specific hazards in that severity/probability cell.

### Required tasks

1. **Backend endpoint**
   - Add to the existing `backend/app/routes/dashboard.py` (do not create a new route module):
     `GET /api/v1/dashboard/risk-matrix/cell?severity={}&probability={}`
   - Authenticate with `get_tenant_user`.
   - Validate `severity` and `probability` as integers `1–5`.
   - Delegate to a new `DashboardService` method, for example `get_hazard_risk_cell(severity, probability)`.
   - Tenant-scope with `register_tenant(self.tenant_id)` and `is_demo == demo_scope()`.
   - Return only hazards whose numeric severity and probability match the requested cell.
   - Suggested response contract:

     ```json
     {
       "severity": 4,
       "probability": 4,
       "risk_index": "4B",
       "tolerability": "Intolerable",
       "total": 1,
       "items": [
         {
           "id": "...",
           "hazard_id": "...",
           "title": "...",
           "status": "...",
           "assigned_to": "...",
           "department": "...",
           "created_at": "...",
           "risk_level": "..."
         }
       ]
     }
     ```

   - Reuse the canonical ICAO helpers (`risk_index`, `get_tolerability`) rather than duplicating the grid.
   - Add a sensible result cap and document it, so a large cell cannot return an unbounded payload.

2. **Reusable frontend modal**
   - Create `public/js/executive-modal.js`.
   - Requirements:
     - Focus trap while open.
     - Close on Escape, backdrop click, and explicit close button.
     - Restore focus to the triggering matrix cell on close.
     - ARIA attributes (`role="dialog"`, `aria-modal="true"`, labelled title).
     - Loading, empty, and error states.
     - No inline event-handler strings; attach listeners in JavaScript.

3. **Matrix interaction**
   - Update `public/js/dashboard-safety-manager.js`.
   - Add `data-severity`, `data-probability`, `data-risk-index`, and `data-tolerability` attributes to each `.exec-risk-cell`.
   - Use event delegation on `#s2-matrix` for click and keyboard activation (`Enter` / `Space`).
   - Fetch the new cell endpoint and render the hazard list in the modal.
   - Show the cell reference and tolerability in the modal header.
   - Handle empty cells without opening an empty modal, or show a clear “No hazards in this cell” state.
   - Preserve the existing rendering when the modal script is unavailable.

4. **Verification**
   - Add unit coverage for the service filter (exact severity/probability matching, tenant/demo scoping).
   - Smoke-test the endpoint with a `TENANT_ADMIN` token.
   - Confirm a different tenant cannot see another tenant’s hazards.
   - Run `node --check` on the new and changed JavaScript.
   - Run the pure backend tests; note the known pgbouncer limitation for DB-backed tests.

### Guardrails for this task

- Do not change the existing `/dashboard/risk-matrix` response shape; the modal endpoint is additive.
- Do not move ICAO math into the browser.
- Do not start SMS Maturity or PSOE work as part of the modal task.
- Do not touch `nav-config.js`, `executive-shell.js`, `safety.html`, or legacy pages unless the SME explicitly expands scope.

---

## 6. Test Credentials

| Role | Value |
|---|---|
| **TENANT_ADMIN (sita-air)** | `safety@sitaair.com.np` |
| **SUPER_ADMIN** | `ezondiza.dhf@gmail.com` |
| **Tenant UUID** | `2ec7c30d-bbdf-5ec1-b897-ea6a28f6c6fc` |
| **Firebase App Check debug token** | `[REDACTED — rotated in Firebase Console on 2026-10-28]` |

The App Check debug token must be registered in the Firebase Console for the test environment.

**Security note:** these are test accounts/tokens. Do not reuse them in production and do not commit production secrets.

---

## 7. Working Rules

1. **Verify before fix.** Start with a read-only audit of the relevant files and live behavior.
2. **Use state-neutral terminology.** Use `STATE` or `ICAO`; do not introduce regulator-specific abbreviations in code or UI.
3. **Protect the working tree.** Do not push `firebase.json` or `public/etl/`; they are intentional local working-tree changes.
4. **One commit = one logical change.** Keep commits reviewable and avoid mixing modules.
5. **Preserve backward compatibility.** Keep legacy numeric risk fields and endpoints intact unless the SME approves a breaking change.
6. **Do not start PSOE or SMS Maturity work in the current dashboard commit series.**
7. **Do not touch `nav-config.js`, `executive-shell.js`, `safety.html`, or legacy pages** during the current dashboard phase unless scope is explicitly expanded.
8. **Server owns the math.** Tolerability, risk indices, CAP buckets, and date comparisons must remain server-side.

---

## Appendix — Quick Start for the Next Session

1. Confirm the baseline:

   ```powershell
   git status --short
   git log --oneline -3
   ```

   Expected:

   ```text
    M firebase.json
   ?? public/etl/
   c924081 feat: align risk matrix and CAP donut with ICAO Doc 9859 standard
   710bf6f feat: integrate existing SMS Maturity math into new dashboard
   222f7a6 feat: hardcode executive navigation menu for new dashboard
   ```

2. Read these files before changing anything:
   - `public/dashboard/safety-manager.html`
   - `public/js/dashboard-safety-manager.js`
   - `backend/app/routes/dashboard.py`
   - `backend/app/services/dashboard_service.py`
   - `backend/app/services/risk_calculator.py`
   - `backend/app/db/db_models.py` (`Hazard`, `Cap`)

3. Verify the current endpoints:
   - `GET /api/v1/dashboard/risk-matrix`
   - `GET /api/v1/dashboard/action-completion`

4. Implement Option A (drill-down modals) as described in Section 5.

5. Commit only the modal feature files and push `main`. Do not stage `firebase.json` or `public/etl/`.
