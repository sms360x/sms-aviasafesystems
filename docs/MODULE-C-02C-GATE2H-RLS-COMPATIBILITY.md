# MODULE-C-02C — Gate 2H RLS Compatibility Report

Date: 05 November 2026
Mode: Read-only

## Findings

- DATABASE_URL not exposed.
- Backend role cannot be determined statically; RLS listener installs GUCs (session.py lines 180-187).
- RLS policies for new tables are not defined in the migration (only ENABLE RLS). Backend access depends on existing RLS conventions/role grants. UNVERIFIED.
- Minimum corrective action if inaccessible: add appropriate RLS policies/privileges for the backend role following existing conventions, without bypassing RLS.

## Status

UNVERIFIED (requires live DB inspection). STOP for owner review.