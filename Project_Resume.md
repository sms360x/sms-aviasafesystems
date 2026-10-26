# Project Resume: AviaSAFE SMS (Phase 3D — CSV Import Complete)

**Session Date:** 2026-10-26  
**Status:** CSV-only Master Logsheet import is VERIFIED WORKING end-to-end in production.  
**Next Priority:** Build the ETL (Excel → CSV) and Export (DB → CSV) Mini-SaaS tools.

## ✅ Master Logsheet Import (CSV) — VERIFIED WORKING
The import engine is fully functional, bypassing the previous PgBouncer deadlock.

- **Frontend:** `/dashboard/historical-import.html` (embedded in Safety Dashboard). Uses App Check + Auth.
- **Backend:** `POST /api/v1/imports/master-logsheet` and `/promote`.
- **Architecture:** Uses isolated SQLAlchemy transactions (`get_engine().begin()`) to bypass the shared bridge session.
- **RLS:** Deterministic tenant UUID (`uuid5`) is used consistently for both `app.current_tenant` and staging inserts.
- **Dashboard:** Dual-insert into `reports` ensures KPIs update immediately.

### Smoke Test Results (2026-10-26)
- Uploaded `test_import.csv` (3 rows).
- Result: 200 OK, 3 rows staged, 3 rows promoted.
- Dashboard KPIs updated (Total Reports: 27 → 30).

## 🚀 Next Phase: Complimentary Mini-SaaS Suite
We are building two standalone tools to ship as a complimentary onboarding suite for prospective clients. This solves the "messy data" problem and provides a demo airline dataset.

### Mini-SaaS 1: ETL Tool (Excel → CSV)
**Purpose:** Allow airlines to upload their messy, multi-tab Excel logsheets, map columns, validate data, and download clean CSV files that the core SMS can ingest.

**Tech Stack:** Python (FastAPI) + Pandas or React + SheetJS.

**Key Features:**
- Multi-tab Excel upload.
- Column mapping UI (auto-detect headers, map to CAAN canonical headers).
- Validation engine (dates, enums, required fields).
- Output: ZIP containing `hazards.csv`, `occurrences.csv`, `flight_diversions.csv`, and `validation_report.csv`.

### Mini-SaaS 2: Export Tool (DB → CSV)
**Purpose:** Allow prospective clients to see the "Exit Strategy" — export any register (Hazard, Risk, Barrier, Occurrence) into a clean, CAAN-formatted CSV.

**Tech Stack:** Same stack as core app.

**Key Features:**
- Select tenant and register type.
- Apply date filters.
- One-click download of CAAN-compliant CSV.

### The Demo Airline Concept
- **Scenario:** Prospective client logs into the app.
- **Action:** They are given access to a "Demo Airline" tenant (e.g., "Sita Air Demo") pre-populated with realistic, CAAN-compliant data.
- **Value:** They can explore the dashboard, run reports, and see the system populated before making a purchase decision.
- **Onboarding:** When they sign, they use the **ETL Mini-SaaS** to convert their real Excel files, upload the CSVs, and clear the demo data.
