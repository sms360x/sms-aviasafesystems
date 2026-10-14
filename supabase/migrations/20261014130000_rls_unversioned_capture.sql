-- ============================================================================
-- 2C.3c — capture the 12 unversioned RLS policies into the repo
--
-- These 12 policies exist in the live database but had no source in
-- supabase/migrations/ (Step 1 census / 2C.1 §13). This migration makes the
-- repo the source of truth for their current live definitions.
--
-- The definitions below are the live catalog definitions, reproduced verbatim
-- (via pg_get_expr). No policy is changed: DROP POLICY IF EXISTS + CREATE
-- POLICY is a no-op in effect. Nothing else is touched (the 2C.3b / 2C.3b-fix
-- policies, the 8 deferred zero-policy tables, and the enforcement flag are
-- untouched).
--
-- Idempotent: DROP POLICY IF EXISTS precedes every CREATE.
-- ============================================================================

-- READ-ONLY / claim-scoped policies -------------------------------------------------

DROP POLICY IF EXISTS audit_logs_admin_only ON public.audit_logs;
CREATE POLICY audit_logs_admin_only ON public.audit_logs
    FOR SELECT
    TO public
    USING (((auth.jwt() ->> 'role'::text) = 'SUPER_ADMIN'::text));

DROP POLICY IF EXISTS hfacs_nanocodes_read_policy ON public.hfacs_nanocodes;
CREATE POLICY hfacs_nanocodes_read_policy ON public.hfacs_nanocodes
    FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS icao_adrep_read_policy ON public.icao_adrep_taxonomies;
CREATE POLICY icao_adrep_read_policy ON public.icao_adrep_taxonomies
    FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS psoe_questions_read_all ON public.psoe_questions;
CREATE POLICY psoe_questions_read_all ON public.psoe_questions
    FOR SELECT
    TO public
    USING (true);

DROP POLICY IF EXISTS regulator_read_all ON public.regulators_old;
CREATE POLICY regulator_read_all ON public.regulators_old
    FOR SELECT
    TO public
    USING (true);

-- `tenants` / `users` self-scoped policies ------------------------------------------

DROP POLICY IF EXISTS tenant_admin_all ON public.tenants;
CREATE POLICY tenant_admin_all ON public.tenants
    FOR ALL
    TO public
    USING (((auth.jwt() ->> 'role'::text) = 'SUPER_ADMIN'::text));

DROP POLICY IF EXISTS tenant_read_own ON public.tenants;
CREATE POLICY tenant_read_own ON public.tenants
    FOR SELECT
    TO public
    USING ((tenant_id = current_setting('app.current_tenant'::text)));

DROP POLICY IF EXISTS user_read_own ON public.users;
CREATE POLICY user_read_own ON public.users
    FOR SELECT
    TO public
    USING ((uid = (auth.uid())::text));

-- Mapping-table tenant isolation (claim-based) --------------------------------------

DROP POLICY IF EXISTS tenant_isolation_hazard_adrep ON public.hazard_adrep_mappings;
CREATE POLICY tenant_isolation_hazard_adrep ON public.hazard_adrep_mappings
    FOR ALL
    TO public
    USING ((tenant_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'tenant_id'::text))::uuid))
    WITH CHECK ((tenant_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'tenant_id'::text))::uuid));

DROP POLICY IF EXISTS tenant_isolation_hazard_hfacs ON public.hazard_hfacs_codes;
CREATE POLICY tenant_isolation_hazard_hfacs ON public.hazard_hfacs_codes
    FOR ALL
    TO public
    USING ((tenant_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'tenant_id'::text))::uuid))
    WITH CHECK ((tenant_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'tenant_id'::text))::uuid));

DROP POLICY IF EXISTS tenant_isolation_report_adrep ON public.report_adrep_mappings;
CREATE POLICY tenant_isolation_report_adrep ON public.report_adrep_mappings
    FOR ALL
    TO public
    USING ((tenant_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'tenant_id'::text))::uuid))
    WITH CHECK ((tenant_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'tenant_id'::text))::uuid));

DROP POLICY IF EXISTS tenant_isolation_report_hfacs ON public.report_hfacs_codes;
CREATE POLICY tenant_isolation_report_hfacs ON public.report_hfacs_codes
    FOR ALL
    TO public
    USING ((tenant_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'tenant_id'::text))::uuid))
    WITH CHECK ((tenant_id = (((auth.jwt() -> 'app_metadata'::text) ->> 'tenant_id'::text))::uuid));
