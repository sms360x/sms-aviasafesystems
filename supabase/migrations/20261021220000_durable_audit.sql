-- ============================================================================
-- Phase 2E.2 — Durable audit trail (Postgres, per-tenant HMAC-SHA256 chain)
--
--   * `durable_audit_logs` — append-only, tamper-evident audit table.
--   * `append_audit_event` — SECURITY DEFINER append function (only writer).
--   * `verify_durable_chain` — recomputes a tenant chain and returns the first
--     broken row id (NULL when valid).
--   * `durable_audit_no_mutate` — trigger forbidding UPDATE / DELETE.
--   * Backfill — one-time chronological copy of `audit_logs` (idempotent).
--
-- SME decisions (2E.1): drop IP entirely; SUPER_ADMIN-only reads; indefinite
-- retention; per-tenant chain; HMAC-SHA256 with AUDIT_HMAC_KEY; exempt from
-- demo/reset purge.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Global partition key for tenantless events (LOGIN, CAAN reads, STATE_SPT…).
-- Matches app/db/ids.py tenant_uuid('__global__').
CREATE TABLE IF NOT EXISTS public.durable_audit_logs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL,
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT now(),
    action        TEXT NOT NULL,
    actor_uid     TEXT,
    resource_type TEXT,
    resource_id   TEXT,
    metadata      JSONB,
    prev_hash     TEXT,
    current_hash  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_durable_audit_tenant
    ON public.durable_audit_logs (tenant_id, timestamp, id);
CREATE INDEX IF NOT EXISTS ix_durable_audit_action
    ON public.durable_audit_logs (action);

ALTER TABLE public.durable_audit_logs ENABLE ROW LEVEL SECURITY;

-- Reads: SUPER_ADMIN only. No INSERT policy (inserts go through the definer
-- function). No UPDATE/DELETE policy (append-only).
DROP POLICY IF EXISTS durable_audit_select_super ON public.durable_audit_logs;
CREATE POLICY durable_audit_select_super ON public.durable_audit_logs
    FOR SELECT
    TO authenticated
    USING (current_setting('app.current_role', true) = 'SUPER_ADMIN');

REVOKE ALL ON public.durable_audit_logs FROM authenticated;
GRANT SELECT ON public.durable_audit_logs TO authenticated;

-- ── Append function ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.append_audit_event(
    p_tenant_id     uuid,
    p_action        text,
    p_actor_uid     text,
    p_resource_type text,
    p_resource_id   text,
    p_metadata      jsonb,
    p_hmac_key      text
) RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
DECLARE
    v_prev_hash    text := 'GENESIS';
    v_event_data   text;
    v_current_hash text;
    v_id           uuid;
BEGIN
    -- Serialize per-tenant appends so two writers cannot read the same head.
    PERFORM pg_advisory_xact_lock(hashtext(p_tenant_id::text));

    SELECT current_hash INTO v_prev_hash
      FROM public.durable_audit_logs
     WHERE tenant_id = p_tenant_id
     ORDER BY timestamp DESC, id DESC
     LIMIT 1;

    IF v_prev_hash IS NULL THEN
        v_prev_hash := 'GENESIS';
    END IF;

    v_event_data := coalesce(p_action, '')
        || '|' || coalesce(p_resource_type, '')
        || '|' || coalesce(p_resource_id, '')
        || '|' || coalesce(p_metadata::text, '')
        || '|' || coalesce(p_actor_uid, '');

    v_current_hash := encode(
        hmac(convert_to(v_prev_hash || v_event_data, 'UTF8'),
             convert_to(coalesce(p_hmac_key, ''), 'UTF8'),
             'sha256'),
        'hex');

    INSERT INTO public.durable_audit_logs
        (tenant_id, action, actor_uid, resource_type, resource_id, metadata,
         prev_hash, current_hash)
    VALUES
        (p_tenant_id, p_action, p_actor_uid, p_resource_type, p_resource_id,
         p_metadata, v_prev_hash, v_current_hash)
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION public.append_audit_event(uuid, text, text, text, text, jsonb, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.append_audit_event(uuid, text, text, text, text, jsonb, text) TO authenticated;

-- ── Verify function ─────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.verify_durable_chain(
    p_tenant_id uuid,
    p_hmac_key  text
) RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
DECLARE
    r           record;
    v_prev_hash text := 'GENESIS';
    v_event_data text;
    v_expected  text;
BEGIN
    FOR r IN
        SELECT * FROM public.durable_audit_logs
         WHERE tenant_id = p_tenant_id
         ORDER BY timestamp ASC, id ASC
    LOOP
        IF r.prev_hash IS DISTINCT FROM v_prev_hash THEN
            RETURN r.id;
        END IF;

        v_event_data := coalesce(r.action, '')
            || '|' || coalesce(r.resource_type, '')
            || '|' || coalesce(r.resource_id, '')
            || '|' || coalesce(r.metadata::text, '')
            || '|' || coalesce(r.actor_uid, '');

        v_expected := encode(
            hmac(convert_to(coalesce(r.prev_hash, 'GENESIS') || v_event_data, 'UTF8'),
                 convert_to(coalesce(p_hmac_key, ''), 'UTF8'),
                 'sha256'),
            'hex');

        IF r.current_hash IS DISTINCT FROM v_expected THEN
            RETURN r.id;
        END IF;

        v_prev_hash := r.current_hash;
    END LOOP;

    RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION public.verify_durable_chain(uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.verify_durable_chain(uuid, text) TO authenticated;

-- ── Append-only trigger ─────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.durable_audit_no_mutate() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'durable_audit_logs is append-only (% forbidden)', TG_OP;
END;
$$;

DROP TRIGGER IF EXISTS durable_audit_no_mutate_trg ON public.durable_audit_logs;
CREATE TRIGGER durable_audit_no_mutate_trg
    BEFORE UPDATE OR DELETE ON public.durable_audit_logs
    FOR EACH ROW EXECUTE FUNCTION public.durable_audit_no_mutate();

-- ── One-time backfill of existing audit_logs ─────────────────────────────────
-- Idempotent: only runs when durable_audit_logs is empty. The HMAC key falls
-- back to the same dev-only literal the app uses when AUDIT_HMAC_KEY is unset,
-- so backfilled rows chain with subsequent app appends.
DO $$
DECLARE
    r     record;
    v_tid uuid;
    v_key text;
BEGIN
    IF (SELECT count(*) FROM public.durable_audit_logs) > 0 THEN
        RETURN;
    END IF;

    v_key := current_setting('app.audit_hmac_key', true);
    IF v_key IS NULL OR v_key = '' THEN
        v_key := 'dev-only-audit-hmac-key-2e2';
    END IF;

    FOR r IN
        SELECT * FROM public.audit_logs ORDER BY created_at, id
    LOOP
        v_tid := CASE
            WHEN r.tenant_id IS NULL
                THEN 'cdcf0284-a0e3-53aa-a133-7205e12f80c9'::uuid
            ELSE uuid_generate_v5(uuid_ns_dns(), 'tenant:' || r.tenant_id)
        END;

        PERFORM public.append_audit_event(
            v_tid, r.action, r.actor, r.target_type, r.target_id,
            coalesce(r.metadata_json, '{}'::jsonb), v_key);
    END LOOP;
END;
$$;
