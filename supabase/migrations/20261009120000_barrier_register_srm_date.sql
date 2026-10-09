-- ============================================================================
-- 1B.4 — barrier_register.srm_date (CAAN SRM Manual §2.3.4)
--
-- Purely additive: one nullable date column on the existing table. No existing
-- column changes, no data migration, no backfill. The column is populated when
-- a barrier is created or edited (later item); existing rows remain NULL.
-- ============================================================================

ALTER TABLE public.barrier_register
    ADD COLUMN IF NOT EXISTS srm_date date NULL;

COMMENT ON COLUMN public.barrier_register.srm_date IS
    'CAAN SRM Manual §2.3.4 SRM Date.';
