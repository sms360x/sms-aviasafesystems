-- ============================================================================
-- 2A.2 — memberships + oversight_relationships (Step 2, W1 / D3, D15)
--
-- Purely additive: two new tables and their indexes. No existing column is
-- changed, no data is migrated, no row is written. The tables are inert until
-- Phase 2A.3 (backfill): nothing reads them yet.
--
-- RLS is ENABLED on both with no policies (default-deny for any non-owner
-- role); the real policies are deferred to Phase 2C per the Step 1 RLS
-- deferral (docs/step1/1B.2_rls_exemptions.md, docs/step1/rls_bypass_finding.md).
-- FORCE ROW LEVEL SECURITY is deliberately NOT set here (Phase 2C).
--
-- Idempotent: safe to re-run (IF NOT EXISTS).
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.memberships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    tenant_id uuid NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    role text NOT NULL,
    effective_from timestamptz NOT NULL,
    effective_to timestamptz NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memberships_user_effective
    ON public.memberships (user_id, effective_from DESC);

CREATE UNIQUE INDEX IF NOT EXISTS memberships_active_unique
    ON public.memberships (user_id, tenant_id, role)
    WHERE is_active AND effective_to IS NULL;

CREATE TABLE IF NOT EXISTS public.oversight_relationships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    regulator_tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    operator_tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    effective_from timestamptz NOT NULL,
    effective_to timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS oversight_relationships_active_unique
    ON public.oversight_relationships (regulator_tenant_id, operator_tenant_id)
    WHERE effective_to IS NULL;

CREATE INDEX IF NOT EXISTS oversight_relationships_regulator
    ON public.oversight_relationships (regulator_tenant_id);

CREATE INDEX IF NOT EXISTS oversight_relationships_operator
    ON public.oversight_relationships (operator_tenant_id);

ALTER TABLE public.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.oversight_relationships ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE public.memberships IS
    'Step 2 W1 (D3) effective-dated user memberships, single active context. Inert until 2A.3.';
COMMENT ON TABLE public.oversight_relationships IS
    'Step 2 W1 (D15/L9) one-to-many regulator->operator oversight relationships (tenant<->tenant). Inert until 2A.3.';
