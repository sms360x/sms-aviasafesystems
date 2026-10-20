-- ============================================================================
-- 2D.2.1 — VSR anonymity: nullable `reports.created_by` + definer write path.
--
-- Design of record: 2D.1 §16/§17 and the 2D.2.1 SME decisions (2026-10-20).
--
--   * A VSR is anonymous at the database layer. `reports.created_by` is NULL
--     for every VSR, identified or not; MOR keeps the submitter uid.
--   * `reporter_contacts` is still custodied by the report tenant's
--     TENANT_ADMIN, but the submission write no longer depends on the
--     submitter holding a safety role. Any authenticated tenant member may
--     file a VSR, so the write goes through `submit_vsr_contact()`, a
--     SECURITY DEFINER function that validates the report and its tenant and
--     performs the insert. Direct inserts by `authenticated` are denied.
--
-- Idempotent: safe to re-run.
-- ============================================================================

-- ── 1. Anonymous VSR report rows ────────────────────────────────────────────
ALTER TABLE public.reports ALTER COLUMN created_by DROP NOT NULL;

-- Existing VSR rows (all dummy data) carry no submitter linkage any more.
UPDATE public.reports
   SET created_by = NULL
 WHERE report_type = 'voluntary'
   AND created_by IS NOT NULL;

COMMENT ON COLUMN public.reports.created_by
    IS '2D.2.1: NULL for every VSR (anonymous by construction); the submitter '
       'uid for MOR. Never used to link a reporter contact to a person.';

-- ── 2. Custodian read policy (SELECT only) ──────────────────────────────────
-- Reads remain TENANT_ADMIN-of-the-report's-tenant. There is deliberately no
-- INSERT/UPDATE/DELETE policy for `authenticated`: all writes go through the
-- SECURITY DEFINER function below, so a direct table insert fails.
DROP POLICY IF EXISTS reporter_contacts_tenant_admin ON public.reporter_contacts;
DROP POLICY IF EXISTS reporter_contacts_insert_safety_officer ON public.reporter_contacts;
DROP POLICY IF EXISTS reporter_contacts_submission_insert ON public.reporter_contacts;
CREATE POLICY reporter_contacts_tenant_admin ON public.reporter_contacts
    AS PERMISSIVE
    FOR SELECT
    TO authenticated
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        AND current_setting('app.current_role', true) = 'TENANT_ADMIN'
    );

-- ── 3. Submission write path (SECURITY DEFINER) ─────────────────────────────
-- Validates:
--   * the report exists and is a VSR (`voluntary`);
--   * the report's tenant equals the supplied tenant;
--   * when a request identity is present, the tenant matches it.
-- Then upserts the 1:1 contact row, bypassing RLS as the function owner.
CREATE OR REPLACE FUNCTION public.submit_vsr_contact(
    p_report_id       uuid,
    p_tenant_id       uuid,
    p_reporter_name   text,
    p_reporter_email  text,
    p_reporter_phone  text
) RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_report_tenant uuid;
    v_report_type   text;
    v_contact_id    uuid;
    v_caller_tenant uuid;
BEGIN
    SELECT tenant_id, report_type
      INTO v_report_tenant, v_report_type
      FROM public.reports
     WHERE id = p_report_id;

    IF v_report_tenant IS NULL THEN
        RAISE EXCEPTION 'report not found';
    END IF;
    IF v_report_type <> 'voluntary' THEN
        RAISE EXCEPTION 'reporter_contacts is VSR-only';
    END IF;
    IF v_report_tenant <> p_tenant_id THEN
        RAISE EXCEPTION 'tenant mismatch';
    END IF;

    -- Bind the write to the request tenant when an RLS identity is present.
    v_caller_tenant := NULLIF(current_setting('app.current_tenant', true), '')::uuid;
    IF v_caller_tenant IS NOT NULL AND v_caller_tenant <> p_tenant_id THEN
        RAISE EXCEPTION 'cross-tenant contact write denied';
    END IF;

    INSERT INTO public.reporter_contacts
        (report_id, tenant_id, reporter_name, reporter_email, reporter_phone)
    VALUES
        (p_report_id, p_tenant_id, p_reporter_name, p_reporter_email,
         p_reporter_phone)
    ON CONFLICT (report_id) DO UPDATE
       SET reporter_name  = EXCLUDED.reporter_name,
           reporter_email = EXCLUDED.reporter_email,
           reporter_phone = EXCLUDED.reporter_phone,
           updated_at     = now()
    RETURNING id INTO v_contact_id;

    RETURN v_contact_id;
END;
$$;

REVOKE ALL ON FUNCTION
    public.submit_vsr_contact(uuid, uuid, text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    public.submit_vsr_contact(uuid, uuid, text, text, text) TO authenticated;
GRANT EXECUTE ON FUNCTION
    public.submit_vsr_contact(uuid, uuid, text, text, text) TO service_role;

-- ── 4. Audit append (required for the VSR_SUBMITTED event) ──────────────────
-- `audit_logs` had RLS enabled with only a SUPER_ADMIN SELECT policy, so every
-- INSERT from the `authenticated` app role was denied and audit events were
-- silently dropped (log_audit is best-effort by design). This is append-only
-- and tenant-scoped; reads remain SUPER_ADMIN-only.
DROP POLICY IF EXISTS audit_logs_insert_authenticated ON public.audit_logs;
CREATE POLICY audit_logs_insert_authenticated ON public.audit_logs
    AS PERMISSIVE
    FOR INSERT
    TO authenticated
    WITH CHECK (
        tenant_id IS NULL
        OR tenant_id = current_setting('app.current_tenant_slug', true)
        OR current_setting('app.current_role', true) = 'SUPER_ADMIN'
    );
