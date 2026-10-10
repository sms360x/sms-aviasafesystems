-- ============================================================================
-- 2A.3 — membership backfill (Step 2, W1)
--
-- One membership per existing user, from users.role / users.tenant_id.
--   * SUPER_ADMIN            -> tenant_id NULL (platform context; design Q5)
--   * every other known role -> tenant_id = users.tenant_id
--
-- Skipped (reported as orphans in docs/step2/2A.3_orphaned_users.md, NOT
-- backfilled): users whose role is NULL / not a known value, or whose
-- non-SUPER_ADMIN known role has a NULL tenant_id (cannot be scoped).
--
-- Idempotent: the NOT EXISTS clause makes a re-run a no-op.
-- No users-table change, no schema change, no RLS policy, no code change.
-- ============================================================================

INSERT INTO public.memberships
    (user_id, tenant_id, role, effective_from, effective_to, is_active)
SELECT
    u.id,
    CASE WHEN u.role = 'SUPER_ADMIN' THEN NULL ELSE u.tenant_id END,
    u.role,
    COALESCE(u.created_at, now()),
    NULL,
    true
FROM public.users u
WHERE u.role IN (
        'SUPER_ADMIN', 'CAAN_SMD', 'STATE_SMD', 'TENANT_ADMIN',
        'AIRLINE_ADMIN', 'ACCOUNTABLE_EXECUTIVE', 'DEPT_ADMIN',
        'SAFETY_OFFICER', 'OFFICER', 'STAFF', 'USER', 'SAG_MEMBER'
    )
  AND (u.role = 'SUPER_ADMIN' OR u.tenant_id IS NOT NULL)
  AND NOT EXISTS (
        SELECT 1 FROM public.memberships m WHERE m.user_id = u.id
    );
