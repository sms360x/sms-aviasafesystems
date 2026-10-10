-- ============================================================================
-- 2A.3b — insert regulator rows into tenants (schema-only unification, phase 1)
--
-- Copies each public.regulators row into public.tenants with kind='regulator',
-- preserving the regulator's id as tenants.id (so 2A.3b-code can use the same
-- UUID in both tables) and setting tenants.tenant_id = the regulator slug.
-- Common columns carry straight across; the regulator's `website` column maps
-- to the new tenants.website column. Existing tenants rows are untouched.
--
-- The `regulators` table is NOT modified. Idempotent via the NOT EXISTS guard.
-- ============================================================================

INSERT INTO public.tenants (
    id, slug, tenant_id, name, country, kind,
    operator_tenant_ids, short_name, country_code, country_name, domain,
    status, is_demo, is_saas_customer, module_access, subscription_status,
    subscription_start, subscription_end, regulator_type, display_name,
    data, contact_email, contact_phone, website, created_at, updated_at
)
SELECT
    r.id, r.slug, r.slug, r.name, r.country_name, 'regulator',
    r.operator_tenant_ids, r.short_name, r.country_code, r.country_name, r.domain,
    r.status, r.is_demo, r.is_saas_customer, r.module_access, r.subscription_status,
    r.subscription_start, r.subscription_end, r.regulator_type, r.display_name,
    r.data, r.contact_email, r.contact_phone, r.website,
    COALESCE(r.created_at, now()), COALESCE(r.updated_at, now())
FROM public.regulators r
WHERE NOT EXISTS (
    SELECT 1 FROM public.tenants t WHERE t.id = r.id
);
