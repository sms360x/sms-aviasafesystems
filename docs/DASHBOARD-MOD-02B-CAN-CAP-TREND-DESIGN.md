# DASHBOARD-MOD-02B — Departmental CAN/CAP Activity Trend (Design)

## Architecture findings
- CAN table: `cans` (SQLAlchemy `Can`), CAP table: `caps` (`Cap`).
- Date fields: `cans.issued_at` (authoritative for CANs issued), `caps.submitted_at` (authoritative for CAPs created).
- Ownership: `tenant_id`, `department` (nullable). `is_demo` boolean separates DEMO/LIVE.
- Backend: FastAPI, auth via Firebase claims. Existing can_cap router prefix from settings.

## Proposed backend aggregation
- New endpoint: `GET /api/can-cap/activity-trend` (or under existing prefix).
- Auth: Firebase bearer token; resolve tenant + department from verified claims (not browser).
- Filter: tenant_id = claim tenant; department = claim department (for OFFICER/DEPT_ADMIN); is_demo matches runtime mode.
- Aggregate counts by month (YYYY-MM) for last 12 calendar months including current, using issued_at/submitted_at.
- Include zero months. Exclude null dates and missing department attribution (only count records whose department matches).
- Avoid double counting: count CAPs by submitted_at independently of CANs.

## Frontend integration
- Add hero section above four cards in dept-home.html with a line chart (Chart.js if available, else lightweight SVG). Need inspect existing chart lib; assume Chart.js CDN.
- Two series: CANs issued, CAPs created. Legend, tooltips, responsive.
- Loading/empty/error states. No fabricated counts.

## Unresolved questions
- Exact API prefix and existing aggregate endpoint availability.
- Timezone convention (UTC vs tenant local) for month bucketing.
- Charting library currently bundled?

## Minimal file list (implementation)
- backend/app/routes/can_cap.py (new endpoint)
- backend/app/services/can_cap_service.py (aggregation)
- public/dashboard/dept-home.html (hero + chart)
- docs report.

## Recommendation
READY FOR IMPLEMENTATION (pending architect confirmation of timezone and chart library).