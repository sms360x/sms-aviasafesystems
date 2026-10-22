# ============================================================================
# P3-1 — hazard triage API (POST/GET /api/v1/hazards/{id}/triage).
# ============================================================================

from fastapi.testclient import TestClient

from app.main import app
from app.middleware.auth import get_current_user
from app.services import hazard_triage_service as svc_mod
from app.services.hazard_triage_service import HazardTriageService

client = TestClient(app)


def _user(role="OFFICER", tenant_id="air1", department="safety"):
    # so@ is the Safety Department account: only an officer of the Safety
    # department is a Safety Officer.
    return {"uid": "u1", "email": "so@air1.com", "role": role,
            "tenant_id": tenant_id, "department": department}


def test_triage_requires_safety_role(monkeypatch):
    """Step-3: the retired STAFF literal is gone; the least-privilege tenant
    member (USER) is still below the safety-officer gate."""
    app.dependency_overrides[get_current_user] = lambda: _user(role="USER")
    try:
        r = client.post("/api/v1/hazards/HZ-1/triage", json={"decision": "Accepted"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_triage_rejects_officer_outside_safety_department():
    """A Flight Ops officer is not a Safety Officer (Step-3 RBAC hardening)."""
    app.dependency_overrides[get_current_user] = lambda: _user(
        role="OFFICER", department="flight_ops")
    try:
        r = client.post("/api/v1/hazards/HZ-1/triage", json={"decision": "Accepted"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_triage_records_decision(monkeypatch):
    monkeypatch.setattr(HazardTriageService, "triage_hazard",
                        lambda self, hid, user, dec, notes=None, initial_priority=None:
                        {"id": "t1", "decision": dec})
    app.dependency_overrides[get_current_user] = lambda: _user()
    try:
        r = client.post("/api/v1/hazards/HZ-1/triage",
                        json={"decision": "Escalated", "notes": "urgent"})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "success"
        assert body["data"]["decision"] == "Escalated"
    finally:
        app.dependency_overrides.clear()


def test_triage_rejects_bad_decision():
    app.dependency_overrides[get_current_user] = lambda: _user()
    try:
        r = client.post("/api/v1/hazards/HZ-1/triage", json={"decision": "Maybe"})
        assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_triage_list(monkeypatch):
    monkeypatch.setattr(HazardTriageService, "list_triage",
                        lambda self, hid: [{"id": "t1", "decision": "Accepted"}])
    app.dependency_overrides[get_current_user] = lambda: _user()
    try:
        r = client.get("/api/v1/hazards/HZ-1/triage")
        assert r.status_code == 200
        assert r.json()["data"][0]["decision"] == "Accepted"
    finally:
        app.dependency_overrides.clear()
