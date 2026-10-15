# ============================================================================
# 3C.2C — canonical role compatibility + regulator mutation boundaries.
#
# Fully isolated: denials precede any service call; allowed reads use
# monkeypatched service methods returning canned data. No database,
# Firebase, or network contact occurs.
# ============================================================================

import pytest
from fastapi.testclient import TestClient

from app.middleware.auth import get_current_user
import app.routes.can_cap as can_cap_routes
import app.routes.hazards as hazards_routes
import app.routes.occurrence_reports as occ_routes


def _user(role, tenant_id="t1", email=None):
    return {"uid": "u-" + role.lower(), "email": email or f"{role.lower()}@x.test",
            "role": role, "tenant_id": tenant_id}


@pytest.fixture
def client(monkeypatch):
    from app.main import app

    app.dependency_overrides.clear()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _override(role, tenant_id="t1"):
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: _user(role, tenant_id)


# ---------------------------------------------------------------------------
# STATE_SMD write denial (tenantless AND populated tenant — tenant_id must
# never widen regulator access)
# ---------------------------------------------------------------------------

CAN_BODY = {
    "hazard_id": "H-1", "title": "Engine vibration",
    "description": "Sustained vibration above limits during climb",
    "required_action": "Inspect engine mounts",
    "target_completion_date": "2026-12-31T00:00:00Z",
    "assigned_to": "Maintenance", "priority": "High",
}
CAP_BODY = {
    "can_id": "c1", "action_plan": "Replace mounts and re-test engine",
    "timeline": "7 days", "target_completion_date": "2026-12-31T00:00:00Z",
}


@pytest.mark.parametrize("tenant_id", [None, "t1"])
@pytest.mark.parametrize("role", ["STATE_SMD", "CAAN_SMD"])
def test_regulator_cannot_issue_can(client, role, tenant_id):
    _override(role, tenant_id)
    r = client.post("/api/v1/cans/", json=CAN_BODY)
    assert r.status_code == 403
    if tenant_id is not None:
        # Populated tenant proves the role block fires independently of
        # the tenant check (F-P1-4: no reliance on tenant_id=None).
        assert "READ-ONLY" in r.text


@pytest.mark.parametrize("tenant_id", [None, "t1"])
@pytest.mark.parametrize("role", ["STATE_SMD", "CAAN_SMD"])
def test_regulator_cannot_change_can_status(client, role, tenant_id):
    _override(role, tenant_id)
    r = client.patch("/api/v1/cans/c1/status", params={"status": "Closed"})
    assert r.status_code == 403


@pytest.mark.parametrize("tenant_id", [None, "t1"])
def test_regulator_cannot_delete_can(client, tenant_id):
    _override("STATE_SMD", tenant_id)
    r = client.delete("/api/v1/cans/c1")
    assert r.status_code == 403


@pytest.mark.parametrize("tenant_id", [None, "t1"])
def test_regulator_cannot_submit_cap(client, tenant_id):
    _override("STATE_SMD", tenant_id)
    r = client.post("/api/v1/cans/c1/caps", json=CAP_BODY)
    assert r.status_code == 403


def test_regulator_cannot_review_cap_even_with_tenant(client):
    _override("STATE_SMD", "t1")
    r = client.patch("/api/v1/cans/caps/cap1/review", json={"status": "Completed"})
    assert r.status_code == 403


def test_regulator_cannot_regulatory_submit_mor(client, monkeypatch):
    _override("STATE_SMD", "t1")
    r = client.post("/api/v1/reports/r1/regulatory-submit", json={})
    assert r.status_code == 403
    assert "READ-ONLY" in r.text


def test_unauthenticated_cannot_issue_can(client):
    r = client.post("/api/v1/cans/", json={"title": "x"})
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Canonical regulator reads preserved
# ---------------------------------------------------------------------------

def test_state_smd_hazard_scoping_honored(client, monkeypatch):
    captured = {}

    def _fake_list(self, svc_user, filters):
        captured["tenant"] = filters.get("tenant_id")
        return []

    monkeypatch.setattr(hazards_routes.HazardService, "list_hazards", _fake_list)
    _override("STATE_SMD", None)
    r = client.get("/api/v1/hazards/", params={"tenant_id": "op-1"})
    assert r.status_code == 200
    assert captured["tenant"] == "op-1"


def test_state_smd_can_list_reports(client, monkeypatch):
    monkeypatch.setattr(occ_routes.ReportService, "get_reports",
                        lambda self, user: [])
    _override("STATE_SMD", None)
    r = client.get("/api/v1/reports/")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# OFFICER canonical equivalence for raw VSR reads (+ legacy compat)
# ---------------------------------------------------------------------------

def test_officer_can_read_report_list(client, monkeypatch):
    monkeypatch.setattr(occ_routes.ReportService, "get_reports",
                        lambda self, user: [])
    _override("OFFICER", "t1")
    assert client.get("/api/v1/reports/").status_code == 200


def test_legacy_safety_officer_still_admitted(client, monkeypatch):
    monkeypatch.setattr(occ_routes.ReportService, "get_reports",
                        lambda self, user: [])
    _override("SAFETY_OFFICER", "t1")
    assert client.get("/api/v1/reports/").status_code == 200


def test_staff_cannot_read_report_list(client):
    _override("STAFF", "t1")
    r = client.get("/api/v1/reports/")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Tenant workflows unaffected (mocked services, session tenant authoritative)
# ---------------------------------------------------------------------------

def test_tenant_admin_can_issue_can(client, monkeypatch):
    captured = {}

    def _fake_issue(self, payload, user):
        captured["tenant"] = user["tenant_id"]
        return {"id": "c1", "can_reference": "CAN-1", "title": payload.get("title"),
                "status": "Open", "priority": "High"}

    monkeypatch.setattr(can_cap_routes.CanCapService, "issue_can", _fake_issue)
    monkeypatch.setattr(can_cap_routes, "log_audit", lambda **kw: None)
    _override("TENANT_ADMIN", "t1")
    r = client.post("/api/v1/cans/", json=CAN_BODY)
    assert r.status_code == 201
    assert captured["tenant"] == "t1"


def test_tenant_admin_mor_submit_allowed(client, monkeypatch):
    _override("TENANT_ADMIN", "t1")
    # can_submit_mor parity: canonical regulator name admitted like legacy.
    from app.routes.occurrence_reports import can_submit_mor

    assert can_submit_mor(_user("TENANT_ADMIN", "t1")) is True
    assert can_submit_mor(_user("STATE_SMD", None)) is True
    assert can_submit_mor(_user("CAAN_SMD", None)) is True
    assert can_submit_mor(_user("STAFF", "t1")) is False
    assert can_submit_mor(None) is False
