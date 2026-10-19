-- ============================================================================
-- 2D.2 — VSR reporter-contact store (schema + RLS).
--
-- Design of record: docs/step2/2D.1_reporter_contact_design.md §8, §16
-- (SME decisions 2026-10-19) and §17:
--   * VSR-only. Non-VSR (MOR) reporter identity stays on `reports` (Q1/Q6).
--   * 1:1 with a report; the contact is subordinate to the report (CASCADE).
--   * Custody of a report's reporter contact is the TENANT_ADMIN of the
--     report's tenant — no STATE_ADMIN path, no named-custodian column, no
--     fallback, no SUPER_ADMIN break-glass (Q4/Q5/Q7).
--   * Reports are tenant-scoped by construction; the state regulator sees
--     aggregates, never individual reports or reporter identity (Q7/§17).
--
-- RLS: enabled (not forced — the Phase 2C convention: the app connects as a
-- non-owner `authenticated` role, so the owner-bypass is not reachable from the
-- app path; verified against the live RLS state).
--
-- Idempotent: safe to re-run (IF NOT EXISTS / DROP POLICY IF EXISTS).
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.reporter_contacts (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id                 UUID NOT NULL UNIQUE
                                  REFERENCES public.reports (id) ON DELETE CASCADE,
    tenant_id                 UUID NOT NULL
                                  REFERENCES public.tenants (id),
    reporter_name             TEXT,
    reporter_email            TEXT,
    reporter_phone            TEXT,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_reporter_contacts_tenant
    ON public.reporter_contacts (tenant_id);

COMMENT ON TABLE public.reporter_contacts
    IS '2D.2: VSR reporter contact (1:1). Custodied by the report tenant''s '
       'TENANT_ADMIN; never read by STATE_ADMIN/SUPER_ADMIN.';
COMMENT ON COLUMN public.reporter_contacts.reporter_email
    IS '2D.2: VSR reporter contact PII (nullable — a VSR may be anonymous).';

ALTER TABLE public.reporter_contacts ENABLE ROW LEVEL SECURITY;

-- ── Custodian read/write: the TENANT_ADMIN of the report's tenant. ──────────
-- Single form per SME decision Q7: tenant scope + role, no state GUC and no
-- department GUC. Everyone else (STATE_SMD, SUPER_ADMIN, OFFICER, DEPT_ADMIN,
-- STAFF, and every cross-tenant role) sees 0 rows.
DROP POLICY IF EXISTS reporter_contacts_tenant_admin ON public.reporter_contacts;
CREATE POLICY reporter_contacts_tenant_admin ON public.reporter_contacts
    AS PERMISSIVE
    FOR ALL
    TO authenticated
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        AND current_setting('app.current_role', true) = 'TENANT_ADMIN'
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        AND current_setting('app.current_role', true) = 'TENANT_ADMIN'
    );

-- ── Submission write path ───────────────────────────────────────────────────
-- The reporter who files a VSR is an ordinary tenant member (STAFF/OFFICER/…),
-- not a TENANT_ADMIN, so the custodial policy above cannot admit the INSERT.
-- The app writes the contact row exactly once, at submission, for the report's
-- own tenant (ReportService.create_report). This permissive INSERT policy
-- admits that write and nothing else: SELECT/UPDATE/DELETE remain gated by the
-- custodial policy above (a FOR INSERT policy does not apply to SELECT).
DROP POLICY IF EXISTS reporter_contacts_submission_insert ON public.reporter_contacts;
CREATE POLICY reporter_contacts_submission_insert ON public.reporter_contacts
    AS PERMISSIVE
    FOR INSERT
    TO authenticated
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    );

-- ── Grants (table-level; RLS still governs every row) ──────────────────────
GRANT ALL ON TABLE public.reporter_contacts TO anon, authenticated, service_role;
