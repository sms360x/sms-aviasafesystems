-- ============================================================================
-- 2A.5 — memberships reporting substrate: one active row per user.
--
-- SME ruling (2026-10-12): one user = one tenant = one role (ICAO
-- accountability). The memberships table is retained as a Super-Admin-only
-- reporting substrate, kept in sync with the users row (on creation and role
-- change). It is not read by any operational/auth path.
--
-- This partial unique index enforces at most one ACTIVE membership per user.
-- Idempotent: safe to re-run.
-- ============================================================================

CREATE UNIQUE INDEX IF NOT EXISTS memberships_one_active_per_user
    ON public.memberships (user_id)
    WHERE is_active = true;
