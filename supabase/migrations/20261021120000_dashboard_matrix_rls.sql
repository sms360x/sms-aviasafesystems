-- 2D.3 — Dashboard authorization matrix (RLS defense in depth).
--
--   * DEPT_ADMIN  : hazards / cans are department-scoped via app.current_department.
--   * STATE_SMD   : raw hazards / reports are no longer visible through the
--                   oversight_relationships branch — aggregate views only.
--   * ACCOUNTABLE_EXECUTIVE : relies on the app-layer gate; RLS keeps tenant
--                   isolation (no role branch exists to remove here).
--
-- Idempotent: safe to re-run.

-- ── 1. hazards — department predicate, drop STATE_SMD oversight branch ──
DROP POLICY IF EXISTS p_hazards_tenant_isolation ON public.hazards;
CREATE POLICY p_hazards_tenant_isolation ON public.hazards
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR (
      tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
      AND (
        current_setting('app.current_role', true) <> 'DEPT_ADMIN'
        OR department = current_setting('app.current_department', true)
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

-- ── 2. cans — department predicate ──
DROP POLICY IF EXISTS p_cans_tenant_isolation ON public.cans;
CREATE POLICY p_cans_tenant_isolation ON public.cans
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR (
      tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
      AND (
        current_setting('app.current_role', true) <> 'DEPT_ADMIN'
        OR department = current_setting('app.current_department', true)
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

-- ── 3. reports — drop STATE_SMD MOR oversight branch (aggregate views only) ──
DROP POLICY IF EXISTS p_reports_tenant_isolation ON public.reports;
CREATE POLICY p_reports_tenant_isolation ON public.reports
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );
