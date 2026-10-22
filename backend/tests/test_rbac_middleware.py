# ============================================================================
# P2-26 — RBAC middleware (module gate + tenant isolation + cross-tenant bypass).
# ============================================================================

import asyncio

from starlette.requests import Request

from app.main import app
from app.middleware import rbac_middleware as mw
from app.middleware.auth import get_current_user
from app.middleware.rbac_middleware import RBACMiddleware, get_module_for_path
from app.services import sms_maturity_service


def _request(path, *, user=None, query=None):
    scope = {
        "type": "http", "method": "GET", "path": path, "query_string": b"",
        "headers": [], "path_params": {},
    }
    req = Request(scope)
    if user is not None:
        req.state.user = user
    req._mw_query = query or {}
    return req


def _call(mw_func, path, user, monkeypatch):
    req = _request(path, user=user)

    async def _call_next(_req):
        return {"ok": True}

    return asyncio.run(mw_func(req, _call_next))


def test_module_path_mapping():
    assert get_module_for_path("/api/v1/surveys/") == "module1"
    assert get_module_for_path("/api/v1/hazards/x") == "module2"
    assert get_module_for_path("/api/v1/regulator/industry-averages") == "module5"
    assert get_module_for_path("/api/v1/spi/state/values") == "module5"
    assert get_module_for_path("/api/v1/health") == ""


def test_employee_blocked_from_module5(monkeypatch):
    monkeypatch.setattr(mw, "_user_from_request", lambda r: {
        "role": "OFFICER", "tenant_id": "air1"})
    resp = _call(mw.rbac_middleware, "/api/v1/regulator/industry-averages",
                 {"role": "OFFICER"}, monkeypatch)
    assert getattr(resp, "status_code", None) == 403


def test_tenant_admin_allowed_when_module_enabled(monkeypatch):
    monkeypatch.setattr(mw, "_user_from_request", lambda r: {
        "role": "TENANT_ADMIN", "tenant_id": "air1"})
    monkeypatch.setattr(mw, "_tenant_module_enabled", lambda t, m: True)
    resp = _call(mw.rbac_middleware, "/api/v1/hazards/", {"role": "TENANT_ADMIN"}, monkeypatch)
    assert resp == {"ok": True}


def test_module_disabled_blocks_tenant_user(monkeypatch):
    monkeypatch.setattr(mw, "_user_from_request", lambda r: {
        "role": "TENANT_ADMIN", "tenant_id": "air1"})
    monkeypatch.setattr(mw, "_tenant_module_enabled", lambda t, m: False)
    resp = _call(mw.rbac_middleware, "/api/v1/hazards/", {"role": "TENANT_ADMIN"}, monkeypatch)
    assert getattr(resp, "status_code", None) == 403


def test_cross_tenant_bypasses_module_gate(monkeypatch):
    monkeypatch.setattr(mw, "_user_from_request", lambda r: {
        "role": "STATE_SMD", "tenant_id": None})
    # Even if a tenant flag lookup would deny, CAAN bypasses it.
    monkeypatch.setattr(mw, "_tenant_module_enabled", lambda t, m: False)
    resp = _call(mw.rbac_middleware, "/api/v1/regulator/industry-averages",
                 {"role": "STATE_SMD"}, monkeypatch)
    assert resp == {"ok": True}


def test_tenant_isolation_blocks_cross_tenant_param(monkeypatch):
    monkeypatch.setattr(mw, "_user_from_request", lambda r: {
        "role": "TENANT_ADMIN", "tenant_id": "air1"})
    monkeypatch.setattr(mw, "_tenant_module_enabled", lambda t, m: True)

    req = _request("/api/v1/hazards/x", user={"role": "TENANT_ADMIN"})
    req.query_params  # ensure attribute exists
    req._query_params = {"tenant_id": "air2"}

    async def _call_next(_req):
        return {"ok": True}

    # Patch query param access via scope query_string.
    req2 = Request({
        "type": "http", "method": "GET", "path": "/api/v1/hazards/x",
        "query_string": b"tenant_id=air2", "headers": [], "path_params": {},
    })
    req2.state.user = {"role": "TENANT_ADMIN", "tenant_id": "air1"}
    monkeypatch.setattr(mw, "_user_from_request", lambda r: {
        "role": "TENANT_ADMIN", "tenant_id": "air1"})
    resp = asyncio.run(mw.rbac_middleware(req2, _call_next))
    assert getattr(resp, "status_code", None) == 403


def test_unauthenticated_passthrough(monkeypatch):
    monkeypatch.setattr(mw, "_user_from_request", lambda r: None)
    resp = _call(mw.rbac_middleware, "/api/v1/hazards/", None, monkeypatch)
    assert resp == {"ok": True}


def test_has_permission_for_user_helper():
    assert mw.has_permission_for_user({"role": "TENANT_ADMIN"}, "module2") is True
    assert mw.has_permission_for_user({"role": "OFFICER"}, "module5") is False


# ============================================================================
# Integration tests — real FastAPI app + real mapped route (module1).
# These complement the unit tests above, which use an internal sentinel.
# Route: GET /api/v1/sms-maturity/{tenant_id}/cache (ENDPOINT_MODULE_MAP:
# "/api/v1/sms-maturity" -> module1).
# ============================================================================

_MAPPED_ROUTE = "/api/v1/sms-maturity/air1/cache"


def _override_route_user(role="TENANT_ADMIN", tenant_id="air1"):
    app.dependency_overrides[get_current_user] = lambda: {
        "uid": "uid1",
        "email": "admin@air1.com",
        "role": role,
        "tenant_id": tenant_id,
        "department": None,
        "claims": {"role": role, "tenant_id": tenant_id},
    }


def test_integration_valid_own_tenant_returns_200(monkeypatch, client):
    """Real route, valid own-tenant TENANT_ADMIN, module enabled -> 200."""
    monkeypatch.setattr(mw, "verify_firebase_token", lambda token: {
        "uid": "uid1", "email": "admin@air1.com",
        "role": "TENANT_ADMIN", "tenant_id": "air1",
    })
    monkeypatch.setattr(mw, "_tenant_module_enabled", lambda t, m: True)
    monkeypatch.setattr(
        sms_maturity_service, "read_sms_maturity",
        lambda tid: {"overall_sms_maturity": 3.5},
    )
    _override_route_user()

    resp = client.get(_MAPPED_ROUTE, headers={"Authorization": "Bearer test-token"})

    assert resp.status_code == 200
    assert resp.status_code != 403
    assert resp.json()["tenant_id"] == "air1"


def test_integration_module_disabled_returns_403(monkeypatch, client):
    """Real route, valid TENANT_ADMIN, tenant module flag off -> 403."""
    monkeypatch.setattr(mw, "verify_firebase_token", lambda token: {
        "uid": "uid1", "email": "admin@air1.com",
        "role": "TENANT_ADMIN", "tenant_id": "air1",
    })
    monkeypatch.setattr(mw, "_tenant_module_enabled", lambda t, m: False)
    _override_route_user()

    resp = client.get(_MAPPED_ROUTE, headers={"Authorization": "Bearer test-token"})

    assert resp.status_code == 403
