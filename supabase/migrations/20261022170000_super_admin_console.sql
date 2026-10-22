-- ============================================================================
-- Phase 3A Task 2 — SUPER_ADMIN console (audit chain viewer + system configs)
--
--   1. `durable_audit_logs.actor_role` — the role the actor held when the
--      event was appended. The HMAC input is UNCHANGED, so every chain that
--      exists today still verifies byte-for-byte.
--   2. `append_audit_event(..., p_actor_role, ...)` — 8-arg form carries the
--      role. The 7-arg form is kept as a thin wrapper (actor_role = NULL) so
--      an app that rolls out before/after this migration keeps appending.
--   3. `admin_tenant_view()` — SUPER_ADMIN-only SECURITY DEFINER read view.
--      The `tenants` table is NOT readable by platform roles under the app's
--      RLS identity (its policies are tenant-scoped), so the console needs a
--      definer path to label audit rows and to list tenant config.
--   4. `set_tenant_config_key()` — SUPER_ADMIN-only SECURITY DEFINER write
--      path for permitted tenant config keys. It merges the new value (keeps
--      undeclared keys), syncs the derived camelCase mirror, and appends the
--      durable audit event in the SAME transaction (append_audit_event is
--      itself SECURITY DEFINER) so a config change can never land un-audited.
--
-- NON-GOALS (deliberately absent):
--   * no UPDATE/DELETE/INSERT path on durable_audit_logs (append-only, and the
--     `durable_audit_no_mutate_trg` trigger is untouched);
--   * no chain repair / backfill / re-hash endpoint;
--   * no reporter_contacts mutation, no impersonation, no break-glass.
-- ============================================================================

-- ── 1. Actor role on the durable trail ──────────────────────────────────────
ALTER TABLE public.durable_audit_logs ADD COLUMN IF NOT EXISTS actor_role TEXT;

-- Link lookups: the console resolves `prev_hash` -> predecessor row and
-- counts successors per event, both by (tenant_id, hash).
CREATE INDEX IF NOT EXISTS ix_durable_audit_prev
    ON public.durable_audit_logs (tenant_id, prev_hash);
CREATE INDEX IF NOT EXISTS ix_durable_audit_hash
    ON public.durable_audit_logs (tenant_id, current_hash);

-- Newest-first listing: the console pages the trail by (timestamp, id).
CREATE INDEX IF NOT EXISTS ix_durable_audit_ts
    ON public.durable_audit_logs (timestamp DESC, id DESC);

-- ── 2. Append function with the actor role ─────────────────────────────────
CREATE OR REPLACE FUNCTION public.append_audit_event(
    p_tenant_id     uuid,
    p_action        text,
    p_actor_uid     text,
    p_resource_type text,
    p_resource_id   text,
    p_metadata      jsonb,
    p_actor_role    text,
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

    -- NOTE: the hashed payload is intentionally unchanged. `actor_role` is
    -- evidence recorded alongside the event, not part of the signed body, so
    -- chains written before this migration keep verifying.
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
        (tenant_id, action, actor_uid, actor_role, resource_type, resource_id,
         metadata, prev_hash, current_hash)
    VALUES
        (p_tenant_id, p_action, p_actor_uid, p_actor_role, p_resource_type,
         p_resource_id, p_metadata, v_prev_hash, v_current_hash)
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION public.append_audit_event(uuid, text, text, text, text, jsonb, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.append_audit_event(uuid, text, text, text, text, jsonb, text, text) TO authenticated;

-- Backwards-compatible 7-arg wrapper (pre-3A.2 callers). Delegates with a
-- NULL actor role so the hash input stays identical to what it always was.
CREATE OR REPLACE FUNCTION public.append_audit_event(
    p_tenant_id     uuid,
    p_action        text,
    p_actor_uid     text,
    p_resource_type text,
    p_resource_id   text,
    p_metadata      jsonb,
    p_hmac_key      text
) RETURNS uuid
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
    SELECT public.append_audit_event(
        p_tenant_id, p_action, p_actor_uid, p_resource_type, p_resource_id,
        p_metadata, NULL::text, p_hmac_key);
$$;

REVOKE ALL ON FUNCTION public.append_audit_event(uuid, text, text, text, text, jsonb, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.append_audit_event(uuid, text, text, text, text, jsonb, text) TO authenticated;

-- ── 3. SUPER_ADMIN tenant read view ─────────────────────────────────────────
-- Labels audit rows (tenant_uuid -> slug/name) and backs the System Configs
-- tenant picker. Definer + explicit role gate: the function bypasses RLS, so
-- the gate has to live inside it.
-- The return signature changed after the first application of this file, so
-- the function is dropped first: CREATE OR REPLACE cannot alter a return type.
DROP FUNCTION IF EXISTS public.admin_tenant_view();

CREATE OR REPLACE FUNCTION public.admin_tenant_view()
RETURNS TABLE (
    slug         text,
    name         text,
    tenant_uuid  uuid,
    kind         text,
    status       text,
    module_flags jsonb,
    config       jsonb,
    survey_config jsonb
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
BEGIN
    IF current_setting('app.current_role', true) IS DISTINCT FROM 'SUPER_ADMIN' THEN
        RAISE EXCEPTION 'SUPER_ADMIN role required' USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT t.slug::text,
           t.name::text,
           uuid_generate_v5(uuid_ns_dns(), 'tenant:' || t.slug),
           t.kind::text,
           t.status::text,
           coalesce(nullif(t.modules, '{}'::jsonb),
                    nullif(t.module_access, '{}'::jsonb),
                    '{}'::jsonb),
           coalesce(t.data -> 'config', '{}'::jsonb),
           coalesce(t.data -> 'surveyConfig', '{}'::jsonb)
      FROM public.tenants t
     ORDER BY t.slug;
END;
$$;

REVOKE ALL ON FUNCTION public.admin_tenant_view() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.admin_tenant_view() TO authenticated;

-- ── 4. SUPER_ADMIN tenant config write path ─────────────────────────────────
-- Merges one permitted key into the tenant's config (or module flags), keeps
-- every undeclared key, refreshes the derived camelCase mirror, and appends
-- the durable audit event in the same transaction.
--
--   p_target        'config' | 'modules'
--   p_value         jsonb map of candidate values (only p_allowed_keys are read)
--   p_allowed_keys  text[] of permitted keys for this write
--   p_extra         jsonb derived mirror map (surveyConfig) — config target only
--   p_audit_key     the key being changed (recorded in the audit event)
--   p_audit_value   the new value of that key (recorded in the audit event)
CREATE OR REPLACE FUNCTION public.set_tenant_config_key(
    p_tenant_slug  text,
    p_target       text,
    p_value        jsonb,
    p_allowed_keys text[],
    p_extra        jsonb,
    p_audit_key    text,
    p_audit_value  jsonb,
    p_actor        text,
    p_actor_role   text,
    p_hmac_key     text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
DECLARE
    v_row     public.tenants%ROWTYPE;
    v_config  jsonb := '{}'::jsonb;
    v_survey  jsonb := '{}'::jsonb;
    v_modules jsonb := '{}'::jsonb;
    v_data    jsonb := '{}'::jsonb;
    v_key     text;
    v_applied jsonb := '{}'::jsonb;
BEGIN
    IF current_setting('app.current_role', true) IS DISTINCT FROM 'SUPER_ADMIN' THEN
        RAISE EXCEPTION 'SUPER_ADMIN role required' USING ERRCODE = '42501';
    END IF;

    IF p_target IS NULL OR p_target NOT IN ('config', 'modules') THEN
        RAISE EXCEPTION 'invalid config target: %', p_target USING ERRCODE = '22023';
    END IF;

    SELECT * INTO v_row
      FROM public.tenants
     WHERE slug = p_tenant_slug
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown tenant: %', p_tenant_slug USING ERRCODE = '22023';
    END IF;

    v_data := coalesce(v_row.data, '{}'::jsonb);

    IF p_target = 'config' THEN
        v_config := coalesce(v_data -> 'config', '{}'::jsonb);
        FOREACH v_key IN ARRAY coalesce(p_allowed_keys, ARRAY[]::text[]) LOOP
            IF p_value ? v_key THEN
                v_applied := v_applied || jsonb_build_object(v_key, p_value -> v_key);
            END IF;
        END LOOP;
        v_config := v_config || v_applied;

        -- Derived mirror (surveyConfig) — recomputed by the caller from the
        -- canonical config so both representations stay in step.
        v_survey := coalesce(v_data -> 'surveyConfig', '{}'::jsonb)
                    || coalesce(p_extra, '{}'::jsonb);

        UPDATE public.tenants
           SET data = v_data || jsonb_build_object('config', v_config,
                                                   'surveyConfig', v_survey),
               updated_at = now()
         WHERE slug = p_tenant_slug;
    ELSE
        v_modules := coalesce(v_row.modules, '{}'::jsonb);
        FOREACH v_key IN ARRAY coalesce(p_allowed_keys, ARRAY[]::text[]) LOOP
            IF p_value ? v_key THEN
                v_applied := v_applied || jsonb_build_object(v_key, p_value -> v_key);
            END IF;
        END LOOP;
        v_modules := v_modules || v_applied;

        -- `module_access` mirrors `modules` for operator tenants; the shell
        -- reads module_access first, so both are written to stay consistent.
        UPDATE public.tenants
           SET modules = v_modules,
               module_access = v_modules,
               data = v_data || jsonb_build_object(
                          'modules_updated_at', now(),
                          'modules_updated_by', coalesce(p_actor, '')),
               updated_at = now()
         WHERE slug = p_tenant_slug;
    END IF;

    PERFORM public.append_audit_event(
        uuid_generate_v5(uuid_ns_dns(), 'tenant:' || p_tenant_slug),
        'SYSTEM_CONFIG_UPDATED',
        p_actor,
        'tenant_config',
        p_tenant_slug,
        jsonb_build_object('key', p_audit_key,
                           'value', p_audit_value,
                           'target', p_target),
        p_actor_role,
        p_hmac_key);

    RETURN jsonb_build_object('config', v_config,
                              'surveyConfig', v_survey,
                              'modules', v_modules);
END;
$$;

REVOKE ALL ON FUNCTION public.set_tenant_config_key(text, text, jsonb, text[], jsonb, text, jsonb, text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.set_tenant_config_key(text, text, jsonb, text[], jsonb, text, jsonb, text, text, text) TO authenticated;
