# Logsheet Studio — standalone Excel → separate CSVs

This app is independent of the SMS backend. It imports nothing from `backend/app`, needs no database, and writes no uploaded workbook to disk. Pandas validates/converts on the server; React and SheetJS provide the upload/review interface.

## Run locally (Python 3.12+, Node 22+)

From `etl-mini-saas/`:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
cd web
npm ci
npm run build
cd ..
.\.venv\Scripts\python -m uvicorn api.main:app --host 127.0.0.1 --port 8001
```

Open http://127.0.0.1:8001. For frontend development, run `npm run dev` from `web/` in another terminal; Vite proxies `/api` to port 8001. API docs: http://127.0.0.1:8001/api/docs.

## Workflow

1. Upload an `.xlsx` (20 MB maximum, expanded XLSX contents at most 100 MB).
2. Every tab is listed. Review the detected header row and choose one or two header rows. Two-level headers are flattened, merged parent labels are carried across child labels, and duplicate names receive a suffix. Unnamed columns are retained as `Column N`, including blank leading columns, to avoid losing source data.
3. **Split only** is the default. It preserves source columns before mapping. It does not enforce entity validation. Export first, then use the results to decide the mapping plan.
4. **Map to standard headers** optionally selects Hazard, Occurrence, or Diversion per tab. Map each target header to a source column or enter a constant (for example, an explicitly reviewed `Status` constant). Unmapped output fields are blank. Tabs with no agreed contract can stay `Original`.
5. Generate, then download each tab's CSV separately. Filenames match workbook tabs; filesystem-unsafe characters are replaced by underscores. No ZIP is produced. Download `validation_report.csv` separately.

**Test mode is intentionally fixed to the first 10 physical data rows after each tab's header.** Fewer rows means fewer exported rows; headers-only tabs generate headers-only CSVs. Invalid mapped rows are excluded, and the converter does not reach beyond the first ten to replace them. Up to 110 worksheet rows are inspected, with automatic header search within the first 60 rows. Header controls support the first 61 rows. This is not yet a full-workbook production conversion mode.

## Exact mapped CSV contracts

Hazard:
```csv
"S.N","Reported Date","Occurrence Date","Sources of Information","Description","Hazard ID","Taxonomy","Threat","Top Event","Consequence","Priority","Status","Concerned Department","Remarks"
```
Occurrence:
```csv
"S.N","Reported Date","Occurrence Date","Sources of Information","Description","Occurrence","Status","Concerned Department","Remarks"
```
Diversion:
```csv
"S.N","Occurrence Date","Flight Number","Flight Sector","Diverted To","Aircraft Registration","Reason of diversion","Description","Status","Remarks"
```

Mapped validation: nonempty Description; Status exactly Open/Closed; nonempty dates must be real dates in YYYY-MM-DD or DD/MM/YYYY, normalized to YYYY-MM-DD. Native Excel date cells are accepted. Blank dates remain blank because the supplied contract did not make them mandatory. Hazard Priority defaults to M only when blank, otherwise H/M/L; Taxonomy defaults to Organizational only when blank, otherwise Organizational/Technical/Human/Environmental. Invalid nonempty enums are rejected, not silently recategorized. There is no invented default Status or date. Report columns: Sheet, Excel Row (1-based original worksheet row), Result, Details. Split-only rows are explicitly marked unmapped with validation deferred.

The CSV writer quotes every field, preserves embedded commas/newlines and Unicode, and uses CRLF. Downloads have a UTF-8 BOM for Excel. Source text is trimmed and native dates are serialized; split mode does not perform entity mapping. Formula cells are read as their cached Excel values; recalculate and save the workbook in Excel before upload if formula results are missing. Literal formula-like text is preserved for ingestion, so treat unknown input as data when opening it in spreadsheet software.

## Supplied workbook samples

`sample-output/` contains separate exports from `data/Master Logsheet-2026.xlsx`:

| Tab | Header Excel row | Header depth | Sample data rows |
| --- | --- | --- | --- |
| Master logsheet 2026 working | 2 | 2 | 10 |
| Occurrence 2026 | 2 | 2 | 7 |
| Safety Deficiencies 2026 | 3 | 2 | 10 |
| Hazard-logsheet-2026 | 3 | 2 | 0 |
| Flight diversion report-2026 | 3 | 1 | 10 |
| Risk Register-sheet-2026 | 2 | 2 | 0 |

These are split-only review files, not validated SMS import files. The supplied diversion sheet has no Status column and separates sector origin/destination; the mapping plan must decide status and sector composition before ingestion. Safety Deficiencies and Risk need an agreed contract. No values have been inferred for them.

## Verification

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
cd web
npm run build
```

No accounts, billing, durable uploads, or public hosting are configured. Run locally for this review phase. Sample files contain the workbook's safety narratives; handle them as airline data.
