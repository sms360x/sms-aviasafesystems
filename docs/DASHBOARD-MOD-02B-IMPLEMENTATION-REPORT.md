# DASHBOARD-MOD-02B Implementation Report

## Root cause
Frontend requested relative `/api/can-cap/activity-trend` against hosting origin, returning HTML (DOCTYPE). Fixed to use APP_CONFIG.apiBaseUrl and validate content-type.

## Changed files
- public/dashboard/dept-home.html

## Verification
- UNVERIFIED runtime; corrected request base.