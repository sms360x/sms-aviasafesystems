"""2C.3d — adversarial RLS isolation tests (Phase 1: flag ON in a test context).

These tests exercise RLS enforcement on the real application path. Unlike the
~85 tests that override ``get_current_user`` (and therefore never publish an RLS
identity), these go **through the real auth dependency** — ``get_current_user``
is called, which sets the request identity ContextVar that the SQLAlchemy
``after_begin`` listener turns into the ``app.current_*`` GUCs and (when
``RLS_ENFORCEMENT_ENABLED``) ``SET LOCAL ROLE authenticated``.

Only ``verify_firebase_token`` / ``resolve_user_context`` / ``_tenant_is_suspended``
are patched (the token/DB lookups); ``get_current_user`` itself runs for real.

The flag is enabled per-test via monkeypatch only; ``config.py`` is not changed
here. Each query runs in its own transaction; write attempts that succeed
against the wrong tenant are rolled back and the fixture tenants are removed.
"""

import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.core.config import settings
from app.db.ids import tenant_uuid
from app.db.rls import clear_current_identity
from app.db.session import get_engine, session_scope

from _mbb import cleanup, create_tenant, unique_slug


BATCH = "import_batches"  # Operator-only (uuid tenant_id), simple ALL policy.
READ_ALL = "hfacs_nanocodes"  # Reference table, USING (true).

# The 20 Module B/C policies that schema_init.py's runtime DDL used to revert
# (2C.3b-fix). T9 asserts the re-creator keeps them GUC-based.
MODULE20 = [
    "p_action_items_tenant_isolation", "p_hazard_triage_tenant_isolation",
    "p_import_batches_tenant_isolation", "p_import_links_tenant_isolation",
    "p_import_mappings_tenant_isolation", "p_import_rows_tenant_isolation",
    "p_safety_communications_tenant_isolation", "p_sag_meetings_tenant_isolation",
    "p_srb_meetings_tenant_isolation", "p_module_c_aggregates_tenant_isolation",
    "p_caan_reports_tenant_isolation", "p_caan_reports_cross_tenant",
    "p_metric_definitions_cross_tenant", "p_module_c_aggregates_cross_tenant",
    "p_module_c_aggregates_national", "p_regulatory_reports_cross_tenant",
    "p_state_risk_categories_cross_tenant", "p_state_risk_register_cross_tenant",
    "p_state_safety_performance_targets_caan", "p_taxonomy_mappings_cross_tenant",
]


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    """Phase 1: enable enforcement for the duration of each test only."""
    monkeypatch.setattr(settings, "RLS_ENFORCEMENT_ENABLED", True)
    clear_current_identity()
    yield
    clear_current_identity()


def _insert_batch(tid: str, batch_id: uuid.UUID) -> None:
    async def _go():
        async with session_scope() as s:
            await s.execute(text(
                "INSERT INTO public.import_batches (id, tenant_id) "
                "VALUES (:id, :tid)"
            ), {"id": batch_id, "tid": tid})

    asyncio.run(_go())


@pytest.fixture
def rls_env():
    slug_a = unique_slug("rls-a")
    slug_b = unique_slug("rls-b")
    create_tenant(slug_a)
    create_tenant(slug_b)
    id_a, id_b = tenant_uuid(slug_a), tenant_uuid(slug_b)
    batch_a, batch_b = uuid.uuid4(), uuid.uuid4()
    _insert_batch(id_a, batch_a)
    _insert_batch(id_b, batch_b)
    try:
        yield {"slug_a": slug_a, "slug_b": slug_b, "id_a": id_a, "id_b": id_b,
               "batch_a": batch_a, "batch_b": batch_b}
    finally:
        cleanup(slug_a, [BATCH])
        cleanup(slug_b, [BATCH])


def _run_as(monkeypatch, slug, role, fn, uid="u-rls"):
    """Run ``fn(session)`` on a transaction whose identity comes from the REAL
    ``get_current_user`` path (auth dependency), with the flag ON."""
    import app.middleware.auth as auth
    from fastapi.security import HTTPAuthorizationCredentials

    decoded = {"uid": uid, "email": f"{uid}@test.local"}
    monkeypatch.setattr(auth, "verify_firebase_token", lambda token: decoded)
    monkeypatch.setattr(
        auth, "resolve_user_context",
        lambda email: {"role": role, "tenant_id": slug},
    )
    monkeypatch.setattr(auth, "_tenant_is_suspended", lambda tenant_id: False)

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok")

    async def _go():
        await auth.get_current_user(creds)  # real dependency -> sets ContextVar
        async with session_scope() as s:
            return await fn(s)

    return asyncio.run(_go())


# ---------------------------------------------------------------------------
# T1–T5 — cross-tenant isolation on a policy-covered table
# ---------------------------------------------------------------------------

def test_t1_same_tenant_read_succeeds(rls_env, monkeypatch):
    env = rls_env

    async def q(s):
        return (await s.execute(
            text("SELECT count(*) FROM public.import_batches WHERE tenant_id = :t"),
            {"t": env["id_a"]},
        )).scalar_one()

    assert _run_as(monkeypatch, env["slug_a"], "TENANT_ADMIN", q) == 1


def test_t2_cross_tenant_read_denied(rls_env, monkeypatch):
    env = rls_env

    async def q(s):
        return (await s.execute(
            text("SELECT count(*) FROM public.import_batches WHERE tenant_id = :t"),
            {"t": env["id_b"]},
        )).scalar_one()

    assert _run_as(monkeypatch, env["slug_a"], "TENANT_ADMIN", q) == 0


def test_t3_cross_tenant_insert_rejected(rls_env, monkeypatch):
    env = rls_env

    async def q(s):
        await s.execute(text(
            "INSERT INTO public.import_batches (id, tenant_id) VALUES (:id, :tid)"
        ), {"id": uuid.uuid4(), "tid": env["id_b"]})

    with pytest.raises(ProgrammingError) as exc:
        _run_as(monkeypatch, env["slug_a"], "TENANT_ADMIN", q)
    assert "row-level security" in str(exc.value).lower()


def test_t4_cross_tenant_update_affects_zero_rows(rls_env, monkeypatch):
    env = rls_env

    async def q(s):
        res = await s.execute(text(
            "UPDATE public.import_batches SET status = 'parsed' WHERE tenant_id = :t"
        ), {"t": env["id_b"]})
        return res.rowcount

    assert _run_as(monkeypatch, env["slug_a"], "TENANT_ADMIN", q) == 0


def test_t5_cross_tenant_delete_affects_zero_rows(rls_env, monkeypatch):
    env = rls_env

    async def q(s):
        res = await s.execute(text(
            "DELETE FROM public.import_batches WHERE tenant_id = :t"
        ), {"t": env["id_b"]})
        return res.rowcount

    assert _run_as(monkeypatch, env["slug_a"], "TENANT_ADMIN", q) == 0


# ---------------------------------------------------------------------------
# T6 — SUPER_ADMIN inline exemption
# ---------------------------------------------------------------------------

def test_t6_super_admin_exemption_reads_across_tenants(rls_env, monkeypatch):
    env = rls_env

    async def q(s):
        return (await s.execute(
            text("SELECT count(*) FROM public.import_batches")
        )).scalar_one()

    # SUPER_ADMIN with no tenant sees both A's and B's rows.
    total = _run_as(monkeypatch, None, "SUPER_ADMIN", q, uid="u-admin")
    assert total == 2


# ---------------------------------------------------------------------------
# T7 — unset GUCs fail closed
# ---------------------------------------------------------------------------

def test_t7_unset_identity_fails_closed(rls_env):
    env = rls_env

    async def q():
        async with session_scope() as s:
            # Authenticated role but no identity -> GUCs unset.
            await s.execute(text("SET LOCAL ROLE authenticated"))
            total = (await s.execute(
                text("SELECT count(*) FROM public.import_batches")
            )).scalar_one()
            own = (await s.execute(
                text("SELECT count(*) FROM public.import_batches WHERE tenant_id = :t"),
                {"t": env["id_a"]},
            )).scalar_one()
            return total, own

    total, own = asyncio.run(q())
    assert total == 0, "unset identity must see no rows"
    assert own == 0, "unset identity must not see even the matching row"


# ---------------------------------------------------------------------------
# T8 — read-all policies still work
# ---------------------------------------------------------------------------

def test_t8_read_all_policy_still_returns_rows(rls_env, monkeypatch):
    env = rls_env

    async def owner_count():
        async with session_scope() as s:
            return (await s.execute(
                text(f"SELECT count(*) FROM public.{READ_ALL}")
            )).scalar_one()

    expected = asyncio.run(owner_count())
    assert expected >= 1

    async def q(s):
        return (await s.execute(
            text(f"SELECT count(*) FROM public.{READ_ALL}")
        )).scalar_one()

    got = _run_as(monkeypatch, env["slug_a"], "TENANT_ADMIN", q)
    assert got == expected, "read-all policy must not filter rows"


# ---------------------------------------------------------------------------
# T9 — the runtime re-creator does not revert the policies
# ---------------------------------------------------------------------------

def test_t9_recreator_keeps_policies_guc_based(rls_env):
    async def run_recreator():
        from app.db.schema_init import ensure_domain_schema_async
        await ensure_domain_schema_async(get_engine())
        async with session_scope() as s:
            return dict((await s.execute(text(
                "SELECT policyname, "
                "  (qual LIKE '%current_setting(''app.current%' "
                "   OR with_check LIKE '%current_setting(''app.current%') AS guc "
                "FROM pg_policies WHERE schemaname='public' "
                "AND policyname = ANY(:names)"
            ), {"names": MODULE20})).all())

    state = asyncio.run(run_recreator())
    assert len(state) == 20, f"expected all 20 policies, found {len(state)}"
    reverted = sorted(n for n, guc in state.items() if not guc)
    assert not reverted, f"re-creator reverted policies to auth.jwt: {reverted}"


# ---------------------------------------------------------------------------
# T10 — regulator oversight predicate
# ---------------------------------------------------------------------------

def test_t10_regulator_oversight_predicate():
    pytest.skip(
        "The regulator-oversight branch cannot be exercised yet: "
        "oversight_relationships has RLS enabled and NO policy, so the EXISTS "
        "subquery returns no rows for the authenticated role. The predicate is "
        "written into the Outcome-visible policies but is inert until 2C.4 "
        "writes the oversight_relationships / memberships policies."
    )
