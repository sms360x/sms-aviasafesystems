-- ============================================================================
-- 2A.3b-fix — align tenants.contact_email / tenants.contact_phone to
-- character varying (matching public.regulators).
--
-- Part of the approved 2A.3b Option 2 that was not applied in the phase-1
-- commit (f7d8dce). Data-preserving: text -> varchar with no length limit is
-- lossless in Postgres. No code change; no data migration; regulators
-- unchanged.
-- ============================================================================

ALTER TABLE public.tenants
  ALTER COLUMN contact_email TYPE character varying,
  ALTER COLUMN contact_phone TYPE character varying;
