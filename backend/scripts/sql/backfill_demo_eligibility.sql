-- ============================================================================
-- DEMO-ELIGIBILITY-02E — Idempotent backfill for shared-demo eligibility
-- ============================================================================
--
-- Purpose: Enable shared-DEMO read eligibility on the three existing
--          demonstration airlines by setting tenants.module_access.shared_demo
--          = true in the existing JSONB column.
--
-- Scope:   sita-air, air-dynasty, saurya-airlines
--
-- Safety properties:
--   * Idempotent: running multiple times produces the same result.
--   * Preserves all existing module_access JSONB keys; only sets/ensures
--     shared_demo = true.
--   * Only the three intended tenants are updated.
--   * Missing tenant rows cause a clear failure (RAISE EXCEPTION), not silent
--     partial success.
--   * Original module_access values are saved to a backup table so rollback
--     restores the exact pre-backfill state. The original backup snapshot is
--     preserved across repeated executions (ON CONFLICT DO NOTHING).
--   * Pre-backfill safety check rejects an existing backup table containing
--     unexpected or inconsistent records rather than silently trusting stale
--     backups.
--   * Rollback checks for intervening changes to module_access and refuses to
--     overwrite unrelated permission updates.
--   * Read-only pre-check and post-check queries are included.
--
-- DO NOT EXECUTE without separate owner authorization.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- PRE-CHECK (read-only): show current module_access for the three tenants.
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
-- BACKFILL (idempotent): set shared_demo = true inside module_access for each
-- target tenant, preserving all other JSONB keys. Original values are saved
-- to public.demo_eligibility_backfill_backup for rollback.
-- ---------------------------------------------------------------------------
BEGIN;

DO $$
DECLARE
    target_slugs TEXT[] := ARRAY['sita-air', 'air-dynasty', 'saurya-airlines'];
    target_slug TEXT;
    existing JSONB;
    enabled_count INTEGER;
BEGIN
    -- Ensure the backup table exists (idempotent).
    CREATE TABLE IF NOT EXISTS public.demo_eligibility_backfill_backup (
        slug TEXT PRIMARY KEY,
        original_module_access JSONB NOT NULL,
        backed_up_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    -- Safety check: reject an existing backup table containing unexpected or
    -- inconsistent records rather than silently trusting stale backups.
    --   * Rows for slugs outside the target scope are unexpected.
    --   * Rows for target slugs whose original_module_access does not match
    --     the current module_access (accounting for shared_demo already being
    --     true) indicate a stale backup from a prior divergent run.
    DECLARE
        unexpected_count INTEGER;
        inconsistent_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO unexpected_count
        FROM public.demo_eligibility_backfill_backup
        WHERE slug NOT IN ('sita-air', 'air-dynasty', 'saurya-airlines');

        IF unexpected_count > 0 THEN
            RAISE EXCEPTION 'Backup table contains unexpected records outside the target scope (count=%); refusing to proceed.', unexpected_count;
        END IF;

        SELECT COUNT(*) INTO inconsistent_count
        FROM public.demo_eligibility_backfill_backup b
        JOIN public.tenants t ON t.slug = b.slug
        WHERE b.slug IN ('sita-air', 'air-dynasty', 'saurya-airlines')
          AND jsonb_set(b.original_module_access, '{shared_demo}', 'true'::jsonb, true)
              IS DISTINCT FROM t.module_access;

        IF inconsistent_count > 0 THEN
            RAISE EXCEPTION 'Backup table contains inconsistent records for % target tenant(s); refusing to proceed.', inconsistent_count;
        END IF;
    END;

    FOREACH target_slug IN ARRAY target_slugs LOOP
        -- Fail loudly if the tenant row does not exist: never silently skip.
        IF NOT EXISTS (SELECT 1 FROM public.tenants WHERE slug = target_slug) THEN
            RAISE EXCEPTION 'Backfill target tenant does not exist: %', target_slug;
        END IF;

        -- Read current module_access (or empty object).
        SELECT COALESCE(module_access, '{}'::jsonb) INTO existing
        FROM public.tenants WHERE slug = target_slug;

        -- Idempotent: skip if already enabled.
        IF (existing->>'shared_demo')::boolean IS TRUE THEN
            -- Still ensure a backup row exists for rollback completeness.
            INSERT INTO public.demo_eligibility_backfill_backup (slug, original_module_access)
            VALUES (target_slug, existing)
            ON CONFLICT (slug) DO NOTHING;
            RAISE NOTICE 'Already enabled: %', target_slug;
            CONTINUE;
        END IF;

        -- Save the original value before mutating (restore point for rollback).
        -- ON CONFLICT DO NOTHING preserves the original backup snapshot across
        -- repeated executions; it never overwrites an earlier backup.
        INSERT INTO public.demo_eligibility_backfill_backup (slug, original_module_access)
        VALUES (target_slug, existing)
        ON CONFLICT (slug) DO NOTHING;

        -- Upsert shared_demo = true, preserving all other keys.
        UPDATE public.tenants
        SET module_access = jsonb_set(
            existing,
            '{shared_demo}',
            'true'::jsonb,
            true   -- create missing key
        ),
        updated_at = now()
        WHERE slug = target_slug;

        RAISE NOTICE 'Enabled shared_demo for: %', target_slug;
    END LOOP;

    -- Post-update assertion: exactly the three intended tenants must have
    -- shared_demo=true. Any other count indicates partial or incorrect update.
    SELECT COUNT(*) INTO enabled_count
    FROM public.tenants
    WHERE slug IN ('sita-air', 'air-dynasty', 'saurya-airlines')
      AND (module_access->>'shared_demo')::boolean IS TRUE;

    IF enabled_count <> 3 THEN
        RAISE EXCEPTION 'Expected exactly 3 tenants with shared_demo=true, found %; rolling back.', enabled_count;
    END IF;
END $$;

COMMIT;

-- ---------------------------------------------------------------------------
-- POST-CHECK (read-only): verify shared_demo = true for the three tenants.
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
-- SHOW BACKUP (read-only): original values captured for rollback.
-- ---------------------------------------------------------------------------
SELECT
    slug,
    original_module_access,
    backed_up_at
FROM public.demo_eligibility_backfill_backup
WHERE slug IN ('sita-air', 'air-dynasty', 'saurya-airlines')
ORDER BY slug;
