# ============================================================================
# 2A.3c — admin tenant `kind` (service-provider kind selector backend).
#
# Deterministic: auth dependency overridden, the setup-key check neutralised,
# and create_tenant / pg.update monkeypatched. No DB.
# ============================================================================

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.auth import get_admin_user
from app.routes import admin as admin_routes
from app.services import production_seed

client = TestClient(app)

SERVICE_KINDS = ["operator", "airport", "amo", "ato", "ans"]


def _admin():
    return {"uid": "sa", "email": "sa@x.com", "role": "SUPER_ADMIN", "tenant_id": None}


@pytest.fixture(autouse=True)
def _overrides(monkeypatch):
    app.dependency_overrides[get_admin_user] = _admin
    monkeypatch.setattr(admin_routes, "_verify_admin_setup", lambda key: None)

    async def _no_seed(data, result):
        return 0

    monkeypatch.setattr(admin_routes, "_seed_new_tenant_hazards", _no_seed)
    yield
    app.dependency_overrides.clear()


def test_tenant_kinds_endpoint():
    r = client.get("/api/v1/admin/tenant-kinds")
    assert r.status_code == 200, r.text
    kinds = r.json()["kinds"]
    assert kinds == SERVICE_KINDS
    assert "regulator" not in kinds
    assert "platform" not in kinds


@pytest.mark.parametrize("kind", SERVICE_KINDS)
def test_create_tenant_with_each_kind(monkeypatch, kind):
    captured = {}

    def fake_create(data, user):
        captured["data"] = data
        return {"tenant_id": data.get("tenant_id"), "kind": data.get("kind")}

    monkeypatch.setattr(production_seed, "create_tenant", fake_create)
    r = client.post("/api/v1/admin/tenants", json={
        "setup_key": "x",
        "tenant": {"tenant_id": f"t-{kind}", "name": "N", "kind": kind},
    })
    assert r.status_code == 200, r.text
    assert captured["data"]["kind"] == kind


def test_create_tenant_invalid_kind(monkeypatch):
    monkeypatch.setattr(production_seed, "create_tenant",
                        lambda data, user: {"tenant_id": "x"})
    r = client.post("/api/v1/admin/tenants", json={
        "setup_key": "x",
        "tenant": {"tenant_id": "bad", "name": "N", "kind": "invalid"},
    })
    assert r.status_code == 400, r.text


def test_create_tenant_without_kind_defaults_to_operator(monkeypatch):
    captured = {}

    def fake_create(data, user):
        captured["data"] = data
        return {"tenant_id": "d", "kind": data.get("kind")}

    monkeypatch.setattr(production_seed, "create_tenant", fake_create)
    r = client.post("/api/v1/admin/tenants", json={
        "setup_key": "x",
        "tenant": {"tenant_id": "d", "name": "N"},
    })
    assert r.status_code == 200, r.text
    assert captured["data"]["kind"] == "operator"


def test_patch_tenant_kind(monkeypatch):
    captured = {}

    def fake_update(model, column, value, fields):
        captured["fields"] = fields
        return {"slug": value, **fields}

    monkeypatch.setattr(admin_routes.pg, "update", fake_update)
    r = client.patch("/api/v1/admin/tenants/caan", json={
        "setup_key": "x", "kind": "ato",
    })
    assert r.status_code == 200, r.text
    assert captured["fields"]["kind"] == "ato"


def test_patch_tenant_invalid_kind(monkeypatch):
    monkeypatch.setattr(admin_routes.pg, "update", lambda *a, **k: {"slug": "caan"})
    r = client.patch("/api/v1/admin/tenants/caan", json={
        "setup_key": "x", "kind": "nope",
    })
    assert r.status_code == 400, r.text


def test_patch_tenant_without_kind_leaves_unchanged(monkeypatch):
    captured = {}

    def fake_update(model, column, value, fields):
        captured["fields"] = fields
        return {"slug": value, **fields}

    monkeypatch.setattr(admin_routes.pg, "update", fake_update)
    r = client.patch("/api/v1/admin/tenants/caan", json={
        "setup_key": "x", "name": "New Name",
    })
    assert r.status_code == 200, r.text
    assert "kind" not in captured["fields"]
