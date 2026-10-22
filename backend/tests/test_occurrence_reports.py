# ============================================================================
# MOR submission gate — CAMO/QA Department Admins.
#
# The retired role literals CAMO_ADMIN / QA_ADMIN / CAMO_USER / QA_USER are
# gone (SME ruling): a CAMO/QA account is the DEPT_ADMIN of the CAMO or the
# QA department. A DEPT_ADMIN of any other department (Flight Ops, ...) must
# not be able to file a Mandatory Occurrence Report.
#
# Fully isolated: the denial precedes any service call and the accepted path
# uses a stubbed persistence layer. No database, Firebase, or network
# contact occurs.
# ============================================================================

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.auth import get_tenant_user
from app.routes import occurrence_reports as occ_routes
from app.routes.occurrence_reports import can_submit_mor

MOR_BODY = {
    "reporter_name": "Jane Reporter",
    "reporter_role": "other",
    "reporter_organisation": "AviaSAFE Air",
    "reporter_email": "jane@air1.com",
    "aircraft_make": "Boeing",
    "aircraft_model": "737",
    "aircraft_registration": "9N-ABC",
    "aircraft_category": "Aeroplane",
    "operator": "AviaSAFE Air",
    "flight_type": "Commercial",
    "flight_phase": "Landing",
    "occurrence_date_time": datetime.now(timezone.utc).isoformat(),
    "occurrence_location": "KTM",
    "occurrence_country": "NP",
    "occurrence_type": "INCIDENT",
    "occurrence_class": "CLASS_C",
    "occurrence_category": "BIRD",
    "narrative": "Mandatory occurrence narrative for the CAMO register.",
}


def _user(role, tenant_id="air1", department=None, email="user@air1.com"):
    return {"uid": "u-1", "email": email, "role": role,
            "tenant_id": tenant_id, "department": department}


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _stub_report_service(monkeypatch):
    """Replace the persistence layer with an in-memory stub."""
    captured = {}

    class _FakeReportService:
        def __init__(self, tenant_id):
            self.tenant_id = tenant_id

        def create_report(self, payload, user):
            captured["payload"] = payload
            captured["user"] = user
            now = datetime.now(timezone.utc)
            return {
                "id": "rep-1",
                "tenant_id": self.tenant_id,
                "report_type": "mandatory",
                "status": "NEW",
                "ai_status": "PENDING",
                "narrative": payload.get("narrative", ""),
                "location": payload.get("location", ""),
                "occurrence_date": now,
                "created_at": now,
                "updated_at": now,
                "created_by": user.get("uid"),
                "is_anonymous": False,
                "etops": False,
                "manufacturer_advised": False,
                "fdr_data_retained": False,
            }

        def run_ai_analysis(self, report_id, narrative):
            return None

    monkeypatch.setattr(occ_routes, "ReportService", _FakeReportService)
    monkeypatch.setattr(occ_routes, "_auto_create_hazard_from_report",
                        lambda stored, user: None)
    monkeypatch.setattr(occ_routes, "log_audit", lambda **kw: None)
    monkeypatch.setattr("app.services.regulatory_timer_service.set_mor_deadline",
                        lambda *a, **k: None)
    return captured


# ---------------------------------------------------------------------------
# Unit level — the gate itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("department", ["camo", "qa", "CAMO", "QA"])
def test_camo_qa_dept_admin_is_admitted(department):
    assert can_submit_mor(_user("DEPT_ADMIN", department=department)) is True


@pytest.mark.parametrize("department", ["flight_ops", "maintenance_145",
                                        "ground_ops", "safety", None])
def test_other_dept_admin_is_denied(department):
    assert can_submit_mor(_user("DEPT_ADMIN", department=department)) is False


def test_retired_camo_qa_role_literals_are_not_admitted():
    """The dead literals carry no privilege any more."""
    for role in ("CAMO_ADMIN", "QA_ADMIN", "CAMO_USER", "QA_USER"):
        assert can_submit_mor(_user(role, department="flight_ops")) is False


def test_tenant_admin_and_regulator_are_admitted():
    assert can_submit_mor(_user("TENANT_ADMIN")) is True
    assert can_submit_mor(_user("SUPER_ADMIN")) is True
    assert can_submit_mor(_user("STATE_SMD", tenant_id=None)) is True


def test_plain_officer_is_denied():
    """An officer is not a CAMO/QA Department Admin."""
    assert can_submit_mor(_user("OFFICER", department="safety")) is False
    assert can_submit_mor(_user("OFFICER", department="camo")) is False


def test_email_prefix_fallback_is_kept():
    """Legacy accounts provisioned before the department column still work."""
    assert can_submit_mor(_user("OFFICER", email="camo@air1.com")) is True
    assert can_submit_mor(_user("OFFICER", email="qa@air1.com")) is True


def test_empty_user_is_denied():
    assert can_submit_mor(None) is False
    assert can_submit_mor({}) is False


# ---------------------------------------------------------------------------
# Route level — POST /api/v1/reports/mor
# ---------------------------------------------------------------------------

def test_camo_dept_admin_can_submit_mor(client, monkeypatch):
    _stub_report_service(monkeypatch)
    app.dependency_overrides[get_tenant_user] = lambda: _user(
        "DEPT_ADMIN", department="camo")
    resp = client.post("/api/v1/reports/mor", json=MOR_BODY)
    assert resp.status_code == 201, resp.text
    assert resp.json()["id"] == "rep-1"


def test_qa_dept_admin_can_submit_mor(client, monkeypatch):
    _stub_report_service(monkeypatch)
    app.dependency_overrides[get_tenant_user] = lambda: _user(
        "DEPT_ADMIN", department="qa")
    resp = client.post("/api/v1/reports/mor", json=MOR_BODY)
    assert resp.status_code == 201, resp.text


def test_flight_ops_dept_admin_cannot_submit_mor(client, monkeypatch):
    _stub_report_service(monkeypatch)
    app.dependency_overrides[get_tenant_user] = lambda: _user(
        "DEPT_ADMIN", department="flight_ops")
    resp = client.post("/api/v1/reports/mor", json=MOR_BODY)
    assert resp.status_code == 403, resp.text
    assert "CAMO and QA Department Admins" in resp.json()["detail"]


def test_safety_officer_cannot_submit_mor(client, monkeypatch):
    _stub_report_service(monkeypatch)
    app.dependency_overrides[get_tenant_user] = lambda: _user(
        "OFFICER", department="safety")
    resp = client.post("/api/v1/reports/mor", json=MOR_BODY)
    assert resp.status_code == 403, resp.text
