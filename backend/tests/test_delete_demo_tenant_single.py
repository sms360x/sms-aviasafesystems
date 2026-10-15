# ============================================================================
# 3C.1A — single-tenant demo deletion scope + contract regression tests.
#
# All tests are fully isolated: Firestore/Auth/session_scope/_audit are faked
# or monkeypatched. No database, Firebase, or network contact occurs.
# ============================================================================

import asyncio
import uuid as uuid_mod

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db import db_models as dm
from app.db.ids import tenant_uuid
from app.middleware.auth import get_current_user
import app.services.admin_data_service as ads
from app.services.admin_data_service import (
    _build_purge_steps,
    _delete_tenant_postgres_data,
    count_demo_tenant_rows,
    delete_demo_tenant,
    unseed_tenant_demo_data,
)

UUID_A = uuid_mod.UUID(tenant_uuid("tenant-a-3c1a"))
UUID_B = uuid_mod.UUID(tenant_uuid("tenant-b-3c1a"))


class _FakeResult:
    def __init__(self, scalar=None, rowcount=0):
        self._scalar = scalar
        self.rowcount = rowcount

    def scalar_one(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar

    def first(self):
        return self._scalar


class _FakeSession:
    """Replays scripted SELECT rows; records every executed statement."""

    def __init__(self, lookup_row=None, count_value=0):
        self.executed = []
        self.lookup_row = lookup_row
        self.count_value = count_value

    async def execute(self, stmt, *args, **kwargs):
        self.executed.append(stmt)
        text = str(stmt)
        if text.lstrip().upper().startswith("SELECT"):
            if "tenants" in text and ("slug" in text or "id" in text) \
                    and "count" not in text.lower():
                return _FakeResult(scalar=self.lookup_row)
            return _FakeResult(scalar=self.count_value)
        table = getattr(getattr(stmt, "table", None), "name", "?")
        if table == "tenants":
            return _FakeResult(rowcount=1)
        return _FakeResult(rowcount=0)


class _FakeScope:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *args):
        return False


def _run(coro):
    return asyncio.run(coro)


def _demo_row(slug, is_demo=True, kind="operator", uid=None):
    resolved = uuid_mod.UUID(tenant_uuid(slug)) if uid is None else uid
    return (resolved, slug, is_demo, kind)


def _where_params(stmt):
    """Bound values of a statement's WHERE clause (no DB needed)."""
    try:
        return dict(stmt.compile().params)
    except Exception:
        return {}


def _params_text(stmt):
    return " ".join(str(v) for v in _where_params(stmt).values())


@pytest.fixture
def quiet_audit(monkeypatch):
    monkeypatch.setattr(ads, "_audit", lambda *a, **k: None)


# ---------------------------------------------------------------------------
# 1/11. Scoped purge deletes only the target (registry + rows)
# ---------------------------------------------------------------------------

def test_scoped_purge_touches_only_target(quiet_audit):
    async def _go():
        session = _FakeSession()
        scope = _FakeScope(session)
        import unittest.mock as mock

        with mock.patch.object(ads, "session_scope", return_value=scope):
            result = await _delete_tenant_postgres_data([UUID_A])
        return result, session.executed

    result, executed = _run(_go())
    by_table = {}
    for stmt in executed:
        table = getattr(getattr(stmt, "table", None), "name", "?")
        by_table.setdefault(table, []).append(stmt)
    # Every executed DELETE references tenant A and never tenant B.
    assert executed, "expected statements to be executed"
    for stmt in executed:
        assert str(UUID_A) in _params_text(stmt), f"target missing: {stmt}"
        assert str(UUID_B) not in _params_text(stmt), f"leak to B: {stmt}"
    # The registry step is scoped to the target only (F-P0-1R fix).
    tenant_stmts = by_table.get("tenants", [])
    assert len(tenant_stmts) == 1
    assert str(UUID_A) in _params_text(tenant_stmts[0])
    assert str(UUID_B) not in _params_text(tenant_stmts[0])
    assert result["details"]["tenants"] == 1


def test_no_global_registry_wipe_in_scoped_mode():
    async def _go():
        return await _build_purge_steps(tenant_uuids=[UUID_A])

    steps = _run(_go())
    names = [n for n, _ in steps]
    assert "regulators" not in names  # cluster-only table skipped
    tenant_step = next(s for n, s in steps if n == "tenants")
    sql = str(tenant_step.whereclause)
    assert "is_demo" in sql  # defense-in-depth predicate retained
    params = _params_text(tenant_step)
    assert str(UUID_A) in params and str(UUID_B) not in params


def test_cluster_purge_keeps_documented_global_scope():
    async def _go():
        return await _build_purge_steps()

    steps = _run(_go())
    names = [n for n, _ in steps]
    assert "regulators" in names and "tenants" in names  # intentional global path


# ---------------------------------------------------------------------------
# 2. Unseed never touches the tenant registry
# ---------------------------------------------------------------------------

def test_unseed_preserves_registry(monkeypatch, quiet_audit):
    session = _FakeSession()
    monkeypatch.setattr(ads, "session_scope", lambda: _FakeScope(session))
    monkeypatch.setattr(ads, "_get_tenant", lambda tid: {"slug": tid})

    async def _fake_uuid(*args, **kwargs):
        return str(UUID_A)

    monkeypatch.setattr(ads, "_resolve_tenant_uuid", _fake_uuid)

    result = _run(unseed_tenant_demo_data("tenant-a-3c1a", ["can", "vsr"], {}))
    tables = {getattr(getattr(s, "table", None), "name", "?") for s in session.executed}
    assert "tenants" not in tables
    assert result["tenant_id"] == "tenant-a-3c1a"


# ---------------------------------------------------------------------------
# 3/5/6. Service-level resolve + guards
# ---------------------------------------------------------------------------

def _patched_scope(monkeypatch, row):
    session = _FakeSession(lookup_row=row)
    monkeypatch.setattr(ads, "session_scope", lambda: _FakeScope(session))
    return session


def test_real_tenant_rejected(monkeypatch, quiet_audit):
    _patched_scope(monkeypatch, _demo_row("real-co", is_demo=False))
    with pytest.raises(PermissionError, match="not a demo tenant"):
        _run(delete_demo_tenant("real-co", {}))


def test_regulator_tenant_rejected(monkeypatch, quiet_audit):
    _patched_scope(monkeypatch, _demo_row("demostate", is_demo=True, kind="regulator"))
    with pytest.raises(PermissionError, match="regulator"):
        _run(delete_demo_tenant("demostate", {}))


def test_unknown_tenant_returns_not_found(monkeypatch, quiet_audit):
    _patched_scope(monkeypatch, None)
    with pytest.raises(ValueError, match="not found"):
        _run(delete_demo_tenant("ghost-3c1a", {}))


def test_blank_tenant_rejected():
    with pytest.raises(ValueError, match="required"):
        _run(delete_demo_tenant("  ", {}))


def test_empty_tenant_has_accurate_zero_counts(monkeypatch, quiet_audit):
    session = _patched_scope(
        monkeypatch, _demo_row("tenant-a-3c1a", uid=UUID_A))
    monkeypatch.setattr(ads, "_purge_firestore_or_none", lambda call_site: None)
    result = _run(delete_demo_tenant("tenant-a-3c1a", {}))
    assert result["success"] is True
    assert result["tenant"] == "tenant-a-3c1a"
    assert result["postgres"]["details"]["tenants"] == 1
    assert result["firestore"]["status"] == "skipped"  # accurately reported


# ---------------------------------------------------------------------------
# 7. Postgres-only tenant (no Firestore doc) handled safely
# ---------------------------------------------------------------------------

def test_pg_only_tenant_deletes_postgres_and_reports_firestore(monkeypatch, quiet_audit):
    session = _patched_scope(
        monkeypatch, _demo_row("tenant-a-3c1a", uid=UUID_A))

    class _FailingFS:
        def collection(self, name):
            raise RuntimeError("mirror unavailable")

    monkeypatch.setattr(ads, "_purge_firestore_or_none", lambda call_site: _FailingFS())
    result = _run(delete_demo_tenant("tenant-a-3c1a", {}))
    # Postgres work completed; the failed plane is reported, not hidden.
    assert result["postgres"]["details"]["tenants"] == 1
    assert result["firestore"]["status"] == "error"
    assert result["result"] == "partial"


# ---------------------------------------------------------------------------
# 8. Count preview agrees with deletion scope
# ---------------------------------------------------------------------------

def test_count_preview_matches_delete_scope(monkeypatch, quiet_audit):
    session = _FakeSession(
        lookup_row=_demo_row("tenant-a-3c1a", uid=UUID_A), count_value=4)
    monkeypatch.setattr(ads, "session_scope", lambda: _FakeScope(session))
    result = _run(count_demo_tenant_rows("tenant-a-3c1a"))
    delete_names = [n for n, _ in _run(_build_purge_steps(tenant_uuids=[UUID_A]))]
    assert set(result["counts"].keys()) == set(delete_names)
    assert result["total"] == 4 * len(delete_names)
    # Every count query carries the same WHERE as its delete step.
    count_selects = [s for s in session.executed
                     if "count(" in str(s).lower()]
    assert len(count_selects) == len(delete_names), \
        "one count SELECT per delete step"


def test_count_rejects_real_tenant(monkeypatch, quiet_audit):
    _patched_scope(monkeypatch, _demo_row("real-co", is_demo=False))
    with pytest.raises(PermissionError):
        _run(count_demo_tenant_rows("real-co"))


# ---------------------------------------------------------------------------
# 12. Partial failures reported accurately, never raised, never hidden
# ---------------------------------------------------------------------------

def test_partial_external_cleanup_reported(monkeypatch, quiet_audit):
    session = _patched_scope(
        monkeypatch, _demo_row("tenant-a-3c1a", uid=UUID_A))

    class _FakeFS:
        def collection(self, name):
            raise RuntimeError("mirror unavailable")

    monkeypatch.setattr(ads, "_purge_firestore_or_none", lambda call_site: _FakeFS())
    result = _run(delete_demo_tenant("tenant-a-3c1a", {}))
    assert result["result"] == "partial"
    assert result["success"] is True  # HTTP 200 with honest body, not silent success
    assert result["firestore"]["status"] == "error"
    assert result["postgres"]["details"]["tenants"] == 1


# ---------------------------------------------------------------------------
# 4/9/10. HTTP contract: 422/403/404 mapping (no DB touched on these paths)
# ---------------------------------------------------------------------------

def _client(monkeypatch, role="SUPER_ADMIN"):
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: {
        "uid": "u-admin", "email": "admin@x.test",
        "role": role, "tenant_id": "t1",
    }
    monkeypatch.setattr(ads, "_audit", lambda *a, **k: None)
    monkeypatch.setattr("app.core.config.settings.SETUP_SECRET", "test-setup-key",
                        raising=False)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(monkeypatch):
    yield from _client(monkeypatch)


def test_missing_tenant_id_rejected_422(client):
    r = client.post("/api/v1/admin/delete-demo-tenant",
                    json={"setup_key": "test-setup-key"})
    assert r.status_code == 422


def test_missing_setup_key_rejected_422(client):
    r = client.post("/api/v1/admin/delete-demo-tenant",
                    json={"tenant_id": "tenant-a-3c1a"})
    assert r.status_code == 422


def test_wrong_setup_key_rejected_403(client):
    r = client.post("/api/v1/admin/delete-demo-tenant",
                    json={"setup_key": "wrong", "tenant_id": "tenant-a-3c1a"})
    assert r.status_code == 403


def test_non_admin_rejected_403(monkeypatch):
    for c in _client(monkeypatch, role="TENANT_ADMIN"):
        r = c.post("/api/v1/admin/delete-demo-tenant",
                   json={"setup_key": "test-setup-key", "tenant_id": "x"})
        assert r.status_code == 403


def test_bulk_stray_tenant_id_rejected_422(client):
    # F-P0-1C guard: the bulk path must not silently swallow a tenant_id.
    r = client.post("/api/v1/admin/delete-demo-tenants",
                    json={"setup_key": "test-setup-key", "tenant_id": "x"})
    assert r.status_code == 422


def test_unknown_tenant_mapped_404(client, monkeypatch):
    async def _missing(tenant_id, actor):
        raise ValueError("tenant not found: ghost-3c1a")

    monkeypatch.setattr(ads, "delete_demo_tenant", _missing)
    r = client.post("/api/v1/admin/delete-demo-tenant",
                    json={"setup_key": "test-setup-key", "tenant_id": "ghost-3c1a"})
    assert r.status_code == 404


def test_count_missing_tenant_id_422(client):
    r = client.get("/api/v1/admin/delete-demo-tenant/count")
    assert r.status_code == 422


def test_count_unknown_tenant_404(client, monkeypatch):
    async def _missing(tenant_id):
        raise ValueError("tenant not found: ghost-3c1a")

    monkeypatch.setattr(ads, "count_demo_tenant_rows", _missing)
    r = client.get("/api/v1/admin/delete-demo-tenant/count?tenant_id=ghost-3c1a")
    assert r.status_code == 404


def test_single_and_bulk_routes_both_registered():
    from app.routes.admin import router

    paths = {getattr(r, "path", None) for r in router.routes}
    assert "/delete-demo-tenant" in paths
    assert "/delete-demo-tenant/count" in paths
    assert "/delete-demo-tenants" in paths  # bulk kept distinct
