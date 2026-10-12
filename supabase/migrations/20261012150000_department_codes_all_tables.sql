-- ============================================================================
-- 2B.4a — migrate department values to canonical codes (all tables)
--
-- The canonical department vocabulary is codes (app/core/config.py
-- DEPARTMENT_CODES). This rewrites the legacy label/variant strings to codes in
-- every table that stores a department:
--   users.department, hazards.department, cans.department, caps.department.
--
-- Idempotent: the WHERE guards mean a re-run affects 0 rows.
-- No schema change. Reversible: see docs/step2/2B.4a_department_model.md.
--
-- The residue test user trirev-f5d6908e@test.local is deleted separately
-- (Firebase Auth + users); it is not handled here.
-- ============================================================================

-- users.department : label/variant -> code (empty/NULL left untouched)
UPDATE public.users
SET department = CASE department
    WHEN 'CAMO'                       THEN 'camo'
    WHEN 'Corporate Safety Department' THEN 'safety'
    WHEN 'Flight Operations'          THEN 'flight_ops'
    WHEN 'Flight Ops'                 THEN 'flight_ops'
    WHEN 'Part 145'                   THEN 'maintenance_145'
    WHEN 'Part 145/AMO'               THEN 'maintenance_145'
    WHEN 'Safety Management Department' THEN 'safety'
    WHEN 'Safety Management Division'   THEN 'smd'
    ELSE department
END
WHERE department IN (
    'CAMO','Corporate Safety Department','Flight Operations','Flight Ops',
    'Part 145','Part 145/AMO','Safety Management Department',
    'Safety Management Division'
);

-- Safety Department officers: empty/NULL -> 'safety' (AE / SUPER_ADMIN stay empty)
UPDATE public.users
SET department = 'safety'
WHERE email IN (
    'safety@air-dynasty.com.np',
    'safety@saurya.com.np',
    'safety@sitaair.com.np'
)
AND (department IS NULL OR department = '');

-- hazards.department : label -> code
UPDATE public.hazards
SET department = CASE department
    WHEN 'CAMO'              THEN 'camo'
    WHEN 'Flight Operations' THEN 'flight_ops'
    WHEN 'Part-145'          THEN 'maintenance_145'
    ELSE department
END
WHERE department IN ('CAMO','Flight Operations','Part-145');

-- cans.department : label -> code
UPDATE public.cans
SET department = CASE department
    WHEN 'CAMO'              THEN 'camo'
    WHEN 'Flight Operations' THEN 'flight_ops'
    WHEN 'Part-145'          THEN 'maintenance_145'
    ELSE department
END
WHERE department IN ('CAMO','Flight Operations','Part-145');

-- caps.department : label -> code
UPDATE public.caps
SET department = CASE department
    WHEN 'CAMO'              THEN 'camo'
    WHEN 'Flight Operations' THEN 'flight_ops'
    WHEN 'Part-145'          THEN 'maintenance_145'
    ELSE department
END
WHERE department IN ('CAMO','Flight Operations','Part-145');
