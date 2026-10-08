# 1D — Reporter Redaction Check (schema side of item 1C.1b)

Read-only. Date: 2026-10-08.

## Q1 — Is there a place to store VSR reporter contact details separately from report content?
**No.** Reporter metadata is stored on the **same row** as the report content in the Postgres `reports` table:
- `reports.reporter_name`, `reporter_role`, `reporter_email`, `reporter_phone`, `reporter_organisation` (`backend/app/db/db_models.py:259-263`)
- `reports.is_anonymous` (`db_models.py:206`)
- `reports.narrative` (report content) is on the same row.

There is no separate reporter-contact table and no separate "custodian-only" store. This is the schema gap for item 1C.1b: contact details cannot be isolated to the airline Safety Department because they live in the register row itself.

## Q2 — Does the code redact the reporter identity when a VSR's content enters a register?
**No — not automatically.**
- A redaction helper exists for **body content**: `models/report.py:290-291` replaces email and phone patterns with `[REDACTED_EMAIL]` / `[REDACTED_PHONE]` during validation. This redacts contact-like strings *inside the narrative*, not the reporter metadata columns.
- A confidentiality service exists: `backend/app/services/confidential_reporting_service.py` — `_IDENTITY_FIELDS = ("reporter_name", "reporter_email", "reporter_phone", ...)` (`:30`) and `deidentify()` (`:73-83`) strips those fields, with an audited de-identified read (`CAAN_READ_REPORT_DEIDENTIFIED`, `:135`).
- **However, the service is not wired into any route** (referenced only by `backend/tests/test_confidential_reporting.py`). So no submission/register path invokes `deidentify`; identity is not stripped on register entry.
- `routes/occurrence_reports.py:211-212` sets `reporter_name = "Anonymous"` only when it is absent — it does not strip a provided identity.

## Q3 — Does the code preserve self-identified names in the report body as content (not reporter metadata)?
**Effectively yes, but not deliberately.** The body/narrative is stored as content (`reports.narrative`) and is not redacted for personal names — the redaction regex (`models/report.py:290-291`) targets emails and phone numbers only. So a name the reporter writes into the narrative remains as report content. There is no explicit rule/flag distinguishing "self-identified name in body" from metadata; it is preserved only by omission of any name-redaction.

## Plain statement
- No separate storage location for VSR reporter contact details → **does not exist** (they are columns on `reports`). This is the finding.
- Reporter identity is **not** redacted on register entry → `confidential_reporting_service.deidentify` exists but is unwired.
- Self-identified names in the body are preserved as content → yes, by lack of name redaction (not by explicit design).

Files: `backend/app/db/db_models.py:206,259-263`; `backend/app/models/report.py:290-291`; `backend/app/services/confidential_reporting_service.py:30,73-83,135`; `backend/app/routes/occurrence_reports.py:211-212`.

Documentation only; no code changed.
