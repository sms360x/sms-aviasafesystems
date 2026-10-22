"""H1 — /api/v1/nhrc auth + tenant-match gate (SECURITY_REVIEW H1 remediation).

Previously all N-HRC routes had no auth dependency: any internet caller could
read per-tenant or State-aggregated KPIs cross-tenant. Now:

  * Every route requires a valid Firebase ID token (Depends(get_current_user)).
  * GET /nhrc/tenant/{tenant_id}/kpis additionally requires the caller's
    tenant_id to match {tenant_id} unless the role is cross-tenant
    (STATE_SMD / SUPER_ADMIN) — shared require_tenant_access helper.
  * GET /nhrc/state/kpis is a State aggregate and requires the CAAN role
    (Depends(get_caan_user)).

Covers:
  GET  /nhrc/tenant/{tenant_id}/kpis
  GET  /nhrc/state/kpis
  GET  /nhrc/mapping-rules
  GET  /nhrc/seis/{nhrc}
  GET  /nhrc/contributing-factors/{nhrc}
"""

from fastapi.testclient import TestClient

from app.main import app
from app.middleware import auth as auth_mw
from app.middleware import rbac_middleware as mw
from app.middleware.auth import get_current_user
from app.middleware.rbac_middleware import get_module_for_path
from app.services.nhrc_service import NHRCService


NHRC_URLS = [
    "/api/v1/nhrc/tenant/fixedwing/kpis",
    "/api/v1/nhrc/state/kpis",
    "/api/v1/nhrc/mapping-rules",
    "/api/v1/nhrc/seis/CFIT",
    "/api/v1/nhrc/contributing-factors/CFIT",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _airline_user(role="TENANT_ADMIN", tenant_id="fixedwing"):
    return {
        "uid": "u-fw",
        "email": "safety@fixedwing.com.np",
        "role": role,
        "tenant_id": tenant_id,
        "department": "safety",
        "claims": {"role": role, "tenant_id": tenant_id},
    }


def _caan_user():
    return {
        "uid": "u-caan",
        "email": "smd@caanepal.gov.np",
        "role": "STATE_SMD",
        "tenant_id": None,
        "department": None,
        "claims": {"role": "STATE_SMD", "tenant_id": None},
    }


def _super_admin_user():
    return {
        "uid": "u-sa",
        "email": "admin@aviasafesystems.com",
        "role": "SUPER_ADMIN",
        "tenant_id": None,
        "department": None,
        "claims": {"role": "SUPER_ADMIN", "tenant_id": None},
    }


def _override(user):
    app.dependency_overrides[get_current_user] = lambda: user


def _patch_service(monkeypatch):
    monkeypatch.setattr(NHRCService, "calculate_nhrc_kpis", lambda self, tid: [])
    monkeypatch.setattr(NHRCService, "calculate_state_nhrc_kpis", lambda self: [])


# ---------------------------------------------------------------------------
# Unauthenticated — must be rejected
# ---------------------------------------------------------------------------

def test_nhrc_routes_reject_unauthenticated():
    c = TestClient(app)
    for url in NHRC_URLS:
        resp = c.get(url)
        assert resp.status_code in (401, 403), (url, resp.status_code)


# ---------------------------------------------------------------------------
# GET /tenant/{tid}/kpis — tenant-match enforcement
# ---------------------------------------------------------------------------

def test_tenant_kpis_allow_own_tenant(monkeypatch):
    _patch_service(monkeypatch)
    _override(_airline_user(tenant_id="fixedwing"))
    try:
        resp = TestClient(app).get("/api/v1/nhrc/tenant/fixedwing/kpis")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json() == []


def test_tenant_kpis_reject_cross_tenant(monkeypatch):
    _patch_service(monkeypatch)
    _override(_airline_user(tenant_id="fixedwing"))
    try:
        resp = TestClient(app).get("/api/v1/nhrc/tenant/rotarywing/kpis")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 403
    assert "tenant" in resp.json()["detail"].lower()


def test_tenant_kpis_allow_caan_any_tenant(monkeypatch):
    _patch_service(monkeypatch)
    _override(_caan_user())
    try:
        resp = TestClient(app).get("/api/v1/nhrc/tenant/rotarywing/kpis")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json() == []


def test_tenant_kpis_allow_super_admin_any_tenant(monkeypatch):
    _patch_service(monkeypatch)
    _override(_super_admin_user())
    try:
        resp = TestClient(app).get("/api/v1/nhrc/tenant/demoairport/kpis")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /state/kpis — STATE_SMD role only (state-level aggregate)
# ---------------------------------------------------------------------------

def test_state_kpis_reject_airline_user(monkeypatch):
    _patch_service(monkeypatch)
    _override(_airline_user(tenant_id="fixedwing"))
    try:
        resp = TestClient(app).get("/api/v1/nhrc/state/kpis")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 403
    assert "STATE_SMD" in resp.json()["detail"]


def test_state_kpis_allow_caan_user(monkeypatch):
    _patch_service(monkeypatch)
    _override(_caan_user())
    try:
        resp = TestClient(app).get("/api/v1/nhrc/state/kpis")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200


def test_state_kpis_allow_super_admin(monkeypatch):
    _patch_service(monkeypatch)
    _override(_super_admin_user())
    try:
        resp = TestClient(app).get("/api/v1/nhrc/state/kpis")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Non-tenant, non-state routes — any authenticated user
# ---------------------------------------------------------------------------

def test_mapping_rules_allow_authenticated_user():
    _override(_airline_user())
    try:
        resp = TestClient(app).get("/api/v1/nhrc/mapping-rules")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_seis_allow_authenticated_user():
    _override(_airline_user())
    try:
        resp = TestClient(app).get("/api/v1/nhrc/seis/CFIT")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_contributing_factors_allow_authenticated_user():
    _override(_airline_user())
    try:
        resp = TestClient(app).get("/api/v1/nhrc/contributing-factors/WS")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert len(resp.json()) > 0


# ---------------------------------------------------------------------------
# Invalid token — rejected (exercises real token verification, not an override)
# ---------------------------------------------------------------------------

def test_nhrc_routes_reject_invalid_token(monkeypatch):
    monkeypatch.setattr(auth_mw, "verify_firebase_token", lambda token: None)
    monkeypatch.setattr(mw, "verify_firebase_token", lambda token: None)
    c = TestClient(app)
    for url in ("/api/v1/nhrc/state/kpis", "/api/v1/nhrc/tenant/fixedwing/kpis"):
        resp = c.get(url, headers={"Authorization": "Bearer invalid-token"})
        assert resp.status_code in (401, 403), (url, resp.status_code)


# ---------------------------------------------------------------------------
# RBAC middleware module map (documented, not altered)
# ---------------------------------------------------------------------------

def test_nhrc_state_path_is_in_middleware_module_map():
    # /api/v1/nhrc/state is module-gated by the RBAC middleware (module5).
    assert get_module_for_path("/api/v1/nhrc/state/kpis") == "module5"


def test_nhrc_tenant_path_is_in_middleware_module_map_as_module2():
    # Updated by 1A.4 (2026-10-08): /api/v1/nhrc/tenant is now in
    # ENDPOINT_MODULE_MAP as module2. Route-level auth (get_current_user +
    # require_tenant_access) still applies.
    assert get_module_for_path("/api/v1/nhrc/tenant/fixedwing/kpis") == "module2"