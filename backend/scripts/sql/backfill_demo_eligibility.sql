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
--     restores the exact pre-backfill state.
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
DO $$
DECLARE
    target_slugs TEXT[] := ARRAY['sita-air', 'air-dynasty', 'saurya-airlines'];
    target_slug TEXT;
    existing JSONB;
BEGIN
    -- Ensure the backup table exists (idempotent).
    CREATE TABLE IF NOT EXISTS public.demo_eligibility_backfill_backup (
        slug TEXT PRIMARY KEY,
        original_module_access JSONB NOT NULL,
        backed_up_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

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
        INSERT INTO public.demo_eligibility_backfill_backup (slug, original_module_access)
        VALUES (target_slug, existing)
        ON CONFLICT (slug) DO UPDATE SET
            original_module_access = EXCLUDED.original_module_access,
            backed_up_at = now();

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
END $$;

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
