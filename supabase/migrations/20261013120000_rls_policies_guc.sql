-- ============================================================================
-- 2C.3b — rewrite RLS policies to read the session GUCs (Phase 2C)
--
-- Replaces the GoTrue-claim policies with policies that read
--   app.current_role / app.current_tenant / app.current_tenant_slug
-- set per authenticated transaction by 2C.3a.
--
-- Flag RLS_ENFORCEMENT_ENABLED stays OFF; these policies are inert until
-- 2C.3d. Scope: only the 42 live policies that have a repo source and read
-- GoTrue claims. NOT touched here:
--   * the 8 deferred zero-policy tenant tables (2C.4);
--   * the 12 unversioned live policies (2C.3c);
--   * the 7 read-all reference policies and the 2 platform-exempt tables.
--
-- Values: role/tenant comparisons use the canonical role names (STATE_SMD,
-- SUPER_ADMIN) and NULLIF(...,'') guards so an unset GUC fails closed.
-- ============================================================================

-- ── 1. Tenant isolation, UUID columns, with regulator oversight ──
DROP POLICY IF EXISTS p_hazards_tenant_isolation ON public.hazards;
CREATE POLICY p_hazards_tenant_isolation ON public.hazards
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    OR (
      current_setting('app.current_role', true) = 'STATE_SMD'
      AND EXISTS (
        SELECT 1 FROM public.oversight_relationships o
        WHERE o.regulator_tenant_id =
                NULLIF(current_setting('app.current_tenant', true), '')::uuid
          AND o.operator_tenant_id = tenant_id
          AND o.effective_to IS NULL
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

DROP POLICY IF EXISTS p_risk_register_tenant_isolation ON public.risk_register;
CREATE POLICY p_risk_register_tenant_isolation ON public.risk_register
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    OR (
      current_setting('app.current_role', true) = 'STATE_SMD'
      AND EXISTS (
        SELECT 1 FROM public.oversight_relationships o
        WHERE o.regulator_tenant_id =
                NULLIF(current_setting('app.current_tenant', true), '')::uuid
          AND o.operator_tenant_id = tenant_id
          AND o.effective_to IS NULL
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

DROP POLICY IF EXISTS p_barrier_register_tenant_isolation ON public.barrier_register;
CREATE POLICY p_barrier_register_tenant_isolation ON public.barrier_register
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    OR (
      current_setting('app.current_role', true) = 'STATE_SMD'
      AND EXISTS (
        SELECT 1 FROM public.oversight_relationships o
        WHERE o.regulator_tenant_id =
                NULLIF(current_setting('app.current_tenant', true), '')::uuid
          AND o.operator_tenant_id = tenant_id
          AND o.effective_to IS NULL
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

DROP POLICY IF EXISTS p_sram_risk_register_tenant_isolation ON public.sram_risk_register;
CREATE POLICY p_sram_risk_register_tenant_isolation ON public.sram_risk_register
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    OR (
      current_setting('app.current_role', true) = 'STATE_SMD'
      AND EXISTS (
        SELECT 1 FROM public.oversight_relationships o
        WHERE o.regulator_tenant_id =
                NULLIF(current_setting('app.current_tenant', true), '')::uuid
          AND o.operator_tenant_id = tenant_id
          AND o.effective_to IS NULL
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

DROP POLICY IF EXISTS p_bow_tie_analyses_tenant_isolation ON public.bow_tie_analyses;
CREATE POLICY p_bow_tie_analyses_tenant_isolation ON public.bow_tie_analyses
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    OR (
      current_setting('app.current_role', true) = 'STATE_SMD'
      AND EXISTS (
        SELECT 1 FROM public.oversight_relationships o
        WHERE o.regulator_tenant_id =
                NULLIF(current_setting('app.current_tenant', true), '')::uuid
          AND o.operator_tenant_id = tenant_id
          AND o.effective_to IS NULL
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

DROP POLICY IF EXISTS p_bow_tie_threats_tenant_isolation ON public.bow_tie_threats;
CREATE POLICY p_bow_tie_threats_tenant_isolation ON public.bow_tie_threats
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    OR (
      current_setting('app.current_role', true) = 'STATE_SMD'
      AND EXISTS (
        SELECT 1 FROM public.oversight_relationships o
        WHERE o.regulator_tenant_id =
                NULLIF(current_setting('app.current_tenant', true), '')::uuid
          AND o.operator_tenant_id = tenant_id
          AND o.effective_to IS NULL
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

DROP POLICY IF EXISTS p_bow_tie_consequences_tenant_isolation ON public.bow_tie_consequences;
CREATE POLICY p_bow_tie_consequences_tenant_isolation ON public.bow_tie_consequences
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    OR (
      current_setting('app.current_role', true) = 'STATE_SMD'
      AND EXISTS (
        SELECT 1 FROM public.oversight_relationships o
        WHERE o.regulator_tenant_id =
                NULLIF(current_setting('app.current_tenant', true), '')::uuid
          AND o.operator_tenant_id = tenant_id
          AND o.effective_to IS NULL
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

DROP POLICY IF EXISTS p_bow_tie_controls_tenant_isolation ON public.bow_tie_controls;
CREATE POLICY p_bow_tie_controls_tenant_isolation ON public.bow_tie_controls
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    OR (
      current_setting('app.current_role', true) = 'STATE_SMD'
      AND EXISTS (
        SELECT 1 FROM public.oversight_relationships o
        WHERE o.regulator_tenant_id =
                NULLIF(current_setting('app.current_tenant', true), '')::uuid
          AND o.operator_tenant_id = tenant_id
          AND o.effective_to IS NULL
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

DROP POLICY IF EXISTS p_safety_deficiencies_tenant_isolation ON public.safety_deficiencies;
CREATE POLICY p_safety_deficiencies_tenant_isolation ON public.safety_deficiencies
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    OR (
      current_setting('app.current_role', true) = 'STATE_SMD'
      AND EXISTS (
        SELECT 1 FROM public.oversight_relationships o
        WHERE o.regulator_tenant_id =
                NULLIF(current_setting('app.current_tenant', true), '')::uuid
          AND o.operator_tenant_id = tenant_id
          AND o.effective_to IS NULL
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

DROP POLICY IF EXISTS p_sms_maturity_tenant_isolation ON public.sms_maturity;
CREATE POLICY p_sms_maturity_tenant_isolation ON public.sms_maturity
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    OR (
      current_setting('app.current_role', true) = 'STATE_SMD'
      AND EXISTS (
        SELECT 1 FROM public.oversight_relationships o
        WHERE o.regulator_tenant_id =
                NULLIF(current_setting('app.current_tenant', true), '')::uuid
          AND o.operator_tenant_id = tenant_id
          AND o.effective_to IS NULL
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

DROP POLICY IF EXISTS p_regulatory_reports_tenant_isolation ON public.regulatory_reports;
CREATE POLICY p_regulatory_reports_tenant_isolation ON public.regulatory_reports
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    OR (
      current_setting('app.current_role', true) = 'STATE_SMD'
      AND EXISTS (
        SELECT 1 FROM public.oversight_relationships o
        WHERE o.regulator_tenant_id =
                NULLIF(current_setting('app.current_tenant', true), '')::uuid
          AND o.operator_tenant_id = tenant_id
          AND o.effective_to IS NULL
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

DROP POLICY IF EXISTS p_flight_diversions_tenant_isolation ON public.flight_diversions;
CREATE POLICY p_flight_diversions_tenant_isolation ON public.flight_diversions
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    OR (
      current_setting('app.current_role', true) = 'STATE_SMD'
      AND EXISTS (
        SELECT 1 FROM public.oversight_relationships o
        WHERE o.regulator_tenant_id =
                NULLIF(current_setting('app.current_tenant', true), '')::uuid
          AND o.operator_tenant_id = tenant_id
          AND o.effective_to IS NULL
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

DROP POLICY IF EXISTS p_psoe_assessments_tenant_isolation ON public.psoe_assessments;
CREATE POLICY p_psoe_assessments_tenant_isolation ON public.psoe_assessments
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    OR (
      current_setting('app.current_role', true) = 'STATE_SMD'
      AND EXISTS (
        SELECT 1 FROM public.oversight_relationships o
        WHERE o.regulator_tenant_id =
                NULLIF(current_setting('app.current_tenant', true), '')::uuid
          AND o.operator_tenant_id = tenant_id
          AND o.effective_to IS NULL
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

-- ── 2. Tenant isolation, UUID columns, operator-only ──
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

DROP POLICY IF EXISTS p_cans_tenant_isolation ON public.cans;
CREATE POLICY p_cans_tenant_isolation ON public.cans
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

DROP POLICY IF EXISTS p_caps_tenant_isolation ON public.caps;
CREATE POLICY p_caps_tenant_isolation ON public.caps
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

DROP POLICY IF EXISTS p_closures_tenant_isolation ON public.closures;
CREATE POLICY p_closures_tenant_isolation ON public.closures
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

DROP POLICY IF EXISTS p_corrective_actions_tenant_isolation ON public.corrective_actions;
CREATE POLICY p_corrective_actions_tenant_isolation ON public.corrective_actions
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

DROP POLICY IF EXISTS p_survey_responses_tenant_isolation ON public.survey_responses;
CREATE POLICY p_survey_responses_tenant_isolation ON public.survey_responses
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

DROP POLICY IF EXISTS p_surveys_tenant_isolation ON public.surveys;
CREATE POLICY p_surveys_tenant_isolation ON public.surveys
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

DROP POLICY IF EXISTS p_verifications_tenant_isolation ON public.verifications;
CREATE POLICY p_verifications_tenant_isolation ON public.verifications
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

DROP POLICY IF EXISTS p_state_risk_register_tenant_isolation ON public.state_risk_register;
CREATE POLICY p_state_risk_register_tenant_isolation ON public.state_risk_register
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

-- ── 3. Tenant isolation, text (slug) column ──
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

-- ── 4. reports (split: MOR via oversight, VSR operator-only) ──
DROP POLICY IF EXISTS p_reports_tenant_isolation ON public.reports;
CREATE POLICY p_reports_tenant_isolation ON public.reports
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    OR (
      report_type = 'mandatory'
      AND current_setting('app.current_role', true) = 'STATE_SMD'
      AND EXISTS (
        SELECT 1 FROM public.oversight_relationships o
        WHERE o.regulator_tenant_id =
                NULLIF(current_setting('app.current_tenant', true), '')::uuid
          AND o.operator_tenant_id = tenant_id
          AND o.effective_to IS NULL
      )
    )
  )
  WITH CHECK (
    current_setting('app.current_role', true) = 'SUPER_ADMIN'
    OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
  );

-- ── 5. Cross-tenant / state regulator (role-gated) ──
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

DROP POLICY IF EXISTS p_module_c_aggregates_national ON public.module_c_aggregates;
CREATE POLICY p_module_c_aggregates_national ON public.module_c_aggregates
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (tenant_id IS NULL AND current_setting('app.current_role', true) = 'STATE_SMD')
  WITH CHECK (tenant_id IS NULL AND current_setting('app.current_role', true) = 'STATE_SMD');

DROP POLICY IF EXISTS p_state_safety_performance_targets_caan ON public.state_safety_performance_targets;
CREATE POLICY p_state_safety_performance_targets_caan ON public.state_safety_performance_targets
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']))
  WITH CHECK (current_setting('app.current_role', true) = ANY (ARRAY['STATE_SMD','SUPER_ADMIN']));

