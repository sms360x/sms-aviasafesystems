-- ============================================================================
-- DEMO-ELIGIBILITY-02E — Rollback for shared-demo eligibility backfill
-- ============================================================================
--
-- Purpose: Restore tenants.module_access to its pre-backfill state for the
--          three demonstration airlines, using values saved by the backfill
--          script in public.demo_eligibility_backfill_backup.
--
-- Scope:   sita-air, air-dynasty, saurya-airlines
--
-- Safety properties:
--   * Restores the exact original module_access values (does not assume
--     shared_demo was previously false or absent).
--   * Only the three intended tenants are touched.
--   * Missing backup rows cause a clear failure (RAISE EXCEPTION).
--   * Refuses to overwrite unrelated permission updates: if module_access has
--     been changed since the backfill (intervening changes), rollback aborts
--     and the backup table is preserved (transaction rollback prevents the
--     DROP TABLE from executing).
--   * Read-only pre-check and post-check queries are included.
--   * Drops the backup table only after a successful restore.
--
-- DO NOT EXECUTE without separate owner authorization.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- PRE-CHECK (read-only): show current module_access and backup values.
-- ---------------------------------------------------------------------------
SELECT
    t.slug,
    t.name,
    t.status,
    t.active,
    t.module_access AS current_module_access,
    t.module_access->>'shared_demo' AS current_shared_demo_flag,
    b.original_module_access,
    b.backed_up_at
FROM public.tenants t
FULL JOIN public.demo_eligibility_backfill_backup b ON b.slug = t.slug
WHERE t.slug IN ('sita-air', 'air-dynasty', 'saurya-airlines')
   OR b.slug IN ('sita-air', 'air-dynasty', 'saurya-airlines')
ORDER BY COALESCE(t.slug, b.slug);

-- ---------------------------------------------------------------------------
-- ROLLBACK: restore original module_access values from the backup table.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    target_slugs TEXT[] := ARRAY['sita-air', 'air-dynasty', 'saurya-airlines'];
    target_slug TEXT;
    backup_row RECORD;
BEGIN
    FOREACH target_slug IN ARRAY target_slugs LOOP
        -- Fail loudly if no backup row exists for this tenant.
        SELECT * INTO backup_row
        FROM public.demo_eligibility_backfill_backup
        WHERE slug = target_slug;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'No backup row found for tenant: % (cannot safely roll back)', target_slug;
        END IF;

        -- Safety check: refuse to overwrite unrelated permission updates.
        -- Compare current module_access against the expected post-backfill
        -- state (original + shared_demo=true). If they differ, another process
        -- changed module_access after the backfill; abort to avoid clobbering
        -- those unrelated updates.
        DECLARE
            expected_module_access JSONB;
            intervening_count INTEGER;
        BEGIN
            expected_module_access := jsonb_set(
                backup_row.original_module_access,
                '{shared_demo}',
                'true'::jsonb,
                true
            );

            SELECT COUNT(*) INTO intervening_count
            FROM public.tenants
            WHERE slug = target_slug
              AND module_access IS DISTINCT FROM expected_module_access;

            IF intervening_count > 0 THEN
                RAISE EXCEPTION 'Intervening changes detected on module_access for tenant %; refusing to roll back and overwrite unrelated permission updates.', target_slug;
            END IF;
        END;

        -- Restore the exact original module_access value.
        UPDATE public.tenants
        SET module_access = backup_row.original_module_access,
            updated_at = now()
        WHERE slug = target_slug;

        RAISE NOTICE 'Restored module_access for: %', target_slug;
    END LOOP;

    -- Drop the backup table only after all restores succeeded. If any RAISE
    -- EXCEPTION above fired, this transaction aborts and the DROP never
    -- executes, preserving the backup table for inspection.
    DROP TABLE IF EXISTS public.demo_eligibility_backfill_backup;
END $$;

-- ---------------------------------------------------------------------------
-- POST-CHECK (read-only): verify module_access restored for the three tenants.
-- ---------------------------------------------------------------------------
SELECT
    slug,
    name,
    status,
    active,
    module_access,
    module_access->>'shared_demo' AS shared_demo_flag
FROM public.tenants
WHERE slug IN ('sita-air', 'air-dynasty', 'saurya-airlines')
ORDER BY slug;

-- ---------------------------------------------------------------------------
-- VERIFY BACKUP REMOVED (read-only): confirm backup table no longer exists.
-- ---------------------------------------------------------------------------
SELECT
    table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name = 'demo_eligibility_backfill_backup';
