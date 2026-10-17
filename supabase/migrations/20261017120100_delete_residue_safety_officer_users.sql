-- ============================================================================
-- 2C.7 — delete residue SAFETY_OFFICER users (test pollution)
--
-- The RLS adversarial/governance test helpers (backend/tests/_mbb.py,
-- create_user) insert users with the DEFAULT role 'SAFETY_OFFICER', email
-- '<uid>@test.local', under throwaway tenants 'rls-op-*'. Best-effort cleanup
-- stranded 10 of them (the residue the SME reviewed on 2026-10-17).
--
-- They are NOT real users; the three real Safety Department officers already
-- carry the canonical role 'OFFICER' and department 'safety'. Delete the
-- residue. No Firebase Auth change is performed here: these synthetic uids
-- (e.g. 'u-member-<hex>') were never Firebase accounts (the Firebase deletion
-- is attempted separately by the item's runner and is a no-op for absent uids).
--
-- Idempotent: a re-run affects 0 rows.
-- ============================================================================

DELETE FROM public.users
WHERE role = 'SAFETY_OFFICER'
  AND email LIKE '%@test.local';
