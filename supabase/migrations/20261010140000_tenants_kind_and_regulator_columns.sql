-- ============================================================================
-- 2A.3b — tenants.kind + regulator-specific columns (schema-only unification, phase 1)
--
-- Purely additive to `public.tenants`: a `kind` discriminator plus the columns
-- that exist on `public.regulators` but not yet on `public.tenants`. The
-- `regulators` table is left untouched, no FK is migrated, no view is created,
-- no RLS policy is added, and no code changes. Existing tenants rows keep
-- kind = 'operator' (the column default).
--
-- Common columns already present on tenants are NOT re-added here:
--   id, name, status, is_demo, created_at, updated_at, module_access, data,
--   slug, contact_email, contact_phone.
-- NOTE: contact_email / contact_phone are `character varying` on regulators and
-- `text` on tenants — a compatible string-type variance left as-is (no type
-- change in this item).
--
-- Idempotent: safe to re-run (IF NOT EXISTS).
-- ============================================================================

ALTER TABLE public.tenants
  ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'operator';

CREATE INDEX IF NOT EXISTS tenants_kind ON public.tenants (kind);

COMMENT ON COLUMN public.tenants.kind IS
  'Tenant category. Canonical values in
   backend/app/core/config.py TENANT_KINDS. Not a CHECK
   constraint; the list is expected to grow.';

-- Regulator-only columns (actual names/types from the live schema).
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS operator_tenant_ids jsonb;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS short_name text;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS country_code text;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS country_name text;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS domain text;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS is_saas_customer boolean;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS subscription_status varchar;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS subscription_start date;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS subscription_end date;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS regulator_type varchar;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS display_name varchar;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS website varchar;
