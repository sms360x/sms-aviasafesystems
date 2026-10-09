"""Item 1A.8 — hazard_analysis.py authentication + session-derived tenant.

The router in ``backend/app/api/v1/hazard_analysis.py`` previously took a
required caller-supplied ``X-Tenant-Id`` header and had no auth dependency, so
any internet caller could write hazards / RCA / assessments / CAPAs into an
arbitrary tenant's registry. It now:

  * requires an authenticated session via ``get_tenant_user`` on every route,
  * derives the tenant from the session claims, never from the request header.

The router is currently NOT mounted in ``app/api/v1/router.py`` (documented in
``hazard_service.py:14``). These tests therefore mount it on a test-local
FastAPI app so the auth wiring is exercised directly; no production mount is
changed by 1A.8.

Covers:
  * unauthenticated request on every route        -> 401/403
  * authenticated session tenant                  -> 201, service called with session tenant
  * X-Tenant-Id header differing from session     -> ignored (session tenant used)
  * cross-tenant role without a tenant            -> 403 (get_tenant_user)
  * source no longer declares an X-Tenant-Id header
"""

import inspect

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import hazard_analysis
from app.api.v1.hazard_analysis import router, get_hazard_service
from app.middleware.auth import get_current_user, get_tenant_user


CREATE_URL = "/api/v1/hazards"
RCA_URL = "/api/v1/hazards/H1/rca"
ASSESS_URL = "/api/v1/hazards/H1/assessments"
CAPA_URL = "/api/v1/hazards/H1/capas"

DEPARTMENT_USER = {
    "uid": "u-145",
    "email": "145@fixedwing.com.np",
    "role": "OFFICER",
    "tenant_id": "fixedwing",
    "department": "Part-145",
}

SAFETY_USER = {
    "uid": "u-safety",
    "email": "safety@fixedwing.com.np",
    "role": "SAFETY_OFFICER",
    "tenant_id": "fixedwing",
    "department": "Safety",
}

CROSS_TENANT_USER = {
    "uid": "u-caan",
    "email": "smd@caanepal.gov.np",
    "role": "CAAN_SMD",
    "tenant_id": None,
    "department": None,
}


HAZARD_BODY = {
    "title": "Engine vibration on climb",
    "description": "Repeated engine vibration reported during climb out of KTM.",
    "source_type": "voluntary_report",
    "functional_area": "flight_operations",
    "assigned_owner_email": "owner@fixedwing.com.np",
}

RCA_BODY = {
    "tier": 2,
    "category": "PRECOND",
    "subcategory": "crew",
    "nanocode": "PE101",
    "definition": "Adverse mental state",
    "contributing_narrative": "Crew reported fatigue during the sector.",
    "order_sequence": 1,
}

ASSESS_BODY = {
    "assessment_type": "initial",
    "severity_score": 3,
    "severity_justification": "Major reduction in safety margins.",
    "probability_score": "C",
    "probability_justification": "Remote but possible.",
}

CAPA_BODY = {
    "action_type": "corrective",
    "title": "Replace vibration sensor",
    "details": "Replace the vibration sensor and inspect the engine mount.",
    "responsible_department": "Part-145",
    "assignee_email": "eng@fixedwing.com.np",
    "due_date": "2026-11-01T00:00:00Z",
}


class _FakeService:
    def __init__(self):
        self.calls = []

    async def create_hazard(self, *args, **kwargs):
        self.calls.append(("create_hazard", args, kwargs))
        return "HAZ-TEST-0001"

    async def add_rca_factor(self, *args, **kwargs):
        self.calls.append(("add_rca_factor", args, kwargs))
        return "rca_test"

    async def record_assessment(self, *args, **kwargs):
        self.calls.append(("record_assessment", args, kwargs))
        return {"id": "asm_test", "risk_index": "3C"}

    async def add_capa(self, *args, **kwargs):
        self.calls.append(("add_capa", args, kwargs))
        return "capa_test"


def _client(*, user=None, service=None, override_current_user=None):
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")
    if user is not None:
        test_app.dependency_overrides[get_tenant_user] = lambda: user
    if service is not None:
        test_app.dependency_overrides[get_hazard_service] = lambda: service
    if override_current_user is not None:
        test_app.dependency_overrides[get_current_user] = lambda: override_current_user
    return TestClient(test_app)


# ---------------------------------------------------------------------------
# Unauthenticated — every route must reject
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url,body",
    [
        (CREATE_URL, HAZARD_BODY),
        (RCA_URL, RCA_BODY),
        (ASSESS_URL, ASSESS_BODY),
        (CAPA_URL, CAPA_BODY),
    ],
)
def test_routes_reject_unauthenticated(url, body):
    resp = _client().post(url, json=body)
    assert resp.status_code in (401, 403), (url, resp.status_code)


# ---------------------------------------------------------------------------
# Authenticated session tenant — both workflows succeed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url,body,method",
    [
        (CREATE_URL, HAZARD_BODY, "create_hazard"),
        (RCA_URL, RCA_BODY, "add_rca_factor"),
        (ASSESS_URL, ASSESS_BODY, "record_assessment"),
        (CAPA_URL, CAPA_BODY, "add_capa"),
    ],
)
@pytest.mark.parametrize("user", [DEPARTMENT_USER, SAFETY_USER])
def test_authenticated_session_tenant_accepted(url, body, method, user):
    service = _FakeService()
    resp = _client(user=user, service=service).post(url, json=body)
    assert resp.status_code == 201, resp.text
    assert service.calls, "service was not called"
    name, args, _ = service.calls[0]
    assert name == method
    # tenant_id is the first positional arg for every method.
    assert args[0] == "fixedwing"


# ---------------------------------------------------------------------------
# X-Tenant-Id header must be ignored in favour of the session tenant
# ---------------------------------------------------------------------------

def test_header_value_is_ignored_when_it_differs_from_session():
    service = _FakeService()
    resp = _client(user=DEPARTMENT_USER, service=service).post(
        CREATE_URL,
        json=HAZARD_BODY,
        headers={"X-Tenant-Id": "victim-airline"},
    )
    assert resp.status_code == 201, resp.text
    _, args, _ = service.calls[0]
    assert args[0] == "fixedwing"
    assert args[0] != "victim-airline"


# ---------------------------------------------------------------------------
# Cross-tenant role without a tenant is rejected (not a cross-tenant route)
# ---------------------------------------------------------------------------

def test_cross_tenant_role_without_tenant_rejected():
    service = _FakeService()
    resp = _client(service=service, override_current_user=CROSS_TENANT_USER).post(
        CREATE_URL, json=HAZARD_BODY
    )
    assert resp.status_code == 403
    assert not service.calls


# ---------------------------------------------------------------------------
# Regression pin: the module no longer reads X-Tenant-Id
# ---------------------------------------------------------------------------

def test_source_does_not_accept_x_tenant_id_header():
    # The module must not import Header and no route may declare the
    # caller-supplied tenant parameter.
    assert "Header" not in hazard_analysis.__dict__
    routes = (
        hazard_analysis.create_new_hazard,
        hazard_analysis.attach_hfacs_rca,
        hazard_analysis.record_risk_matrix_assessment,
        hazard_analysis.create_hazard_capa,
    )
    for fn in routes:
        params = inspect.signature(fn).parameters
        assert "x_tenant_id" not in params
        assert "user" in params
