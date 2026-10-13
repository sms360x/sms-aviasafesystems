# ============================================================================
# 1C.1 — VSR visibility rule (VSR_VISIBILITY_RULE = "A").
#
# Raw VSR (narrative + reporter metadata) is visible only to the owning
# tenant's Safety Manager (TENANT_ADMIN / AIRLINE_ADMIN) and the Safety
# Department officer (SAFETY_OFFICER). Any other same-tenant role is denied at
# the route layer. Cross-tenant callers stay denied (1A.7). MOR/other report
# types are unchanged.
#
# Corrected 2026-10-10: SAFETY_OFFICER added to the allowed list (SME ruling);
# the literal `SAFETY_OFFICER` is keyed, not the dual-accept OFFICER alias.
#
# Deterministic (no live DB): the route layer is exercised through FastAPI's
# TestClient with the auth dependency overridden and ReportService methods
# monkeypatched.
# ============================================================================

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.auth import get_current_user
from app.services.report_service import ReportService

client = TestClient(app)

TENANT = "air1"


def _user(role, tenant_id=TENANT):
    return {
        "uid": "u1",
        "email": f"u1@{str(role).lower()}.example.com",
        "role": role,
        "tenant_id": tenant_id,
        "department": None,
        "claims": {"role": role, "tenant_id": tenant_id},
    }


def _report(report_type="voluntary"):
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
        "reporter_name": "Jane Reporter",
        "reporter_email": "jane@example.com",
        "reporter_phone": "+977-9800000000",
        "is_anonymous": False,
        "etops": False,
        "manufacturer_advised": False,
        "fdr_data_retained": False,
    }


def _override(role, tenant_id=TENANT):
    app.dependency_overrides[get_current_user] = lambda: _user(role, tenant_id)


def _clear():
    app.dependency_overrides.clear()


def _patch_detail(monkeypatch, doc):
    monkeypatch.setattr(ReportService, "get_report_by_id",
                        lambda self, report_id, user: doc)


def _patch_list(monkeypatch, rows):
    monkeypatch.setattr(ReportService, "get_reports",
                        lambda self, user: rows)


def _list_row():
    now = datetime.now(timezone.utc)
    return {
        "id": str(uuid.uuid4()), "tenant_id": TENANT, "report_type": "voluntary",
        "status": "NEW", "ai_status": "PENDING", "location": "KTM",
        "occurrence_date": now, "created_by": "u1", "created_at": now,
        "is_anonymous": False,
    }


# T1 — TENANT_ADMIN (Safety Manager) of the owning tenant sees the raw VSR.
def test_tenant_admin_receives_raw_vsr(monkeypatch):
    _patch_detail(monkeypatch, _report("voluntary"))
    _override("TENANT_ADMIN")
    try:
        r = client.get(f"/api/v1/reports/{uuid.uuid4()}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["report_type"] == "voluntary"
        assert body["narrative"] == "raw narrative text"
        assert body["reporter_name"] == "Jane Reporter"
        assert body["reporter_email"] == "jane@example.com"
    finally:
        _clear()


# T2 — SAFETY_OFFICER (Safety Department officer) of the owning tenant sees the
#      raw VSR.
def test_safety_officer_receives_raw_vsr(monkeypatch):
    _patch_detail(monkeypatch, _report("voluntary"))
    _override("SAFETY_OFFICER")
    try:
        r = client.get(f"/api/v1/reports/{uuid.uuid4()}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["narrative"] == "raw narrative text"
        assert body["reporter_name"] == "Jane Reporter"
    finally:
        _clear()


# T3 — ACCOUNTABLE_EXECUTIVE of the owning tenant is denied the raw VSR.
def test_accountable_executive_denied_raw_vsr(monkeypatch):
    _patch_detail(monkeypatch, _report("voluntary"))
    _override("ACCOUNTABLE_EXECUTIVE")
    try:
        r = client.get(f"/api/v1/reports/{uuid.uuid4()}")
        assert r.status_code == 403, r.text
        assert "narrative" not in r.text
        assert "Jane Reporter" not in r.text
    finally:
        _clear()


# T4 — DEPT_ADMIN is denied the raw VSR.
def test_dept_admin_denied_raw_vsr(monkeypatch):
    _patch_detail(monkeypatch, _report("voluntary"))
    _override("DEPT_ADMIN")
    try:
        r = client.get(f"/api/v1/reports/{uuid.uuid4()}")
        assert r.status_code == 403, r.text
    finally:
        _clear()


# T5 — OFFICER (the dual-accept rename, not the Safety Department literal) is
#      denied raw VSR: the rule keys on the literal `SAFETY_OFFICER`.
def test_officer_denied_raw_vsr(monkeypatch):
    _patch_detail(monkeypatch, _report("voluntary"))
    _override("OFFICER")
    try:
        r = client.get(f"/api/v1/reports/{uuid.uuid4()}")
        assert r.status_code == 403, r.text
    finally:
        _clear()


# T6 — USER / STAFF are denied the raw VSR.
@pytest.mark.parametrize("role", ["USER", "STAFF"])
def test_staff_denied_raw_vsr(monkeypatch, role):
    _patch_detail(monkeypatch, _report("voluntary"))
    _override(role)
    try:
        r = client.get(f"/api/v1/reports/{uuid.uuid4()}")
        assert r.status_code == 403, r.text
    finally:
        _clear()


# T7 — Cross-tenant callers still get 404 for a VSR (regression of 1A.7).
def test_cross_tenant_vsr_returns_404(monkeypatch):
    _patch_detail(monkeypatch, None)
    _override("STATE_SMD", tenant_id=None)
    try:
        r = client.get(f"/api/v1/reports/{uuid.uuid4()}")
        assert r.status_code == 404, r.text
    finally:
        _clear()


# List endpoint: allowed roles are the Safety Manager + SAFETY_OFFICER.
@pytest.mark.parametrize("role", ["TENANT_ADMIN", "SAFETY_OFFICER"])
def test_list_allowed_for_raw_vsr_roles(monkeypatch, role):
    _patch_list(monkeypatch, [_list_row()])
    _override(role)
    try:
        r = client.get("/api/v1/reports/")
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body) == 1
        # List projection carries no narrative or reporter metadata.
        assert "narrative" not in body[0]
        assert "reporter_name" not in body[0]
        assert "reporter_email" not in body[0]
    finally:
        _clear()


# List endpoint: every other same-tenant role is denied.
@pytest.mark.parametrize("role", [
    "ACCOUNTABLE_EXECUTIVE", "DEPT_ADMIN", "OFFICER", "USER", "STAFF",
])
def test_list_denied_for_non_raw_vsr_roles(monkeypatch, role):
    _override(role)
    try:
        r = client.get("/api/v1/reports/")
        assert r.status_code == 403, r.text
    finally:
        _clear()


# A non-VSR report (MOR) is unaffected: normal same-tenant access applies.
def test_mor_detail_unaffected_for_non_admin(monkeypatch):
    _patch_detail(monkeypatch, _report("mandatory"))
    _override("DEPT_ADMIN")
    try:
        r = client.get(f"/api/v1/reports/{uuid.uuid4()}")
        assert r.status_code == 200, r.text
        assert r.json()["report_type"] == "mandatory"
    finally:
        _clear()
