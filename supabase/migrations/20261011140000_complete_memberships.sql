-- ============================================================================
-- 2A.4-pre — complete the memberships source.
--
-- 1. Cascade-clean the test-residue cluster created by
--    test_hazard_triage::test_rejected_closes_hazard (tenant dd97df3a-…):
--      hazard_triage 18e067e4-…  (leaf)
--      hazards       c53f733c-…  (referenced only by that triage row)
--      users         f4de15a5-…  (referenced only by that triage row)
--    Deleted leaf-to-root. No other table references any of the three
--    (verified: all other FKs referencing hazards.id and hazard_triage.id are 0).
-- 2. Assign the regulator tenants to the two STATE_SMD orphans so the 2A.3
--    backfill can create their memberships.
--
-- The residue Firebase Auth user (uid `trirej-56fa2141`) is a synthetic test
-- uid deleted out-of-band (best-effort). The residue tenant row dd97df3a-…
-- is left in place (no memberships, and only the deleted rows referenced it).
-- ============================================================================

DELETE FROM public.hazard_triage
 WHERE id = '18e067e4-7bed-4a8c-83be-fa6fa8722c08';

DELETE FROM public.hazards
 WHERE id = 'c53f733c-3182-4024-8a45-31fe1f2b0e99';

DELETE FROM public.users
 WHERE id = 'f4de15a5-002f-4fb8-98e2-052dc0182318';

UPDATE public.users
   SET tenant_id = (
        SELECT id FROM public.tenants
        WHERE slug = 'caan' AND kind = 'regulator'
   )
 WHERE email = 'smd@caanepal.gov.np'
   AND role = 'STATE_SMD'
   AND tenant_id IS NULL;

UPDATE public.users
   SET tenant_id = (
        SELECT id FROM public.tenants
        WHERE slug = 'test-regulator' AND kind = 'regulator'
   )
 WHERE email = 'test-admin@examples.com'
   AND role = 'STATE_SMD'
   AND tenant_id IS NULL;
