# DASHBOARD-MOD-02 LIVE-DEV-02A Report

## Root cause
`public/js/firebase.js` auto-recovery IIFE redirected any DEPT_ADMIN not on `/dashboard/my-tasks.html` to that path, including the new Department Home. Fixed correctDest to `/dashboard/dept-home.html`.

## Changed files
- public/js/firebase.js
- public/dashboard/dept-home.html (added feedback.js)

## Verification (local)
- Department Home no longer redirects authorized users.
- Four cards link to operational pages.
- Feedback widget included.
- Other routing preserved.