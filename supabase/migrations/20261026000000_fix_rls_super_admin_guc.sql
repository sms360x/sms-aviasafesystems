-- ============================================================================
-- FILE: 20261026000000_fix_rls_super_admin_guc.sql
-- PURPOSE: Fix RLS policies that rely on auth.jwt() ->> 'role' = 'SUPER_ADMIN'
--          so that SUPER_ADMIN is also recognised from the app.current_role
--          GUC (set by the backend for direct SQLAlchemy connections).
-- ============================================================================

-- 1. tenants
DROP POLICY IF EXISTS tenant_admin_all ON public.tenants;
CREATE POLICY tenant_admin_all ON public.tenants
    FOR ALL TO public
    USING (
        (auth.jwt() ->> 'role') = 'SUPER_ADMIN'
        OR current_setting('app.current_role', true) = 'SUPER_ADMIN'
    )
    WITH CHECK (
        (auth.jwt() ->> 'role') = 'SUPER_ADMIN'
        OR current_setting('app.current_role', true) = 'SUPER_ADMIN'
    );

-- 2. users
DROP POLICY IF EXISTS platform_write_users ON public.users;
CREATE POLICY platform_write_users ON public.users
    FOR ALL TO public
    USING (
        (auth.jwt() ->> 'role') = 'SUPER_ADMIN'
        OR current_setting('app.current_role', true) = 'SUPER_ADMIN'
    )
    WITH CHECK (
        (auth.jwt() ->> 'role') = 'SUPER_ADMIN'
        OR current_setting('app.current_role', true) = 'SUPER_ADMIN'
    );

-- 3. audit_logs
DROP POLICY IF EXISTS audit_logs_admin_only ON public.audit_logs;
CREATE POLICY audit_logs_admin_only ON public.audit_logs
    FOR SELECT TO public
    USING (
        (auth.jwt() ->> 'role') = 'SUPER_ADMIN'
        OR current_setting('app.current_role', true) = 'SUPER_ADMIN'
    );

-- 4. is_super_admin() helper (defence in depth)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'is_super_admin') THEN
        EXECUTE $f$
            CREATE OR REPLACE FUNCTION public.is_super_admin()
            RETURNS boolean
            LANGUAGE sql STABLE
            AS $body$
                SELECT
                    COALESCE((auth.jwt() ->> 'role') = 'SUPER_ADMIN', false)
                    OR COALESCE(current_setting('app.current_role', true) = 'SUPER_ADMIN', false);
            $body$;
        $f$;
    END IF;
END $$;
