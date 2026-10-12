-- ============================================================================
-- 2B.3 — migrate stored role values to canonical names
--
-- Rewrites legacy role literals to their canonical form in the two role
-- stores: public.users.role and public.memberships.role. (Firebase custom
-- claims are migrated separately by scripts/migrate_role_claims.py.)
--
-- Idempotent: the WHERE guard means a re-run affects 0 rows.
-- Reversible: see docs/step2/2B.3_role_migration.md (rollback reverses the map).
--
-- Map:
--   CAAN_SMD       -> STATE_SMD
--   SAFETY_OFFICER -> OFFICER
--   AIRLINE_ADMIN  -> TENANT_ADMIN
--   USER           -> STAFF
--   CAMO_ADMIN     -> DEPT_ADMIN
--   CAMO_USER      -> STAFF
--   QA_ADMIN       -> DEPT_ADMIN
--   QA_USER        -> STAFF
--   CAAN_INSPECTOR -> STATE_SMD
--   CAAN_ADMIN     -> STATE_SMD
--   CAAN_AUDITOR   -> STATE_SMD
--   SAG_MEMBER     -> STAFF
-- ============================================================================

UPDATE public.users
SET role = CASE role
    WHEN 'CAAN_SMD'       THEN 'STATE_SMD'
    WHEN 'SAFETY_OFFICER' THEN 'OFFICER'
    WHEN 'AIRLINE_ADMIN'  THEN 'TENANT_ADMIN'
    WHEN 'USER'           THEN 'STAFF'
    WHEN 'CAMO_ADMIN'     THEN 'DEPT_ADMIN'
    WHEN 'CAMO_USER'      THEN 'STAFF'
    WHEN 'QA_ADMIN'       THEN 'DEPT_ADMIN'
    WHEN 'QA_USER'        THEN 'STAFF'
    WHEN 'CAAN_INSPECTOR' THEN 'STATE_SMD'
    WHEN 'CAAN_ADMIN'     THEN 'STATE_SMD'
    WHEN 'CAAN_AUDITOR'   THEN 'STATE_SMD'
    WHEN 'SAG_MEMBER'     THEN 'STAFF'
    ELSE role
END
WHERE role IN (
    'CAAN_SMD','SAFETY_OFFICER','AIRLINE_ADMIN','USER',
    'CAMO_ADMIN','CAMO_USER','QA_ADMIN','QA_USER',
    'CAAN_INSPECTOR','CAAN_ADMIN','CAAN_AUDITOR','SAG_MEMBER'
);

UPDATE public.memberships
SET role = CASE role
    WHEN 'CAAN_SMD'       THEN 'STATE_SMD'
    WHEN 'SAFETY_OFFICER' THEN 'OFFICER'
    WHEN 'AIRLINE_ADMIN'  THEN 'TENANT_ADMIN'
    WHEN 'USER'           THEN 'STAFF'
    WHEN 'CAMO_ADMIN'     THEN 'DEPT_ADMIN'
    WHEN 'CAMO_USER'      THEN 'STAFF'
    WHEN 'QA_ADMIN'       THEN 'DEPT_ADMIN'
    WHEN 'QA_USER'        THEN 'STAFF'
    WHEN 'CAAN_INSPECTOR' THEN 'STATE_SMD'
    WHEN 'CAAN_ADMIN'     THEN 'STATE_SMD'
    WHEN 'CAAN_AUDITOR'   THEN 'STATE_SMD'
    WHEN 'SAG_MEMBER'     THEN 'STAFF'
    ELSE role
END
WHERE role IN (
    'CAAN_SMD','SAFETY_OFFICER','AIRLINE_ADMIN','USER',
    'CAMO_ADMIN','CAMO_USER','QA_ADMIN','QA_USER',
    'CAAN_INSPECTOR','CAAN_ADMIN','CAAN_AUDITOR','SAG_MEMBER'
);
