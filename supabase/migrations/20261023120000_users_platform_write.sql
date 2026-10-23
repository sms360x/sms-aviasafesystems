-- Phase 3A remediation D1: allow SUPER_ADMIN to write the users mirror row.
-- public.users has RLS enabled with a single read policy (user_read_own) and
-- no permissive write policy, so PATCH /admin/users (and any admin endpoint
-- that refreshes a users mirror row) fails with "new row violates row-level
-- security policy for table users" after the Firebase claim was written.
--
-- This adds a platform-scoped write policy: only a SUPER_ADMIN identity may
-- insert/update/delete rows in public.users. Tenant-scoped writes continue to
-- be impossible through RLS; platform writes are gated by app.current_role.

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS users_platform_write ON public.users;
CREATE POLICY users_platform_write ON public.users
    FOR ALL
    TO public
    USING (current_setting('app.current_role', true) = 'SUPER_ADMIN')
    WITH CHECK (current_setting('app.current_role', true) = 'SUPER_ADMIN');
