# DASHBOARD-MOD-02B Implementation Report

## Changed files
- backend/app/routes/can_cap.py (added /activity-trend endpoint)
- public/dashboard/dept-home.html (hero chart + Chart.js)

## Endpoint
- GET {API_PREFIX}/activity-trend (likely /api/can-cap/activity-trend)
- Auth: get_current_user; tenant/department/is_demo enforced.

## Status
- Backend aggregation implemented in Python using fetch_all filtered by tenant/department/is_demo.
- Frontend renders two-series line chart with Chart.js.
- Loading/error states present.

## Verification
- UNVERIFIED: runtime execution (no DB in this environment).