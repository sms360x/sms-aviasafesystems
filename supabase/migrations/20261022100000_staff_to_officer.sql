-- ============================================================================
-- Step-3 role cleanup — retire the STAFF role literal.
--
-- 2B.3 (20261012140000_role_migration.sql) normalised the general-employee
-- cluster (USER / CAMO_USER / QA_USER / SAG_MEMBER) onto the literal 'STAFF'.
-- Step-3 retires that literal: OFFICER absorbs it, so the canonical role set
-- is SUPER_ADMIN, STATE_SMD, TENANT_ADMIN, DEPT_ADMIN, OFFICER and
-- ACCOUNTABLE_EXECUTIVE.
--
-- This rewrites the remaining 'STAFF' rows in the two role stores so no live
-- account is left holding a role the application no longer recognises.
--
-- Idempotent: the WHERE guard means a re-run affects 0 rows.
-- Reversible: UPDATE public.users SET role = 'STAFF' WHERE role = 'OFFICER'
--             (and the same for public.memberships) — scoped to the rows this
--             migration touched.
-- ============================================================================

UPDATE public.users
SET role = 'OFFICER'
WHERE role = 'STAFF';

UPDATE public.memberships
SET role = 'OFFICER'
WHERE role = 'STAFF';
