-- ============================================================================
-- 2C.3b-fix — apply the 20 RLS rewrites that did not reach live in 2C.3b
--
-- 2C.3b (20261013120000_rls_policies_guc.sql) declares 42 policies rewritten
-- to read the session GUCs (app.current_role / app.current_tenant /
-- app.current_tenant_slug). Live shows only 22 GUC-based; the other 20 are
-- still the original GoTrue-claim (`auth.jwt()`) definitions produced by the
-- Module B / Module C migrations.
--
-- This migration re-applies ONLY those 20 DROP + CREATE pairs, verbatim from
-- the 2C.3b design. It touches nothing else:
--   * the 22 already-GUC-based policies are not touched;
--   * the 12 unversioned policies (2C.3c) are not touched;
--   * the 8 deferred zero-policy tenant tables (2C.4) are not touched;
--   * no schema change, no application-code change; the enforcement flag
--     RLS_ENFORCEMENT_ENABLED stays OFF.
--
-- Idempotent: DROP POLICY IF EXISTS precedes every CREATE.
-- ============================================================================

-- ── Module B tables (operator-only template) ──
DROP POLICY IF EXISTS p_action_items_tenant_isolation ON public.action_items;
CREATE POLICY p_action_items_tenant_isolation ON public.action_items
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

DROP POLICY IF EXISTS p_hazard_triage_tenant_isolation ON public.hazard_triage;
CREATE POLICY p_hazard_triage_tenant_isolation ON public.hazard_triage
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

DROP POLICY IF EXISTS p_import_batches_tenant_isolation ON public.import_batches;
CREATE POLICY p_import_batches_tenant_isolation ON public.import_batches
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

DROP POLICY IF EXISTS p_import_links_tenant_isolation ON public.import_links;
CREATE POLICY p_import_links_tenant_isolation ON public.import_links
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

DROP POLICY IF EXISTS p_import_mappings_tenant_isolation ON public.import_mappings;
CREATE POLICY p_import_mappings_tenant_isolation ON public.import_mappings
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

DROP POLICY IF EXISTS p_import_rows_tenant_isolation ON public.import_rows;
CREATE POLICY p_import_rows_tenant_isolation ON public.import_rows
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

DROP POLICY IF EXISTS p_safety_communications_tenant_isolation ON public.safety_communications;
CREATE POLICY p_safety_communications_tenant_isolation ON public.safety_communications
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

DROP POLICY IF EXISTS p_sag_meetings_tenant_isolation ON public.sag_meetings;
CREATE POLICY p_sag_meetings_tenant_isolation ON public.sag_meetings
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

DROP POLICY IF EXISTS p_srb_meetings_tenant_isolation ON public.srb_meetings;
CREATE POLICY p_srb_meetings_tenant_isolation ON public.srb_meetings
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

-- ── Module C tables ──
DROP POLICY IF EXISTS p_module_c_aggregates_tenant_isolation ON public.module_c_aggregates;
CREATE POLICY p_module_c_aggregates_tenant_isolation ON public.module_c_aggregates
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

DROP POLICY IF EXISTS p_caan_reports_tenant_isolation ON public.caan_reports;
CREATE POLICY p_caan_reports_tenant_isolation ON public.caan_reports
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant_slug', true), '')
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant_slug', true), '')
  );

DROP POLICY IF EXISTS p_caan_reports_cross_tenant ON public.caan_reports;
CREATE POLICY p_caan_reports_cross_tenant ON public.caan_reports
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']))
  WITH CHECK (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']));

DROP POLICY IF EXISTS p_metric_definitions_cross_tenant ON public.metric_definitions;
CREATE POLICY p_metric_definitions_cross_tenant ON public.metric_definitions
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']))
  WITH CHECK (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']));

DROP POLICY IF EXISTS p_module_c_aggregates_cross_tenant ON public.module_c_aggregates;
CREATE POLICY p_module_c_aggregates_cross_tenant ON public.module_c_aggregates
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']))
  WITH CHECK (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']));

DROP POLICY IF EXISTS p_module_c_aggregates_national ON public.module_c_aggregates;
CREATE POLICY p_module_c_aggregates_national ON public.module_c_aggregates
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (tenant_id IS NULL AND current_setting('app.current_role', true) = 'STATE_SMD')
  WITH CHECK (tenant_id IS NULL AND current_setting('app.current_role', true) = 'STATE_SMD');

DROP POLICY IF EXISTS p_regulatory_reports_cross_tenant ON public.regulatory_reports;
CREATE POLICY p_regulatory_reports_cross_tenant ON public.regulatory_reports
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']))
  WITH CHECK (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']));

DROP POLICY IF EXISTS p_state_risk_categories_cross_tenant ON public.state_risk_categories;
CREATE POLICY p_state_risk_categories_cross_tenant ON public.state_risk_categories
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']))
  WITH CHECK (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']));

DROP POLICY IF EXISTS p_state_risk_register_cross_tenant ON public.state_risk_register;
CREATE POLICY p_state_risk_register_cross_tenant ON public.state_risk_register
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']))
  WITH CHECK (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']));

DROP POLICY IF EXISTS p_taxonomy_mappings_cross_tenant ON public.taxonomy_mappings;
CREATE POLICY p_taxonomy_mappings_cross_tenant ON public.taxonomy_mappings
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']))
  WITH CHECK (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']));

DROP POLICY IF EXISTS p_state_safety_performance_targets_caan ON public.state_safety_performance_targets;
CREATE POLICY p_state_safety_performance_targets_caan ON public.state_safety_performance_targets
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']))
  WITH CHECK (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']));
