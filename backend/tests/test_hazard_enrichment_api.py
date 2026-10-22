# ============================================================================
# P3-2 — hazard enrichment API (POST /api/v1/hazards/{id}/enrich).
# ============================================================================

from fastapi.testclient import TestClient

from app.main import app
from app.middleware.auth import get_current_user
from app.services.hazard_enrichment_service import HazardEnrichmentService

client = TestClient(app)


def _user(role="OFFICER", tenant_id="air1", department="safety"):
    # so@ is the Safety Department account: only an officer of the Safety
    # department is a Safety Officer.
    return {"uid": "u1", "email": "so@air1.com", "role": role,
            "tenant_id": tenant_id, "department": department}


def test_enrich_requires_safety_role():
    """Step-3: the retired STAFF literal is gone; the least-privilege tenant
    member (USER) is still below the safety-officer gate."""
    app.dependency_overrides[get_current_user] = lambda: _user(role="USER")
    try:
        r = client.post("/api/v1/hazards/HZ-1/enrich", json={"description": "x"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_enrich_rejects_officer_outside_safety_department():
    """A Flight Ops officer is not a Safety Officer (Step-3 RBAC hardening)."""
    app.dependency_overrides[get_current_user] = lambda: _user(
        role="OFFICER", department="flight_ops")
    try:
        r = client.post("/api/v1/hazards/HZ-1/enrich", json={"description": "x"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_enrich_records_changes(monkeypatch):
    monkeypatch.setattr(HazardEnrichmentService, "enrich_hazard",
                        lambda self, hid, user, payload:
                        {"hazard_id": hid, "changes": [{"field": "description"}]})
    app.dependency_overrides[get_current_user] = lambda: _user()
    try:
        r = client.post("/api/v1/hazards/HZ-1/enrich", json={"description": "updated"})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["changes"][0]["field"] == "description"
    finally:
        app.dependency_overrides.clear()


def test_enrich_rejects_create_only_field(monkeypatch):
    # The service rejects create-only fields; the route surfaces it as 400.
    def _raise(self, hid, user, payload):
        raise ValueError("Enrichment cannot modify create-only fields: ['source']")

    monkeypatch.setattr(HazardEnrichmentService, "enrich_hazard", _raise)
    app.dependency_overrides[get_current_user] = lambda: _user()
    try:
        r = client.post("/api/v1/hazards/HZ-1/enrich", json={"source": "mandatory"})
        assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_enrich_empty_body_rejected():
    app.dependency_overrides[get_current_user] = lambda: _user()
    try:
        r = client.post("/api/v1/hazards/HZ-1/enrich", json={})
        assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()
