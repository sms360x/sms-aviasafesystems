# Airline Register Export — standalone read-only tool

Exports Hazard, active SRAM Risk, Barrier, Occurrence, and Flight Diversion registers without importing or modifying the core SMS application. FastAPI serves a small HTML/JS frontend. Preview reads at most ten rows; download retrieves all matching rows through paginated Supabase REST GET requests.

## Local setup (Python 3.12+)

From `export-mini-saas/`:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env with server-side values; never commit it.
.\.venv\Scripts\python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8002
```

Open http://127.0.0.1:8002 and choose a register/date range. The browser asks for the configured username/password when preview is requested. Preview first, then download the CSV. Defaults: user `export`; password must be explicitly configured.

Required environment:

- `SUPABASE_URL`: HTTPS project root, e.g. https://your-project.supabase.co.
- `SUPABASE_SERVICE_ROLE_KEY`: server-only key with read access to these tables. Never enter it in frontend code.
- `EXPORT_TENANT_ID`: canonical airline tenant UUID. Mandatory, even for All Time. For occurrences, the text column must store this UUID string; installations storing slugs need an explicit reviewed adapter.
- `EXPORT_PASSWORD`: required local access password.
- `EXPORT_USERNAME`: optional, defaults to export.

No existing credentials were copied or database calls made during implementation. Supply your own local `.env` to verify against the deployed database.

## Register definitions and date filters

| Selector | Table | Date filter/order field |
| --- | --- | --- |
| Hazard | hazards | created_at (registered date) |
| Risk | sram_risk_register | created_at (registered date) |
| Barrier | barrier_register | created_at (registered date) |
| Occurrence | occurrences | date (occurrence date) |
| Flight Diversion | flight_diversions | date (occurrence date) |

30/60/90 days are rolling UTC intervals from request time. All Time applies no date restriction and includes null dates. Date-filtered results exclude null dates. Oldest first, then UUID for stable ordering; preview shows the first ten in that order. Export reads fresh data, so concurrent edits can change results between preview and export. Pagination uses offset/id ordering, not a transaction snapshot. Exports exceeding 100,000 rows fail explicitly and do not download a partial CSV.

`app/registers.py` defines explicit field projections and human-readable CSV headers. Risk uses the active SRAM table, not the legacy risk_register. Barrier fields follow the current repository model: action_by, follow_up_date, notes and seven element scores; the older pasted schema described different fields. A deployment with a different schema returns a clear error instead of guessing or omitting columns.

## CAAN format status

This is a register-data export with fields useful for SRM review (hazard, consequence, initial/resultant risk, tolerability, controls, actions and dates). It is **not a verified CAAN submission template**. The applicable CAAN SRM Manual edition, exact approved headers/order, mandatory fields and formatting were not supplied. Review these projections against that template before representing the CSV as compliant. No regulatory content or risk acceptance decisions are inferred.

## Security and behavior

All database operations are GET requests to five fixed allowlisted tables with explicit tenant filters. There are no insert/update/delete/RPC routes. A Supabase service role key itself can bypass RLS and may have write privileges: this application restricts its use to reads; it does not change the key's database permissions. The password protects API access and the key never reaches the browser. Bind to loopback for local use; add HTTPS and organization identity/access controls before shared hosting. CSV responses and API responses are not cached. Returned errors do not include upstream bodies or credentials.

CSV uses exact declared header order, quoted fields, CRLF, UTF-8 BOM, empty fields for nulls, Yes/No for booleans and unchanged source timestamps. Formula-like text receives a leading apostrophe for spreadsheet safety. Empty results still download the full header. No ZIP. No export data is stored on the server.

## Test

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
```

Tests mock Supabase HTTP responses and verify authentication, required configuration, tenant filtering, allowed registers, pagination even with small server page caps, safe errors and CSV output. Live database/schema permissions require a configured local environment and are not asserted by mocked tests.
