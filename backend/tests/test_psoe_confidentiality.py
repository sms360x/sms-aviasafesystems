# ============================================================================
# 3C.2D-PSOE-1 — private assessment confidentiality containment.
#
# Fully isolated: pg accessors and service internals are faked/monkeypatched,
# auth uses dependency overrides. No database, Firebase, or network contact.
# ============================================================================

import asyncio
import uuid as uuid_mod

import pytest
from fastapi.testclient import TestClient

from app.db.ids import register_tenant, tenant_uuid
from app.middleware.auth import get_current_user
import app.routes.psoe as psoe_routes
import app.api.v1.endpoints.psoe as psoe_v1


def _run(coro):
    return asyncio.run(coro)


def _row(tenant_slug, aid="a1111111-1111-4111-8111-111111111111"):
    register_tenant(tenant_slug)
    return {
        "id": aid, "tenant_id": tenant_uuid(tenant_slug), "title": "Q1",
        "status": "draft", "department": None, "scope": None,
        "template_version": "v1", "overall_score_pct": None,
        "overall_level": None, "assessment_date": None,
        "created_at": None, "updated_at": None,
    }


def _user(role, tenant_id):
    return {"uid": "u-" + role.lower(), "email": f"{role.lower()}@x.test",
            "role": role, "tenant_id": tenant_id}


@pytest.fixture
def client():
    from app.main import app

    app.dependency_overrides.clear()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _override(role, tenant_id):
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: _user(role, tenant_id)


def _boom(*args, **kwargs):
    raise AssertionError("database must not be touched on this path")


# ---------------------------------------------------------------------------
# 1/2. Airline reads own; airline B cannot read A's
# ---------------------------------------------------------------------------

def test_airline_reads_own_assessment(client, monkeypatch):
    row = _row("tenant-a")
    monkeypatch.setattr(psoe_routes.pg, "fetch_by", lambda *a, **k: row)
    monkeypatch.setattr(psoe_routes, "_ensure_tenant_registry", lambda: None)
    _override("TENANT_ADMIN", "tenant-a")
    r = client.get("/api/v1/psoe/assessments/" + row["id"])
    assert r.status_code == 200


def test_airline_cannot_read_other_tenant_assessment(client, monkeypatch):
    row = _row("tenant-a")
    monkeypatch.setattr(psoe_routes.pg, "fetch_by", lambda *a, **k: row)
    monkeypatch.setattr(psoe_routes, "_ensure_tenant_registry", lambda: None)
    monkeypatch.setattr(psoe_routes.pg, "update", _boom)
    _override("TENANT_ADMIN", "tenant-b")
    assert client.get("/api/v1/psoe/assessments/" + row["id"]).status_code == 403


def test_list_scopes_to_caller_tenant(client, monkeypatch):
    captured = {}

    def _fake_fetch(model, where=None):
        captured["params"] = {}
        for w in (where or []):
            try:
                captured["params"].update(dict(w.compile().params))
            except Exception:
                pass
        return []

    monkeypatch.setattr(psoe_routes.pg, "fetch_all", _fake_fetch)
    monkeypatch.setattr(psoe_routes, "_ensure_tenant_registry", lambda: None)
    _override("TENANT_ADMIN", "tenant-b")
    assert client.get("/api/v1/psoe/assessments").status_code == 200
    values = " ".join(str(v) for v in captured["params"].values())
    assert tenant_uuid("tenant-b") in values
    assert tenant_uuid("tenant-a") not in values


# ---------------------------------------------------------------------------
# 3/4/5/6/7. Regulator containment (surface 1)
# ---------------------------------------------------------------------------

def test_regulator_cannot_list_airline_assessments(client, monkeypatch):
    monkeypatch.setattr(psoe_routes.pg, "fetch_all", _boom)
    _override("STATE_SMD", None)
    assert client.get("/api/v1/psoe/assessments").status_code == 403


def test_regulator_cannot_read_by_id(client, monkeypatch):
    row = _row("tenant-a")
    monkeypatch.setattr(psoe_routes.pg, "fetch_by", lambda *a, **k: row)
    monkeypatch.setattr(psoe_routes, "_ensure_tenant_registry", lambda: None)
    _override("STATE_SMD", None)
    assert client.get("/api/v1/psoe/assessments/" + row["id"]).status_code == 403


def test_regulator_cannot_edit_by_id(client, monkeypatch):
    row = _row("tenant-a")
    monkeypatch.setattr(psoe_routes.pg, "fetch_by", lambda *a, **k: row)
    monkeypatch.setattr(psoe_routes, "_ensure_tenant_registry", lambda: None)
    monkeypatch.setattr(psoe_routes.pg, "update", _boom)
    _override("STATE_SMD", None)
    r = client.patch("/api/v1/psoe/assessments/" + row["id"],
                     json={"title": "tampered"})
    assert r.status_code == 403


def test_regulator_cannot_export(client, monkeypatch):
    row = _row("tenant-a")
    monkeypatch.setattr(psoe_routes.pg, "fetch_by", lambda *a, **k: row)
    monkeypatch.setattr(psoe_routes, "_ensure_tenant_registry", lambda: None)
    _override("STATE_SMD", None)
    assert client.get(f"/api/v1/psoe/assessments/{row['id']}/export").status_code == 403


def test_regulator_tenant_param_cannot_bypass(client, monkeypatch):
    monkeypatch.setattr(psoe_routes.pg, "fetch_all", _boom)
    _override("STATE_SMD", None)
    r = client.get("/api/v1/psoe/assessments", params={"tenant_id": "tenant-a"})
    assert r.status_code == 403


def test_regulator_cannot_create_into_airline_tenant(client, monkeypatch):
    monkeypatch.setattr(psoe_routes.pg, "insert", _boom)
    _override("STATE_SMD", None)
    r = client.post("/api/v1/psoe/assessments",
                    json={"title": "Surveillance", "tenant_id": "tenant-a"})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 8. Creation stays tenant-bound for airlines
# ---------------------------------------------------------------------------

def test_airline_cross_tenant_create_rejected(client, monkeypatch):
    monkeypatch.setattr(psoe_routes.pg, "insert", _boom)
    _override("TENANT_ADMIN", "tenant-b")
    r = client.post("/api/v1/psoe/assessments",
                    json={"title": "Sneaky", "tenant_id": "tenant-a"})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 11. Surface 2 behaves consistently
# ---------------------------------------------------------------------------

def test_surface2_regulator_list_override_denied(client):
    _override("STATE_SMD", None)
    r = client.get("/api/v1/supabase/psoe/assessments", params={"tenant_id": "tenant-a"})
    assert r.status_code == 403


def test_surface2_regulator_unscoped_denied(client):
    _override("STATE_SMD", None)
    assert client.get("/api/v1/supabase/psoe/assessments").status_code == 403
    assert client.get("/api/v1/supabase/psoe/assessments/aid").status_code == 403


def test_surface2_own_tenant_preserved(client, monkeypatch):
    captured = {}

    async def _fake_list(tenant_id, status=None):
        captured["tenant"] = tenant_id
        return {"items": []}

    monkeypatch.setattr(psoe_v1.psoe_complete_service, "list_assessments", _fake_list)
    _override("STATE_SMD", "reg-1")
    assert client.get("/api/v1/supabase/psoe/assessments").status_code == 200
    assert captured["tenant"] == "reg-1"


# ---------------------------------------------------------------------------
# 9. Cross-tenant linkage denied (service level, faked session)
# ---------------------------------------------------------------------------

def test_cross_tenant_link_denied(monkeypatch):
    import app.services.psoe_cap_link_service as link_mod

    other = uuid_mod.uuid5(uuid_mod.NAMESPACE_OID, "other")
    finding = {"id": uuid_mod.uuid4(), "assessment_id": uuid_mod.uuid4()}
    cap = {"id": uuid_mod.uuid4(), "tenant_id": other}

    # Call order in _link_async: finding row, cap row, finding's
    # assessment id, assessment owner uuid.
    class _Session:
        async def execute(self, stmt, *a, **k):
            return _FakeOut(next(script))

        async def flush(self):
            return None

    class _FakeOut:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

        def scalars(self):
            return self

        def first(self):
            return self._value

    class _Scope:
        async def __aenter__(self):
            return _Session()

        async def __aexit__(self, *a):
            return False

    # Dict rows support attribute-style reads used by the service.
    class _Attr(dict):
        __getattr__ = dict.get
        __setattr__ = dict.__setitem__

    finding_obj, cap_obj = _Attr(finding), _Attr(cap)
    script = iter([finding_obj, cap_obj, finding["assessment_id"], other])

    monkeypatch.setattr(link_mod, "session_scope", lambda: _Scope())
    monkeypatch.setattr(link_mod, "log_audit", lambda **kw: None)

    svc = link_mod.PsoeCapLinkService("tenant-a")
    with pytest.raises(PermissionError, match="Cross-tenant"):
        svc.link_finding_to_cap(str(finding["id"]), str(cap["id"]),
                                _user("TENANT_ADMIN", "tenant-a"))


def test_same_tenant_link_allowed(monkeypatch):
    import app.services.psoe_cap_link_service as link_mod

    own = uuid_mod.UUID(tenant_uuid("tenant-a"))

    class _Attr(dict):
        __getattr__ = dict.get
        __setattr__ = dict.__setitem__

    finding = _Attr(id=uuid_mod.uuid4(), assessment_id=uuid_mod.uuid4(),
                    cap_id=None)
    cap = _Attr(id=uuid_mod.uuid4(), tenant_id=own,
                source_psoe_finding_id=None, updated_at=None)
    # Deterministic call order in _link_async: finding row, cap row,
    # finding's assessment id, assessment owner uuid.
    script = iter([finding, cap, finding["assessment_id"], own])

    class _Session:
        async def execute(self, stmt, *a, **k):
            return _FakeOut(next(script))

        async def flush(self):
            return None

    class _FakeOut:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

        def scalars(self):
            return self

        def first(self):
            return self._value

    class _Scope:
        async def __aenter__(self):
            return _Session()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(link_mod, "session_scope", lambda: _Scope())
    monkeypatch.setattr(link_mod, "log_audit", lambda **kw: None)

    svc = link_mod.PsoeCapLinkService("tenant-a")
    result = svc.link_finding_to_cap(str(finding["id"]), str(cap["id"]),
                                     _user("TENANT_ADMIN", "tenant-a"))
    assert result["finding_id"] == str(finding["id"])
    assert cap["source_psoe_finding_id"] == finding["id"]


# ---------------------------------------------------------------------------
# 12. Ambiguous ownership fails safely; SUPER_ADMIN recorded separately
# ---------------------------------------------------------------------------

def test_unknown_ownership_denied_for_tenant(client, monkeypatch):
    row = _row("tenant-a")
    row["tenant_id"] = str(uuid_mod.uuid5(uuid_mod.NAMESPACE_OID, "unknown"))
    monkeypatch.setattr(psoe_routes.pg, "fetch_by", lambda *a, **k: row)
    monkeypatch.setattr(psoe_routes, "_ensure_tenant_registry", lambda: None)
    _override("TENANT_ADMIN", "tenant-a")
    assert client.get("/api/v1/psoe/assessments/" + row["id"]).status_code == 403


def test_super_admin_access_recorded(client, monkeypatch):
    # Policy decision recorded separately: platform administration retains
    # access. This test pins current behavior, not approval.
    row = _row("tenant-a")
    monkeypatch.setattr(psoe_routes.pg, "fetch_by", lambda *a, **k: row)
    monkeypatch.setattr(psoe_routes, "_ensure_tenant_registry", lambda: None)
    _override("SUPER_ADMIN", None)
    assert client.get("/api/v1/psoe/assessments/" + row["id"]).status_code == 200
