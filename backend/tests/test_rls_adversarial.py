"""2C.3d/2C.4 — adversarial RLS isolation tests (Phase 1 flag ON in a test context).

These tests exercise RLS enforcement on the real application path. Unlike the
~85 tests that override ``get_current_user`` (and therefore never publish an RLS
identity), these go **through the real auth dependency** — ``get_current_user``
is called, which sets the request identity ContextVar that the SQLAlchemy
``after_begin`` listener turns into the ``app.current_*`` GUCs and (when
``RLS_ENFORCEMENT_ENABLED``) ``SET LOCAL ROLE authenticated``.

Only ``verify_firebase_token`` / ``resolve_user_context`` / ``_tenant_is_suspended``
are patched (the token/DB lookups); ``get_current_user`` itself runs for real.

The flag is enabled per-test via monkeypatch only; ``config.py`` is not changed
here. Every query runs in its own transaction and the fixture rows are removed
in teardown.
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

from _mbb import cleanup, create_tenant, create_user, unique_slug


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


def _owner_sql(sql: str, params=None):
    async def _go():
        async with session_scope() as s:
            return await s.execute(text(sql), params or {})

    return asyncio.run(_go())


def _owner_count(table: str, where: str = "", params=None) -> int:
    sql = f"SELECT count(*) FROM public.{table}"
    if where:
        sql += f" WHERE {where}"
    async def _go():
        async with session_scope() as s:
            return (await s.execute(text(sql), params or {})).scalar_one()
    return asyncio.run(_go())


@pytest.fixture
def rls_env():
    slug_a = unique_slug("rls-a")
    slug_b = unique_slug("rls-b")
    create_tenant(slug_a)
    create_tenant(slug_b)
    id_a, id_b = tenant_uuid(slug_a), tenant_uuid(slug_b)
    batch_a, batch_b = uuid.uuid4(), uuid.uuid4()
    for tid, bid in ((id_a, batch_a), (id_b, batch_b)):
        _owner_sql("INSERT INTO public.import_batches (id, tenant_id) VALUES (:id, :tid)",
                   {"id": bid, "tid": tid})
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

    total = _run_as(monkeypatch, None, "SUPER_ADMIN", q, uid="u-admin")
    assert total == 2


# ---------------------------------------------------------------------------
# T7 — unset GUCs fail closed
# ---------------------------------------------------------------------------

def test_t7_unset_identity_fails_closed(rls_env):
    env = rls_env

    async def q():
        async with session_scope() as s:
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
    expected = _owner_count(READ_ALL)
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
# Governance fixture for T10–T16
# ---------------------------------------------------------------------------

@pytest.fixture
def gov_env():
    slugs = {k: unique_slug(f"rls-{k}") for k in ("op", "reg", "oth", "xa", "xb")}
    ids = {}
    for k, s in slugs.items():
        ids[k] = create_tenant(s)
    _owner_sql("UPDATE public.tenants SET kind='regulator' WHERE id=:id", {"id": ids["reg"]})

    oversight_id = uuid.uuid4()
    a_id, b_id = uuid.uuid4(), uuid.uuid4()
    finding_id, sms_id, batch_id, ha_id = (uuid.uuid4() for _ in range(4))
    rca_id = uuid.uuid4()
    aud_id = f"AUD-{uuid.uuid4().hex[:10]}"
    member_user_id = uuid.UUID(create_user(ids["op"], unique_slug("u-member")))

    async def _setup():
        async with session_scope() as s:
            await s.execute(text(
                "INSERT INTO public.oversight_relationships "
                "(id, regulator_tenant_id, operator_tenant_id, effective_from) "
                "VALUES (:i, :r, :o, now())"),
                {"i": oversight_id, "r": ids["reg"], "o": ids["op"]})
            await s.execute(text(
                "INSERT INTO public.sms_maturity (id, tenant_id) VALUES (:i, :t)"),
                {"i": sms_id, "t": ids["op"]})
            await s.execute(text(
                "INSERT INTO public.import_batches (id, tenant_id) VALUES (:i, :t)"),
                {"i": batch_id, "t": ids["op"]})
            await s.execute(text(
                "INSERT INTO public.hazard_rca_entries "
                "(id, tenant_id, resource_id, title, description, source_type, functional_area, status) "
                "VALUES (:i, :t, 'res-1', 't', 'd', 'voluntary', 'flight_operations', 'Open')"),
                {"i": rca_id, "t": ids["op"]})
            await s.execute(text(
                "INSERT INTO public.hazard_assessments (id, tenant_id, entry_id, resource_id) "
                "VALUES (:i, :t, :e, 'res-1')"),
                {"i": ha_id, "t": ids["op"], "e": rca_id})
            await s.execute(text(
                "INSERT INTO public.feedback (id, tenant_id, user_email) VALUES (:i, :t, 'a@x.com')"),
                {"i": uuid.uuid4(), "t": ids["op"]})
            await s.execute(text(
                "INSERT INTO public.audit_dispatches (audit_id, tenant_id) VALUES (:a, :t)"),
                {"a": aud_id, "t": slugs["op"]})
            await s.execute(text(
                "INSERT INTO public.memberships (user_id, role, effective_from) "
                "VALUES (:u, 'TENANT_ADMIN', now())"), {"u": member_user_id})
            await s.execute(text(
                "INSERT INTO public.psoe_assessments (id, tenant_id, title, template_version) "
                "VALUES (:i, :t, 't', 'v1')"), {"i": a_id, "t": ids["xa"]})
            await s.execute(text(
                "INSERT INTO public.psoe_assessments (id, tenant_id, title, template_version) "
                "VALUES (:i, :t, 't', 'v1')"), {"i": b_id, "t": ids["xb"]})
            await s.execute(text(
                "INSERT INTO public.psoe_findings (id, assessment_id, description) "
                "VALUES (:i, :a, 'd')"), {"i": finding_id, "a": a_id})

    asyncio.run(_setup())

    try:
        yield {"slugs": slugs, "ids": ids, "oversight_id": oversight_id,
               "a_id": a_id, "b_id": b_id, "finding_id": finding_id,
               "aud_id": aud_id, "member_user_id": member_user_id}
    finally:
        async def _teardown():
            async with session_scope() as s:
                await s.execute(text(
                    "DELETE FROM public.psoe_findings WHERE assessment_id = ANY(:a)"),
                    {"a": [a_id, b_id]})
                await s.execute(text(
                    "DELETE FROM public.psoe_assessments WHERE id = ANY(:a)"),
                    {"a": [a_id, b_id]})
                await s.execute(text(
                    "DELETE FROM public.oversight_relationships WHERE id=:i"),
                    {"i": oversight_id})
                await s.execute(text(
                    "DELETE FROM public.memberships WHERE user_id=:u"),
                    {"u": member_user_id})
                await s.execute(text(
                    "DELETE FROM public.audit_dispatches WHERE audit_id=:a"),
                    {"a": aud_id})
        try:
            asyncio.run(_teardown())
        except Exception:
            pass
        for s in slugs.values():
            cleanup(s, ["hazard_assessments", "hazard_rca_entries",
                        "sms_maturity", "import_batches", "feedback"])


# ---------------------------------------------------------------------------
# T10 — regulator oversight predicate (Outcome-visible tables only)
# ---------------------------------------------------------------------------

def test_t10_regulator_oversight_sees_outcomes_not_operator_only(gov_env, monkeypatch):
    env = gov_env
    op_id = env["ids"]["op"]

    def count(table):
        async def q(s):
            return (await s.execute(
                text(f"SELECT count(*) FROM public.{table} WHERE tenant_id = :t"),
                {"t": op_id},
            )).scalar_one()
        return q

    # Outcome-visible (has the regulator branch): sms_maturity -> visible.
    assert _run_as(monkeypatch, env["slugs"]["reg"], "STATE_SMD", count("sms_maturity")) == 1
    # Operator-only (no branch): import_batches -> hidden even via oversight.
    assert _run_as(monkeypatch, env["slugs"]["reg"], "STATE_SMD", count("import_batches")) == 0


# ---------------------------------------------------------------------------
# T11 — memberships is SUPER_ADMIN-only
# ---------------------------------------------------------------------------

def test_t11_memberships_super_admin_only(gov_env, monkeypatch):
    env = gov_env

    async def q(s):
        return (await s.execute(text("SELECT count(*) FROM public.memberships"))).scalar_one()

    tenant_view = _run_as(monkeypatch, env["slugs"]["op"], "TENANT_ADMIN", q)
    assert tenant_view == 0, "a tenant user must not read memberships"

    owner_total = _owner_count("memberships")
    super_view = _run_as(monkeypatch, None, "SUPER_ADMIN", q, uid="u-admin")
    assert super_view == owner_total >= 1


# ---------------------------------------------------------------------------
# T12 — oversight_relationships is shared
# ---------------------------------------------------------------------------

def test_t12_oversight_relationships_shared(gov_env, monkeypatch):
    env = gov_env
    oid = env["oversight_id"]

    async def q(s):
        return (await s.execute(
            text("SELECT count(*) FROM public.oversight_relationships WHERE id=:i"),
            {"i": oid},
        )).scalar_one()

    assert _run_as(monkeypatch, env["slugs"]["reg"], "STATE_SMD", q) == 1
    assert _run_as(monkeypatch, env["slugs"]["op"], "TENANT_ADMIN", q) == 1
    assert _run_as(monkeypatch, None, "SUPER_ADMIN", q, uid="u-admin") == 1
    # A tenant in neither side cannot see the row.
    assert _run_as(monkeypatch, env["slugs"]["oth"], "TENANT_ADMIN", q) == 0


# ---------------------------------------------------------------------------
# T13 / T15 — operator-only tables (audit_dispatches text slug, feedback uuid)
# ---------------------------------------------------------------------------

def test_t13_audit_dispatches_operator_only(gov_env, monkeypatch):
    env = gov_env

    async def q(s):
        return (await s.execute(
            text("SELECT count(*) FROM public.audit_dispatches WHERE audit_id=:a"),
            {"a": env["aud_id"]},
        )).scalar_one()

    assert _run_as(monkeypatch, env["slugs"]["op"], "TENANT_ADMIN", q) == 1
    assert _run_as(monkeypatch, env["slugs"]["reg"], "STATE_SMD", q) == 0


def test_t15_feedback_operator_only(gov_env, monkeypatch):
    env = gov_env
    op_id = env["ids"]["op"]

    async def q(s):
        return (await s.execute(
            text("SELECT count(*) FROM public.feedback WHERE tenant_id=:t"),
            {"t": op_id},
        )).scalar_one()

    assert _run_as(monkeypatch, env["slugs"]["op"], "TENANT_ADMIN", q) == 1
    assert _run_as(monkeypatch, env["slugs"]["reg"], "STATE_SMD", q) == 0


# ---------------------------------------------------------------------------
# T14 — hazard_assessments is operator-only (inverted from the original spec)
# ---------------------------------------------------------------------------

def test_t14_hazard_assessments_operator_only(gov_env, monkeypatch):
    env = gov_env
    op_id = env["ids"]["op"]

    async def q(s):
        return (await s.execute(
            text("SELECT count(*) FROM public.hazard_assessments WHERE tenant_id=:t"),
            {"t": op_id},
        )).scalar_one()

    assert _run_as(monkeypatch, env["slugs"]["op"], "TENANT_ADMIN", q) == 1
    assert _run_as(monkeypatch, env["slugs"]["reg"], "STATE_SMD", q) == 0


# ---------------------------------------------------------------------------
# T16 — psoe_findings scoped via psoe_assessments
# ---------------------------------------------------------------------------

def test_t16_psoe_findings_scoped_via_assessment(gov_env, monkeypatch):
    env = gov_env

    async def q(s):
        return (await s.execute(
            text("SELECT count(*) FROM public.psoe_findings WHERE id=:i"),
            {"i": env["finding_id"]},
        )).scalar_one()

    # The assessment owner's tenant sees the finding; another tenant does not.
    assert _run_as(monkeypatch, env["slugs"]["xa"], "TENANT_ADMIN", q) == 1
    assert _run_as(monkeypatch, env["slugs"]["xb"], "TENANT_ADMIN", q) == 0
