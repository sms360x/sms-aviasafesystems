-- ============================================================================
-- 2B.2 — tenants.safety_department_name
--
-- Additive, nullable column. The tenant-specific Safety Department name is
-- used by the department-based raw VSR / custodian rule (2B.1 Q6): a user with
-- role OFFICER and department matching this value gets raw VSR access.
-- NULL means the tenant has no department-based VSR access; only TENANT_ADMIN
-- gets it.
--
-- Idempotent: safe to re-run.
-- ============================================================================

ALTER TABLE public.tenants
  ADD COLUMN IF NOT EXISTS safety_department_name text NULL;

COMMENT ON COLUMN public.tenants.safety_department_name IS
  'Tenant-specific Safety Department name. Used for the department-based raw VSR rule (Q6). NULL means the tenant has no department-based VSR access; only TENANT_ADMIN gets it.';
