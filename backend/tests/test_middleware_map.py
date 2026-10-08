# ============================================================================
# 1A.4 — RBAC middleware map coverage for the newly-gated paths.
#
# Adds module-gate coverage for the three paths added to ENDPOINT_MODULE_MAP:
#   /api/v1/dashboard/caan -> module5
#   /api/v1/spi/tenant     -> module2
#   /api/v1/nhrc/tenant    -> module2
#
# Deliberately left UNMAPPED (documented reason; Step 2 intent):
#   /api/v1/dashboard            operator hub spans module1 + module2; a single
#                                path-level gate would block the hub. Correct
#                                enforcement is per-card in the handler (Step 2).
#   /api/v1/dashboard/admin      platform-level (no module).
#   /api/v1/nhrc/mapping-rules   static reference data, any tenant regardless
#   /api/v1/nhrc/seis/*          of module.
#   /api/v1/nhrc/contributing-factors/*
# ============================================================================

import asyncio

from fastapi.testclient import TestClient
from starlette.requests import Request

from app.main import app
from app.middleware import rbac_middleware as mw
from app.middleware.rbac_middleware import get_module_for_path


def _call(path, user, monkeypatch):
    monkeypatch.setattr(mw, "_user_from_request", lambda r: user)

    scope = {
        "type": "http", "method": "GET", "path": path, "query_string": b"",
        "headers": [], "path_params": {},
    }
    req = Request(scope)

    async def _next(_req):
        return {"ok": True}

    return asyncio.run(mw.rbac_middleware(req, _next))


TENANT = {"role": "TENANT_ADMIN", "tenant_id": "air1"}
REGULATOR = {"role": "CAAN_SMD", "tenant_id": None}


def test_new_map_entries():
    assert get_module_for_path("/api/v1/dashboard/caan/state") == "module5"
    assert get_module_for_path("/api/v1/spi/tenant/air1/values") == "module2"
    assert get_module_for_path("/api/v1/nhrc/tenant/air1/kpis") == "module2"


def test_caan_dashboard_requires_module5(monkeypatch):
    # A tenant role lacks module5 permission -> 403 from the middleware.
    resp = _call("/api/v1/dashboard/caan/state", TENANT, monkeypatch)
    assert getattr(resp, "status_code", None) == 403
    # A regulator (cross-tenant) is allowed through the gate.
    resp2 = _call("/api/v1/dashboard/caan/state", REGULATOR, monkeypatch)
    assert resp2 == {"ok": True}


def test_spi_tenant_requires_module2(monkeypatch):
    monkeypatch.setattr(mw, "_tenant_module_enabled", lambda t, m: False)
    assert getattr(_call("/api/v1/spi/tenant/air1/values", TENANT, monkeypatch), "status_code", None) == 403
    monkeypatch.setattr(mw, "_tenant_module_enabled", lambda t, m: True)
    assert _call("/api/v1/spi/tenant/air1/values", TENANT, monkeypatch) == {"ok": True}


def test_nhrc_tenant_requires_module2(monkeypatch):
    monkeypatch.setattr(mw, "_tenant_module_enabled", lambda t, m: False)
    assert getattr(_call("/api/v1/nhrc/tenant/air1/kpis", TENANT, monkeypatch), "status_code", None) == 403
    monkeypatch.setattr(mw, "_tenant_module_enabled", lambda t, m: True)
    assert _call("/api/v1/nhrc/tenant/air1/kpis", TENANT, monkeypatch) == {"ok": True}


def test_new_mapped_paths_require_auth():
    c = TestClient(app)
    for path in (
        "/api/v1/dashboard/caan/state",
        "/api/v1/spi/tenant/air1/values",
        "/api/v1/nhrc/tenant/air1/kpis",
    ):
        assert c.get(path).status_code in (401, 403), path
