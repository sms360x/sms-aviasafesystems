# SMS360X Product Roadmap

**Last Updated:** 2026-10-26
**Architecture:** FastAPI + Supabase (PostgreSQL) + Firebase Hosting + Two Standalone Mini-SaaS Tools.
**Current State:** CSV-only import verified working. ETL and Export tools built. Old architecture purged.

---

## Phase 1: Deploy the Mini-SaaS Suite (Priority: High)
**Goal:** Get the ETL and Export tools live on custom subdomains so prospective clients can use them.

### 1.1 Deploy ETL Tool to Render
- **Root Directory:** `etl-mini-saas/`
- **Build Command:** `pip install -r requirements.txt && cd web && npm ci && npm run build && cd ..`
- **Start Command:** `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- **Custom Domain:** `etl.sms360x.com`
- **Verification:** Upload `Master Logsheet-2026.xlsx` and download the Hazard CSV.

### 1.2 Deploy Export Tool to Render
- **Root Directory:** `export-mini-saas/`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT --env-file .env`
- **Environment Variables:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `EXPORT_TENANT_ID`, `EXPORT_PASSWORD`, `EXPORT_USERNAME`.
- **Custom Domain:** `export.sms360x.com`
- **Verification:** Export the Hazard register as CSV and open in Excel.

---

## Phase 2: Implement the New Dashboards (Priority: High)
**Goal:** Replace the old dashboard HTML with the new executive layouts (Safety Manager, Accountable Manager, State Admin, Dept Admin).

### 2.1 Build the Safety Manager Dashboard
- **New File:** `public/dashboard/safety-manager.html`
- **Design System:** Use `executive-ui.css` and `executive-shell.js`.
- **Sections:** KPIs, Safety Risk Profile (5x5 matrix), Reports Trend, Corrective Actions, Recent Reports, Tasks, SPIs, Compliance.
- **API Endpoints:**
  - `/api/v1/dashboard/recent` (reports + hazards)
  - `/api/v1/dashboard/trends` (monthly)
  - `/api/v1/cans/` (corrective actions)
  - `/api/v1/spis/` (safety performance indicators)

### 2.2 Build the Accountable Manager Dashboard
- **New File:** `public/dashboard/accountable-manager.html`
- **Design System:** Same `executive-ui.css`.
- **Sections:** SMS Health (composite score), Top Risks (5 highest), Safety Performance Trends, Corrective Action Status, Regulatory Compliance, Matters Requiring Attention.
- **API Endpoints:**
  - `/api/v1/dashboard/overview` (aggregated KPIs)
  - `/api/v1/dashboard/hazards` (top 5 risks)
  - `/api/v1/dashboard/risk-trends` (SPIs over time)

### 2.3 Build the State Admin & Dept Admin Dashboards
- **Files:** `public/dashboard/state-admin.html`, `public/dashboard/dept-admin.html`
- **Scope:** Define the specific KPIs for regulators (State Admin) and department managers (Dept Admin).

---

## Phase 3: Seed the Demo Airline (Priority: Medium)
**Goal:** Give prospective clients a fully-populated demo tenant.

### 3.1 Create the Demo Tenant
- **Tenant Slug:** `demo-airline`
- **UUID:** `uuid5(NAMESPACE_DNS, "tenant:demo-airline")`
- **Data Source:** Convert the Sita Air Master Logsheet into clean CSVs using the ETL tool.

### 3.2 Seed Data
- **Hazards:** 30–50 realistic hazards (with threat, consequence, taxonomy).
- **Occurrences:** 20–30 VSR/MOR reports.
- **Flight Diversions:** 10–15 diversions.
- **Corrective Actions:** 10–15 open/closed CANs/CAPs.
- **Risk Register:** 10–20 assessed risks with Bow-Tie analysis.

### 3.3 Demo Login Flow
- Create a "Try Demo" button on the landing page that auto-logs into `demo-airline` with a read-only `DEMO_VIEWER` role.

---

## Phase 4: CAAN Compliance Hardening (Priority: Medium)
**Goal:** Reach 100% alignment with the CAAN SRM Manual (Jan 2026).

### 4.1 ERC Matrix (Event Risk Classification)
- **Backend:** Add an ERC function in `srm_engine.py` (4x4 → H/M/L priority).
- **Frontend:** Add an ERC Matrix UI to the hazard assessment flow.
- **Database:** Add `erc_matrix` JSONB column to the `hazards` table.

### 4.2 Hazard Field Extensions
- **Database Migration:**
  - `hazards.area_operation_equipment` (Text)
  - `hazards.hazard_taxonomy` (Enum: Organizational, Technical, Human, Environmental)

### 4.3 Risk Acceptance Authority Mapping
- **Backend:** Add a mapping in `srm_engine.py` associating each risk level with the authorized signer (Accountable Manager, Risk Owner, Safety Manager).
- **Frontend:** Add an "Acceptance Authority" field to the risk register UI.

---

## Phase 5: Documentation & Onboarding (Priority: Low)
**Goal:** Replace old architecture contracts with a single authoritative `SMS_ARCHITECTURE.md`.

### 5.1 Write the New Architecture Doc
- **Sections:** System Overview, Data Model, API Endpoints, Mini-SaaS Integration, CAAN Compliance Matrix.

### 5.2 Create the Client Onboarding Guide
- **File:** `docs/CLIENT_ONBOARDING.md`
- **Content:** Step-by-step for new airlines:
  1. Export data from legacy system.
  2. Use the ETL tool to convert to CSV.
  3. Upload to SMS360X.
  4. Use the Export tool for compliance audits.

---

## Phase 6: Production Hardening (Priority: Low)
**Goal:** Prepare for multi-tenant scaling.
- **Render Upgrade:** Move from Free to Starter to remove cold starts.
- **Supabase Upgrade:** Move to Pro for higher connection limits and backups.
- **Monitoring:** Add Sentry and UptimeRobot.
- **CI/CD:** Add automated tests for backend, frontend, ETL, Export.

---

## Immediate Next Steps (Next Session)
1. **Create `ROADMAP.md`** (this file).
2. **Deploy ETL + Export to Render** (Phase 1).
3. **Build the Safety Manager Dashboard** (Phase 2.1).

**Total Estimated Effort:** ~8 sessions (~1 month at current pace).
