-- ============================================================================
-- 2A.3b-cleanup — retire the `regulators` table.
--
-- The ORM no longer reads or writes `regulators` (Regulator is a Tenant
-- subclass via single-table inheritance — 2A.3b-code). This renames the table
-- to `regulators_old`, which is RETAINED for one commit cycle as a rollback
-- point and dropped in a later item.
--
-- No view is created (the ORM does not use the name). No FK references
-- regulators.id, so nothing else changes.
-- ============================================================================

ALTER TABLE public.regulators RENAME TO regulators_old;
