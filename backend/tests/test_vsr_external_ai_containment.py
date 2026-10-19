# ============================================================================
# Phase 3C AI-4 — VSR external-AI containment.
#
# Voluntary Safety Reports (VSRs) must never be transmitted to external AI
# (Gemini). The report is still stored, retains its narrative, remains readable
# by authorized Safety Department staff, and is recorded with a truthful
# skipped AI state (no fabricated model/confidence/risk values).
#
# Deterministic and OFFLINE: the routes are exercised through FastAPI's
# TestClient with the auth dependency overridden and ReportService methods
# monkeypatched. No database, no Redis, no external provider is contacted.
# ============================================================================

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from loguru import logger

from app.main import app
from app.middleware.auth import get_current_user, get_tenant_user
from app.models.report import AiStatus, ReportResponse
from app.services.report_service import (
    VSR_EXTERNAL_AI_POLICY,
    ReportService,
    external_ai_blocked_for_report_type,
)

client = TestClient(app)

TENANT = "air1"


# ---------------------------------------------------------------- helpers ---

def _user(role="OFFICER", tenant_id=TENANT, department="safety"):
    return {
        "uid": "u1",
        "email": f"u1@{str(role).lower()}.example.com",
        "role": role,
        "tenant_id": tenant_id,
        "department": department,
        "claims": {"role": role, "tenant_id": tenant_id,
                   "department": department},
    }


def _stored(report_type):
    now = datetime.now(timezone.utc)
    return {
        "id": str(uuid.uuid4()),
        "tenant_id": TENANT,
        "report_type": report_type,
        "status": "NEW",
        "ai_status": "PENDING",
        "narrative": "raw narrative text",
        "location": "KTM",
        "occurrence_date": now,
        "created_by": "u1",
        "created_at": now,
        "updated_at": now,
        "is_anonymous": False,
        "etops": False,
        "manufacturer_advised": False,
        "fdr_data_retained": False,
    }


@pytest.fixture
def offline_submit(monkeypatch):
    """Wire the submission routes to spies with no DB / no AI side effects."""
    calls = {"create": [], "skip": [], "run_ai": []}

    def _create_report(self, payload, user):
        row = _stored(payload.get("report_type", "voluntary"))
        row["narrative"] = payload.get("narrative", row["narrative"])
        calls["create"].append(row["id"])
        return row

    monkeypatch.setattr(ReportService, "create_report", _create_report)
    monkeypatch.setattr(
        ReportService, "mark_external_ai_skipped",
        lambda self, report_id: calls["skip"].append(report_id),
    )
    monkeypatch.setattr(
        ReportService, "run_ai_analysis",
        lambda self, report_id, narrative: calls["run_ai"].append((report_id, narrative)),
    )
    # No hazard creation, no audit write, and — defensively — Gemini can never
    # be reached.
    monkeypatch.setattr(
        "app.routes.occurrence_reports._auto_create_hazard_from_report",
        lambda stored, user: None,
    )
    monkeypatch.setattr("app.routes.occurrence_reports.log_audit", lambda **kw: None)

    def _forbidden(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("external AI must not be invoked for a VSR")

    monkeypatch.setattr("app.services.gemini.analyze_report", _forbidden)
    monkeypatch.setattr("app.services.report_service.analyze_report", _forbidden)
    monkeypatch.setattr("app.services.report_service.classify_mandatory", lambda n: {})

    app.dependency_overrides[get_tenant_user] = lambda: _user()
    try:
        yield calls
    finally:
        app.dependency_overrides.clear()


# ------------------------------------------------------------- pure policy --

@pytest.mark.parametrize("value,blocked", [
    ("voluntary", True),
    ("VOLUNTARY", True),
    (" Voluntary ", True),
    ("mandatory", False),
    ("", False),
    (None, False),
])
def test_external_ai_blocked_for_report_type(value, blocked):
    assert external_ai_blocked_for_report_type(value) is blocked


def test_ai_status_enum_exposes_skipped():
    assert AiStatus.SKIPPED == "SKIPPED"


# --------------------------------------------------------------- VSR route --

def test_vsr_submit_records_skip_and_never_calls_ai(offline_submit):
    body = {
        "narrative": "Voluntary report narrative that must stay internal.",
        "location": "KTM",
        "occurrence_date": datetime.now(timezone.utc).isoformat(),
    }
    resp = client.post("/api/v1/reports/vsr", json=body)
    assert resp.status_code == 201, resp.text

    # A truthful skipped state is recorded; external AI is never scheduled.
    assert len(offline_submit["skip"]) == 1
    assert offline_submit["run_ai"] == []
    # Normal receipt is returned, with the original narrative preserved.
    data = resp.json()
    assert data["report_type"] == "voluntary"
    assert data["narrative"] == body["narrative"]


def test_legacy_voluntary_submit_follows_vsr_policy(offline_submit):
    body = {
        "narrative": "Legacy-path voluntary report.",
        "location": "KTM",
        "occurrence_date": datetime.now(timezone.utc).isoformat(),
        "report_type": "voluntary",
    }
    resp = client.post("/api/v1/reports/", json=body)
    assert resp.status_code == 201, resp.text
    assert len(offline_submit["skip"]) == 1
    assert offline_submit["run_ai"] == []


def test_legacy_mandatory_submit_still_schedules_ai(offline_submit):
    body = {
        "narrative": "Mandatory-path report keeps its AI scheduling.",
        "location": "KTM",
        "occurrence_date": datetime.now(timezone.utc).isoformat(),
        "report_type": "mandatory",
    }
    resp = client.post("/api/v1/reports/", json=body)
    assert resp.status_code == 201, resp.text
    assert offline_submit["skip"] == []
    assert len(offline_submit["run_ai"]) == 1
    assert offline_submit["run_ai"][0][1] == body["narrative"]


def test_mor_route_still_schedules_ai(monkeypatch):
    calls = {"skip": [], "run_ai": []}
    monkeypatch.setattr(ReportService, "create_report",
                        lambda self, payload, user: _stored("mandatory"))
    monkeypatch.setattr(ReportService, "mark_external_ai_skipped",
                        lambda self, report_id: calls["skip"].append(report_id))
    monkeypatch.setattr(ReportService, "run_ai_analysis",
                        lambda self, report_id, narrative: calls["run_ai"].append(report_id))
    monkeypatch.setattr("app.routes.occurrence_reports._auto_create_hazard_from_report",
                        lambda stored, user: None)
    monkeypatch.setattr("app.routes.occurrence_reports.log_audit", lambda **kw: None)
    monkeypatch.setattr("app.services.regulatory_timer_service.set_mor_deadline",
                        lambda *a, **k: None)
    monkeypatch.setattr("app.services.report_service.analyze_report", lambda n: {})
    monkeypatch.setattr("app.services.report_service.classify_mandatory", lambda n: {})

    app.dependency_overrides[get_tenant_user] = lambda: _user("AIRLINE_ADMIN")
    try:
        body = {
            "reporter_name": "Jane Reporter",
            "reporter_role": "pilot",
            "reporter_organisation": "AviaSAFE Air",
            "reporter_email": "jane@example.com",
            "aircraft_make": "Boeing",
            "aircraft_model": "737",
            "aircraft_registration": "9N-ABC",
            "operator": "AviaSAFE Air",
            "aircraft_category": "Aeroplane",
            "flight_type": "Commercial",
            "flight_phase": "Landing",
            "occurrence_date_time": datetime.now(timezone.utc).isoformat(),
            "occurrence_location": "KTM",
            "occurrence_country": "Nepal",
            "occurrence_type": "INCIDENT",
            "occurrence_class": "CLASS_C",
            "occurrence_category": "SYS",
            "narrative": "Mandatory occurrence narrative.",
        }
        resp = client.post("/api/v1/reports/mor", json=body)
        assert resp.status_code == 201, resp.text
        assert calls["skip"] == []
        assert len(calls["run_ai"]) == 1
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------- truthful read surface --

def test_skipped_vsr_reads_back_truthfully(monkeypatch):
    now = datetime.now(timezone.utc)
    doc = _stored("voluntary")
    doc.update({"ai_status": "SKIPPED", "ai_analysis": None,
                "updated_at": now})
    monkeypatch.setattr(ReportService, "get_report_by_id",
                        lambda self, report_id, user: doc)
    app.dependency_overrides[get_current_user] = lambda: _user("TENANT_ADMIN")
    try:
        r = client.get(f"/api/v1/reports/{doc['id']}")
        assert r.status_code == 200, r.text
        body = r.json()
        # Truthful: no fabricated analysis is returned.
        assert body["ai_status"] == "SKIPPED"
        assert body["ai_analysis"] is None
        assert body["ai_suggested_assessment"] is None
        # Original report content is preserved for authorized users.
        assert body["narrative"] == "raw narrative text"
    finally:
        app.dependency_overrides.clear()


def test_legacy_report_without_new_metadata_still_serializes():
    now = datetime.now(timezone.utc)
    legacy = {
        "id": str(uuid.uuid4()),
        "tenant_id": TENANT,
        "report_type": "voluntary",
        "status": "NEW",
        "ai_status": "PENDING",
        "narrative": "legacy narrative",
        "location": "KTM",
        "occurrence_date": now,
        "created_by": "u1",
        "created_at": now,
        "updated_at": now,
        "etops": False,
        "manufacturer_advised": False,
        "fdr_data_retained": False,
    }
    model = ReportResponse(**legacy)
    assert model.ai_status == AiStatus.PENDING
    assert model.ai_analysis is None


def test_policy_constant_is_stable():
    assert VSR_EXTERNAL_AI_POLICY == "VSR_CONFIDENTIALITY_POLICY"


# ------------------------------------------------------ logging protection ---

def test_gemini_parse_failure_does_not_log_response_text(monkeypatch):
    from app.services import gemini

    secret = "REPORTER_IDENTIFIER_SECRET_XYZ"

    class _Resp:
        text = f"{secret} — model output that is not valid json"

    class _Model:
        def generate_content(self, prompt):  # noqa: ARG002
            return _Resp()

    monkeypatch.setattr(gemini, "model", _Model())

    captured = []
    sink_id = logger.add(lambda m: captured.append(str(m)), level="ERROR")
    try:
        result = gemini.analyze_report("some narrative")
    finally:
        logger.remove(sink_id)

    # Fallback still returned, but the raw model response never reaches logs.
    assert result["summary"] == "Safety report analyzed using mock classification."
    joined = "".join(captured)
    assert secret not in joined
    assert "Failed to parse Gemini response" in joined
