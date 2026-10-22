-- Step-3 role cleanup — retire the named-custodian column.
--
-- Custody of a VSR reporter contact is no longer a named column on `reports`;
-- it is the TENANT_ADMIN of the report's own tenant, enforced through the
-- SECURITY DEFINER `reporter_contacts` write path (2D.2). The
-- `confidential_custodian_id` column is unused and removed.
ALTER TABLE public.reports DROP COLUMN IF EXISTS confidential_custodian_id;
