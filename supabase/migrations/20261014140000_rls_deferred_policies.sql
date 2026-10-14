-- ============================================================================
-- 2C.4 — RLS policies for the 10 tables that had RLS enabled and no policy
--
-- Per docs/step2/2C.1_rls_design.md §12:
--   Operator-only, uuid tenant_id (6): hazard_assessments, hazard_capas,
--       hazard_rca_entries, hazard_rca_factors, feedback, invites
--   Operator-only, text tenant_id (1): audit_dispatches  -> slug template
--   Operator-only, EXISTS-scoped (1):  psoe_findings     -> via psoe_assessments
--   Platform, SUPER_ADMIN-only (1):    memberships
--   Shared (1):                        oversight_relationships
--
-- No regulator-oversight branch on the Operator-only tables (§6 Q6). The
-- oversight branch stays on the Outcome-visible / Mandatory-report tables only.
-- No schema change; policy DDL only. Idempotent (DROP POLICY IF EXISTS).
-- ============================================================================

-- ── Operator-only, uuid tenant_id ──────────────────────────────────────────

DROP POLICY IF EXISTS hazard_assessments_tenant_isolation ON public.hazard_assessments;
CREATE POLICY hazard_assessments_tenant_isolation ON public.hazard_assessments
    FOR ALL TO authenticated
    USING (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    );

DROP POLICY IF EXISTS hazard_capas_tenant_isolation ON public.hazard_capas;
CREATE POLICY hazard_capas_tenant_isolation ON public.hazard_capas
    FOR ALL TO authenticated
    USING (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    );

DROP POLICY IF EXISTS hazard_rca_entries_tenant_isolation ON public.hazard_rca_entries;
CREATE POLICY hazard_rca_entries_tenant_isolation ON public.hazard_rca_entries
    FOR ALL TO authenticated
    USING (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    );

DROP POLICY IF EXISTS hazard_rca_factors_tenant_isolation ON public.hazard_rca_factors;
CREATE POLICY hazard_rca_factors_tenant_isolation ON public.hazard_rca_factors
    FOR ALL TO authenticated
    USING (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    );

DROP POLICY IF EXISTS feedback_tenant_isolation ON public.feedback;
CREATE POLICY feedback_tenant_isolation ON public.feedback
    FOR ALL TO authenticated
    USING (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    );

DROP POLICY IF EXISTS invites_tenant_isolation ON public.invites;
CREATE POLICY invites_tenant_isolation ON public.invites
    FOR ALL TO authenticated
    USING (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    );

-- ── Operator-only, text (slug) tenant_id ───────────────────────────────────

DROP POLICY IF EXISTS audit_dispatches_tenant_isolation ON public.audit_dispatches;
CREATE POLICY audit_dispatches_tenant_isolation ON public.audit_dispatches
    FOR ALL TO authenticated
    USING (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_slug', true), '')
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_slug', true), '')
    );

-- ── Operator-only, EXISTS-scoped via psoe_assessments ──────────────────────

DROP POLICY IF EXISTS psoe_findings_tenant_isolation ON public.psoe_findings;
CREATE POLICY psoe_findings_tenant_isolation ON public.psoe_findings
    FOR ALL TO authenticated
    USING (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR EXISTS (
            SELECT 1 FROM public.psoe_assessments a
            WHERE a.id = psoe_findings.assessment_id
              AND a.tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR EXISTS (
            SELECT 1 FROM public.psoe_assessments a
            WHERE a.id = psoe_findings.assessment_id
              AND a.tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
    );

-- ── Platform — Super-Admin reporting substrate ─────────────────────────────

DROP POLICY IF EXISTS memberships_super_admin_only ON public.memberships;
CREATE POLICY memberships_super_admin_only ON public.memberships
    FOR ALL TO authenticated
    USING (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
    );

-- ── Shared — regulator / operator links ────────────────────────────────────

DROP POLICY IF EXISTS oversight_relationships_shared ON public.oversight_relationships;
CREATE POLICY oversight_relationships_shared ON public.oversight_relationships
    FOR ALL TO authenticated
    USING (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
        OR regulator_tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        OR operator_tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'SUPER_ADMIN'
    );
