# ============================================================================
# 2E.2 — Durable audit trail (Postgres, per-tenant HMAC-SHA256 chain).
#
# DB-backed: each test uses a throwaway tenant slug and cleans up. The durable
# table is append-only (BEFORE UPDATE/DELETE trigger), so cleanup disables the
# trigger for the test tenant, deletes, and re-enables it.
# ============================================================================

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.ids import tenant_uuid
from app.db.session import session_scope
from app.main import app
from app.middleware.auth import get_current_user
from app.services.audit_service import log_audit

from _mbb import cleanup, create_tenant, unique_slug, run

TRIGGER = "durable_audit_no_mutate_trg"


def _tid(slug: str) -> str:
    return tenant_uuid(slug)


def _durable_rows(slug: str):
    tid = _tid(slug)

    async def _go():
        async with session_scope() as s:
            r = await s.execute(
                text(
                    "SELECT action, actor_uid, resource_type, resource_id, "
                    "metadata, prev_hash, current_hash, id "
                    "FROM public.durable_audit_logs WHERE tenant_id = :t "
                    "ORDER BY timestamp, id"
                ),
                {"t": tid},
            )
            return r.fetchall()

    return run(_go())


def _verify(slug: str):
    """Return the broken row id (None when valid) via the SQL function."""
    tid = _tid(slug)
    from app.services.audit_service import hmac_key

    key = hmac_key()

    async def _go():
        async with session_scope() as s:
            r = await s.execute(
                text("SELECT public.verify_durable_chain(:t, :k)"),
                {"t": tid, "k": key},
            )
            return r.scalar_one()

    return run(_go())


def _purge_durable(slug: str):
    tid = _tid(slug)

    async def _go():
        async with session_scope() as s:
            await s.execute(text(f"ALTER TABLE public.durable_audit_logs DISABLE TRIGGER {TRIGGER}"))
            await s.execute(
                text("DELETE FROM public.durable_audit_logs WHERE tenant_id = :t"),
                {"t": tid},
            )
            await s.execute(text(f"ALTER TABLE public.durable_audit_logs ENABLE TRIGGER {TRIGGER}"))

    run(_go())


@pytest.fixture
def tenant():
    slug = unique_slug("dau")
    create_tenant(slug)
    try:
        yield slug
    finally:
        _purge_durable(slug)
        cleanup(slug, ("tenants",))


def _override(user):
    app.dependency_overrides[get_current_user] = lambda: user


def _clear():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. Append + read / authorization
# ---------------------------------------------------------------------------

def test_append_and_read(tenant):
    log_audit(
        action="TEST_EVENT",
        user="admin@x.test",
        tenant_id=tenant,
        target_type="hazard",
        target_id="H-1",
        metadata={"a": 1},
    )
    rows = _durable_rows(tenant)
    assert len(rows) == 1
    assert rows[0].action == "TEST_EVENT"
    assert rows[0].actor_uid == "admin@x.test"
    assert rows[0].resource_type == "hazard"
    assert rows[0].resource_id == "H-1"

    # SUPER_ADMIN can verify (read) the chain.
    _override({"uid": "u-super", "email": "super@x.test", "role": "SUPER_ADMIN",
               "tenant_id": None})
    try:
        r = TestClient(app).get(f"/api/v1/audit/verify?tenant_id={tenant}")
        assert r.status_code == 200, r.text
        assert r.json()["valid"] is True
    finally:
        _clear()

    # Non-SUPER_ADMIN is denied.
    _override({"uid": "u-ta", "email": "ta@x.test", "role": "TENANT_ADMIN",
               "tenant_id": tenant})
    try:
        r = TestClient(app).get(f"/api/v1/audit/verify?tenant_id={tenant}")
        assert r.status_code == 403, r.text
    finally:
        _clear()


# ---------------------------------------------------------------------------
# 2. Append-only (UPDATE/DELETE trigger)
# ---------------------------------------------------------------------------

def test_update_delete_denied(tenant):
    log_audit(action="LOCKED_EVENT", user="u", tenant_id=tenant,
              target_type="t", target_id="x")
    tid = _tid(tenant)

    async def _update():
        async with session_scope() as s:
            await s.execute(
                text("UPDATE public.durable_audit_logs SET action='TAMPER' WHERE tenant_id = :t"),
                {"t": tid},
            )

    with pytest.raises(Exception):
        run(_update())

    async def _delete():
        async with session_scope() as s:
            await s.execute(
                text("DELETE FROM public.durable_audit_logs WHERE tenant_id = :t"),
                {"t": tid},
            )

    with pytest.raises(Exception):
        run(_delete())


# ---------------------------------------------------------------------------
# 3. Hash-chain integrity
# ---------------------------------------------------------------------------

def test_hash_chain_integrity(tenant):
    for i in range(3):
        log_audit(action=f"EVT_{i}", user="u", tenant_id=tenant,
                  target_type="t", target_id=str(i))
    rows = _durable_rows(tenant)
    assert len(rows) == 3
    assert rows[0].prev_hash == "GENESIS"
    for prev, cur in zip(rows, rows[1:]):
        assert prev.current_hash == cur.prev_hash
    assert _verify(tenant) is None


# ---------------------------------------------------------------------------
# 4. Tampered chain detected
# ---------------------------------------------------------------------------

def test_tampered_chain(tenant):
    for i in range(3):
        log_audit(action=f"TAMPER_{i}", user="u", tenant_id=tenant,
                  target_type="t", target_id=str(i))
    rows = _durable_rows(tenant)
    target_id = rows[0].id

    async def _tamper():
        async with session_scope() as s:
            await s.execute(text(f"ALTER TABLE public.durable_audit_logs DISABLE TRIGGER {TRIGGER}"))
            await s.execute(
                text("UPDATE public.durable_audit_logs SET current_hash = 'deadbeef' WHERE id = :i"),
                {"i": target_id},
            )
            await s.execute(text(f"ALTER TABLE public.durable_audit_logs ENABLE TRIGGER {TRIGGER}"))

    run(_tamper())
    broken = _verify(tenant)
    assert broken is not None  # chain no longer verifies


# ---------------------------------------------------------------------------
# 5. PII redaction for VSR / reporter-contact events
# ---------------------------------------------------------------------------

def test_pii_redaction(tenant):
    log_audit(
        action="VSR_SUBMITTED",
        user="reporter@x.test",
        tenant_id=tenant,
        target_type="report",
        target_id="R-1",
        metadata={"reporter_email": "r@x.test", "note": "ok"},
    )
    log_audit(
        action="REPORTER_CONTACT_WRITTEN",
        user="officer@x.test",
        tenant_id=tenant,
        target_type="reporter_contact",
        target_id="R-1",
        metadata={"has_email": True, "reporter_email": "r@x.test"},
    )
    rows = _durable_rows(tenant)
    assert len(rows) == 2
    for row in rows:
        assert row.actor_uid is None
        meta = row.metadata or {}
        assert not any("email" in k.lower() for k in meta)
        assert not any("reporter" in k.lower() for k in meta)


# ---------------------------------------------------------------------------
# 6. Tenant isolation (independent chains)
# ---------------------------------------------------------------------------

def test_tenant_isolation(tenant):
    other = unique_slug("dau-other")
    create_tenant(other)
    try:
        log_audit(action="A_EVENT", user="u", tenant_id=tenant,
                  target_type="t", target_id="a")
        log_audit(action="B_EVENT", user="u", tenant_id=other,
                  target_type="t", target_id="b")

        rows_a = _durable_rows(tenant)
        rows_b = _durable_rows(other)
        assert len(rows_a) == 1 and len(rows_b) == 1
        assert rows_a[0].prev_hash == "GENESIS"
        assert rows_b[0].prev_hash == "GENESIS"
        assert rows_a[0].current_hash != rows_b[0].current_hash

        assert _verify(tenant) is None
        assert _verify(other) is None
    finally:
        _purge_durable(other)
        cleanup(other, ("tenants",))
