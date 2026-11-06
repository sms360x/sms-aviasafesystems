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
--   * Read-only pre-check and post-check queries are included.
--   * Drops the backup table after a successful restore.
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

        -- Restore the exact original module_access value.
        UPDATE public.tenants
        SET module_access = backup_row.original_module_access,
            updated_at = now()
        WHERE slug = target_slug;

        RAISE NOTICE 'Restored module_access for: %', target_slug;
    END LOOP;

    -- Drop the backup table after successful restore.
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
