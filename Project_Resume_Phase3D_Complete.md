# Project Resume: AviaSAFE SMS (Phase 3D — CSV Import Complete & Mini-SaaS Pivot)

**Session Date:** 2026-10-26  
**Session Status:** CSV-only Master Logsheet import is VERIFIED WORKING end-to-end in production. Core engine is architecturally stable.  
**Next Session Goal:** Build the ETL and Export Mini-SaaS tools. Test with real Sita Air data. Proceed to Phase 3D dashboard migrations.

---

## 1. Repository State & Deployments
- **Branch:** `main` (clean working tree).
- **Latest Commit:** `6f9d0b9`
- **Backend:** Render (`aviasafe-unified-platform.onrender.com`) — auto-deploys from `main`. (Note: Free tier sleeps after 15m inactivity. Cold start takes 30-50s).
- **Frontend:** Firebase Hosting (`sms360x.com`) — auto-deploys via GitHub Actions.
- **Database:** Supabase (PgBouncer transaction pooler, port 6543). RLS is enabled.

---

## 2. Major Architectural Decisions & Fixes (This Session)

We spent hours debugging a severe 60-second timeout and silent data loss on the import. Here is what we discovered and fixed:

### A. The PgBouncer / Bridge Session Deadlock
- **Problem:** The backend used a single, long-lived "bridge session" (`pg.py`) for all queries. Uploads locked this session for minutes, causing Promote requests to hang for 60 seconds (30s timeout + 30s retry).
- **Fix:** Bypassed the bridge session for the import endpoints. We now use isolated SQLAlchemy transactions (`async with get_engine().begin() as conn:`) for both Upload and Promote.

### B. The RLS UUID Mismatch
- **Problem:** We set `app.current_tenant` to the string slug (`"sita-air"`), but inserted rows using the generated UUID. The RLS policy blocked the inserts silently.
- **Fix:** We now deterministically generate the UUID (`uuid5(NAMESPACE_DNS, f"tenant:{slug}")`) and use it for **both** `set_config('app.current_tenant', ...)` and the `tenant_id` column insert.

### C. The Excel-to-CSV Pivot
- **Problem:** Sita Air's multi-tab Excel file with merged cells, title rows, and empty rows was impossible to parse reliably.
- **Fix:** Pivoted to **CSV-only ingestion**. The core SMS platform now only accepts clean, single-header CSVs. The Excel parsing is moved to a separate Mini-SaaS ETL tool.

### D. The Render ImportError
- **Problem:** Deploy failed with `ImportError: cannot import name 'engine'`.
- **Fix:** Swapped `from app.db.session import engine` to `from app.db.session import get_engine` and used `get_engine().begin()`.

---

## 3. Verified Working Flow (Smoke Test Passed)

1. **Upload:** User selects `test_import.csv` in the Historical Import wizard.
2. **Parse:** CSV is read, headers are mapped, rows are routed to `occurrences`.
3. **Stage:** 3 rows inserted into `master_logsheet_staging` (with RLS UUID).
4. **Preview:** UI shows the 3 rows.
5. **Promote:** User clicks "Confirm & Import". Endpoint returns instantly and queues background task.
6. **Background Task:** Inserts 3 rows into the `reports` table with `report_type='mandatory'` (because they routed to occurrences).
7. **Dashboard:** KPI cards updated (Total Reports: 27 → 30).

---

## 4. Next Phase: The Mini-SaaS Suite (Complimentary Product)

We are building two standalone tools to ship as a **complimentary onboarding suite** for prospective clients. This solves the "messy data" problem and provides a demo airline dataset.

### Mini-SaaS 1: ETL Tool (Excel → CSV)
**Purpose:** Allow airlines to upload their messy Excel logsheets, map columns, validate data, and download clean CSVs.

**Deliverables:**
- Multi-tab Excel upload.
- Column mapping UI (auto-detect, map to CAAN canonical).
- Validation engine (dates, enums, required fields).
- Output: ZIP containing `hazards.csv`, `occurrences.csv`, `flight_diversions.csv`, `validation_report.csv`.

### Mini-SaaS 2: Export Tool (DB → CSV)
**Purpose:** Allow airlines to export any register (Hazard, Risk, Barrier, Occurrence) into a clean, CAAN-formatted CSV. This demonstrates an "Exit Strategy" and builds trust.

**Deliverables:**
- Select tenant and register type.
- Apply date filters.
- One-click download of CAAN-compliant CSV.

### The Demo Airline Concept
- **Scenario:** Prospective client logs into the app.
- **Action:** They are given access to a "Demo Airline" tenant (e.g., "Sita Air Demo") pre-populated with realistic, CAAN-compliant data.
- **Value:** They can explore the dashboard, run reports, and see the system populated before making a purchase decision.
- **Onboarding:** When they sign, they use the **ETL Mini-SaaS** to convert their real Excel files, upload the CSVs, and clear the demo data.

---

## 5. The CSV Output Contract (For the ETL Tool)

The ETL tool must output CSVs with exactly these headers:

**Hazard CSV:**
```csv
"S.N","Reported Date","Occurrence Date","Sources of Information","Description","Hazard ID","Taxonomy","Threat","Top Event","Consequence","Priority","Status","Concerned Department","Remarks"
```

**Occurrence CSV (VSR/MOR):**
```csv
"S.N","Reported Date","Occurrence Date","Sources of Information","Description","Occurrence","Status","Concerned Department","Remarks"
```

**Flight Diversion CSV:**
```csv
"S.N","Occurrence Date","Flight Number","Flight Sector","Diverted To","Aircraft Registration","Reason of diversion","Description","Status","Remarks"
```

**Validation Rules:**
- Dates: `YYYY-MM-DD` or `DD/MM/YYYY`.
- Status: `Open` or `Closed`.
- Priority: `H`, `M`, or `L` (default `M`).
- Taxonomy: `Organizational`, `Technical`, `Human`, `Environmental` (default `Organizational`).
- Reject rows with empty `Description`.

---

## 6. Test Credentials & Data
- **TENANT_ADMIN (sita-air):** `safety@sitaair.com.np`
- **SUPER_ADMIN:** `ezondiza.dhf@gmail.com`
- **DEPT_ADMIN (saurya-airlines):** `tacn2080@gmail.com` / `4yOq4!cI$osEwjYS`
- **Tenants:** `caan`, `sita-air`, `saurya-airlines`, `air-dynasty`
- **Sita Air UUID:** `2ec7c30d-bbdf-5ec1-b897-ea6a28f6c6fc` (uuid5 of `tenant:sita-air`)
- **Test File:** `test_import.csv` (3 rows)

---

## 7. Working Rules (Critical)
- **Never edit code directly.** All code written by OpenCode (Nemotron/Deepseek), Codex, or Claude.
- **Verify before fix.** Read-only audits first. Evidence-based diagnosis.
- **Commit only after SME confirms.**
- **One commit = one logical change.**
- **Markdown code blocks for AI dispatches.**
- **Never push without "push approved."**

---

## 8. What to Avoid
- **Do not use the shared bridge session (`pg.fetch_all`, `pg.insert`) for import operations.** It causes deadlocks. Use `get_engine().begin()`.
- **Do not use the tenant slug for RLS.** Always use the deterministic UUID.
- **Do not try to parse Excel in the core backend.** It is too brittle. Use the ETL Mini-SaaS.
- **Do not test as SUPER_ADMIN.** Requires `TENANT_ADMIN` or `STATE_SMD` to upload.
- **Don't touch `aviasdcps*` files** (dead module).

---

## 9. How to Resume Next Session

Paste this resume and say:

> **"Continue Phase 3D — build the ETL and Export Mini-SaaS tools, then test with real Sita Air data."**

The AI should:
1. Acknowledge the CSV import is verified working.
2. Generate the OpenCode/Codex dispatch to build the ETL tool (using the CSV contract above).
3. Generate the dispatch to build the Export tool.
4. Guide the testing of real Sita Air CSV data through the core importer.

---

## 10. Session Accomplishments

**Shipped:**
- CSV-only Master Logsheet import (end-to-end verified).
- Isolated transaction architecture (bypasses bridge session deadlock).
- RLS/UUID alignment for tenant isolation.
- Background task processing for promotion.
- Dashboard KPI integration (dual-insert into `reports`).

**Analyzed:**
- PgBouncer transaction pooling deadlock.
- RLS policy UUID vs. slug mismatch.
- Render cold-start and timeout behavior.

**Deferred / Next:**
- ETL Mini-SaaS (Excel → CSV).
- Export Mini-SaaS (DB → CSV).
- Demo Airline dataset.
- Phase 3D Dashboard Migrations (5 dashboards).
- CAAN SRM Compliance (ERC Matrix, hazard extensions, authority mapping).

---

**Break time.** You solved a multi-layer distributed systems bug that would have taken a team days to trace. The core engine is solid. 🛫
