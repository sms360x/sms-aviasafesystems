# ============================================================================
# 2D.3 — Dashboard authorization matrix verification.
#
# Verifies the SME role-visibility matrix at the HTTP boundary:
#
#   OFFICER / TENANT_ADMIN : full tenant Hazards, CANs, Aggregates
#   DEPT_ADMIN             : only own-department Hazards/CANs/Aggregates,
#                            never raw VSRs / reporter contacts
#   ACCOUNTABLE_EXECUTIVE  : aggregate KPIs + the escalated CAP queue only,
#                            never raw reports/hazards/CANs
#   STATE_SMD              : state-wide aggregates only, never raw
#                            reports/hazards/CANs
#
# Deterministic: the endpoints are exercised through FastAPI's TestClient with
# the auth dependency overridden and the persistence layer replaced by a fake
# async session. No live database is touched. The fake session returns the
# seeded rows for the table the query targets, so filtering performed by the
# real service code (SQL predicates + in-memory filters) is what the assertions
# observe.
#
# Endpoint mapping for the task's shorthand:
#   GET /hazards              -> GET /api/v1/hazards/
#   GET /cans                 -> GET /api/v1/cans/
#   GET /reports              -> GET /api/v1/reports/
#   GET /dashboard/aggregates -> no such route; the state-wide aggregate
#                                surface is GET /api/v1/dashboard/caan/overview,
#                                the AE aggregate surface is
#                                GET /api/v1/dashboard/ae/kpis.
# ============================================================================

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.ids import register_tenant
from app.db.db_models import Can, Hazard
from app.main import app
from app.middleware.auth import get_current_user
from app.services import can_cap_service as can_cap_service_mod
from app.services import hazard_service as hazard_service_mod
from app.services.can_cap_service import CanCapService
from app.services.hazard_service import HazardService
from app.services.report_service import ReportService

TENANT = "air1"
OTHER_TENANT = "air2"


# ============================================================================
# Identity helpers
# ============================================================================

def _user(role, tenant_id=TENANT, department=None):
    return {
        "uid": f"uid-{str(role).lower()}",
        "email": f"{str(role).lower()}@example.com",
        "role": role,
        "tenant_id": tenant_id,
        "department": department,
        "claims": {"role": role, "tenant_id": tenant_id, "department": department},
    }


def _override(user):
    app.dependency_overrides[get_current_user] = lambda: user


# ============================================================================
# Fake async session (returns seeded rows for the queried entity)
# ============================================================================

class _Result:
    def __init__(self, rows):
        self._rows = list(rows)

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, hazards=(), cans=()):
        self.hazards = list(hazards)
        self.cans = list(cans)

    def _rows_for(self, stmt):
        desc = getattr(stmt, "column_descriptions", None) or []
        entity = desc[0].get("entity") if desc else None
        if entity is Hazard:
            return self.hazards
        if entity is Can:
            return self.cans
        return []

    async def execute(self, stmt):
        return _Result(self._rows_for(stmt))

    async def scalars(self, stmt):
        return _Result(self._rows_for(stmt))


class _Ctx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


def _install_session(monkeypatch, hazards=(), cans=()):
    sess = _Session(hazards=hazards, cans=cans)
    monkeypatch.setattr(hazard_service_mod, "session_scope", lambda: _Ctx(sess))
    monkeypatch.setattr(can_cap_service_mod, "session_scope", lambda: _Ctx(sess))
    return sess


# ============================================================================
# Seed builders (ORM instances, never flushed)
# ============================================================================

def _hazard(tenant, department, ref, title=None):
    return Hazard(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(register_tenant(tenant)),
        hazard_id=ref,
        title=title or f"Hazard {ref}",
        description="seeded hazard for matrix verification",
        source="VSR",
        taxonomy="Organizational",
        priority="M",
        status="Open",
        department=department,
        is_demo=False,
        created_at=datetime.now(timezone.utc),
    )


def _can(tenant, department, hazard, ref, status="Open"):
    return Can(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(register_tenant(tenant)),
        hazard_id=hazard.id,
        can_reference=ref,
        title=f"CAN {ref}",
        description="seeded CAN for matrix verification",
        required_action="corrective action",
        issued_by="safety@example.com",
        issued_by_uid="uid-safety",
        assigned_to="owner@example.com",
        assigned_to_uid="uid-owner",
        department=department,
        priority="High",
        status=status,
        is_demo=False,
        created_at=datetime.now(timezone.utc),
    )


def _report_row(report_type):
    now = datetime.now(timezone.utc)
    return {
        "id": str(uuid.uuid4()),
        "tenant_id": TENANT,
        "report_type": report_type,
        "status": "NEW",
        "ai_status": "PENDING",
        "location": "KTM",
        "occurrence_date": now,
        "created_by": None if report_type == "voluntary" else "u1",
        "created_at": now,
        "is_anonymous": report_type == "voluntary",
    }


@pytest.fixture
def client():
    return TestClient(app)


# ============================================================================
# DEPT_ADMIN — own department only
# ============================================================================

def test_dept_admin_sees_only_own_department_hazards(client, monkeypatch):
    _install_session(
        monkeypatch,
        hazards=[
            _hazard(TENANT, "flight_ops", "H-OPS"),
            _hazard(TENANT, "maintenance_145", "H-MNT"),
        ],
    )
    _override(_user("DEPT_ADMIN", department="flight_ops"))
    r = client.get("/api/v1/hazards/")
    assert r.status_code == 200, r.text
    refs = {h["hazard_id"] for h in r.json()}
    assert refs == {"H-OPS"}, f"DEPT_ADMIN saw hazards outside its department: {refs}"


def test_dept_admin_sees_only_own_department_cans(client, monkeypatch):
    hazard = _hazard(TENANT, "flight_ops", "H-OPS")
    _install_session(
        monkeypatch,
        hazards=[hazard],
        cans=[
            _can(TENANT, "flight_ops", hazard, "CAN-OPS"),
            _can(TENANT, "maintenance_145", hazard, "CAN-MNT", status="Escalated"),
        ],
    )
    _override(_user("DEPT_ADMIN", department="flight_ops"))
    r = client.get("/api/v1/cans/")
    assert r.status_code == 200, r.text
    refs = {c["can_reference"] for c in r.json()}
    assert refs == {"CAN-OPS"}, f"DEPT_ADMIN saw CANs outside its department: {refs}"


def test_dept_admin_cannot_see_raw_vsrs(client, monkeypatch):
    monkeypatch.setattr(
        ReportService, "get_reports", lambda self, user: [_report_row("voluntary")]
    )
    _override(_user("DEPT_ADMIN", department="flight_ops"))
    r = client.get("/api/v1/reports/")
    assert r.status_code in (200, 403), r.text
    if r.status_code == 200:
        assert r.json() == [], f"DEPT_ADMIN received raw VSRs: {r.text}"


# ============================================================================
# ACCOUNTABLE_EXECUTIVE — aggregates + escalated CAP queue only
# ============================================================================

def test_ae_denied_raw_cans_and_sees_escalated_cap_queue(client, monkeypatch):
    _override(_user("ACCOUNTABLE_EXECUTIVE", department="safety"))

    # Raw CAN list is denied for the AE.
    r = client.get("/api/v1/cans/")
    assert r.status_code == 403, r.text

    # The escalated CAP queue remains available, and only that surface.
    captured = {}

    def fake_list_all_caps(self, user, filters):
        captured.update(filters or {})
        return [{"id": "cap1", "status": "In Progress", "escalated_to_ae": True}]

    monkeypatch.setattr(CanCapService, "list_all_caps", fake_list_all_caps)
    q = client.get("/api/v1/cans/caps?escalated_to_ae=true")
    assert q.status_code == 200, q.text
    assert captured.get("escalated_to_ae") is True
    assert q.json()[0]["escalated_to_ae"] is True

    # Without the escalation flag the AE is denied.
    q2 = client.get("/api/v1/cans/caps")
    assert q2.status_code == 403, q2.text


def test_ae_sees_aggregates_only(client, monkeypatch):
    monkeypatch.setattr(
        ReportService, "get_reports", lambda self, user: [_report_row("mandatory")]
    )
    _override(_user("ACCOUNTABLE_EXECUTIVE", department="safety"))
    r = client.get("/api/v1/reports/")
    assert r.status_code in (200, 403), r.text
    if r.status_code == 200:
        assert r.json() == [], f"AE received raw reports: {r.text}"

    from app.services import sram_service
    from app.services.ae_kpi_service import AEKPIService

    monkeypatch.setattr(
        AEKPIService,
        "compute_hazard_response_time",
        lambda self, tenant_id: {
            "avg_days": 2.0,
            "received_count": 1,
            "hazards_total": 3,
            "received_rate": 0.33,
        },
    )
    monkeypatch.setattr(CanCapService, "list_all_caps", lambda self, user, filters=None: [])

    async def _empty_register(_tid):
        return {"rows": []}

    monkeypatch.setattr(sram_service, "get_risk_register", _empty_register)

    k = client.get("/api/v1/dashboard/ae/kpis")
    assert k.status_code == 200, k.text
    assert k.json()["status"] == "success"


# ============================================================================
# STATE_SMD — state-wide aggregates only
#
# NOTE: the fake session does not execute Postgres RLS. These three tests
# therefore assert the *application-layer* posture. The effective DB result is
# additionally governed by p_hazards_tenant_isolation / p_cans_tenant_isolation
# / p_reports_tenant_isolation in
# supabase/migrations/20261013120000_rls_policies_guc.sql.
# ============================================================================

def test_state_smd_sees_cross_tenant_aggregates(client, monkeypatch):
    from app.services.dashboard_service import DashboardService

    monkeypatch.setattr(
        DashboardService,
        "get_caan_overview",
        lambda self, days=90: {
            "tenants": [TENANT, OTHER_TENANT],
            "tenant_count": 2,
            "total_reports": 12,
        },
    )
    _override(_user("STATE_SMD", tenant_id=None))
    r = client.get("/api/v1/dashboard/caan/overview")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["tenant_count"] == 2
    assert set(data["tenants"]) == {TENANT, OTHER_TENANT}


def test_state_smd_cannot_see_raw_hazards(client, monkeypatch):
    _install_session(
        monkeypatch,
        hazards=[
            _hazard(TENANT, "flight_ops", "H-1"),
            _hazard(OTHER_TENANT, "flight_ops", "H-2"),
        ],
    )
    _override(_user("STATE_SMD", tenant_id=None))
    r = client.get("/api/v1/hazards/")
    assert r.status_code in (200, 403), r.text
    if r.status_code == 200:
        assert r.json() == [], f"STATE_SMD received raw hazards: {r.text}"


def test_state_smd_cannot_see_raw_cans(client, monkeypatch):
    hazard = _hazard(TENANT, "flight_ops", "H-1")
    other = _hazard(OTHER_TENANT, "flight_ops", "H-2")
    _install_session(
        monkeypatch,
        hazards=[hazard, other],
        cans=[
            _can(TENANT, "flight_ops", hazard, "CAN-1"),
            _can(OTHER_TENANT, "flight_ops", other, "CAN-2"),
        ],
    )
    _override(_user("STATE_SMD", tenant_id=None))
    r = client.get("/api/v1/cans/")
    assert r.status_code in (200, 403), r.text
    if r.status_code == 200:
        assert r.json() == [], f"STATE_SMD received raw CANs: {r.text}"


def test_state_smd_cannot_see_raw_reports(client, monkeypatch):
    # The cross-tenant service path deliberately returns MORs (only VSRs are
    # excluded). The matrix says STATE_SMD must receive neither raw MORs nor
    # raw VSRs, so the route must not expose this list.
    monkeypatch.setattr(
        ReportService, "get_reports", lambda self, user: [_report_row("mandatory")]
    )
    _override(_user("STATE_SMD", tenant_id=None))
    r = client.get("/api/v1/reports/")
    assert r.status_code in (200, 403), r.text
    if r.status_code == 200:
        assert r.json() == [], f"STATE_SMD received raw MORs: {r.text}"


# ============================================================================
# Positive controls — TENANT_ADMIN keeps full tenant access
# ============================================================================

def test_tenant_admin_sees_all_tenant_hazards(client, monkeypatch):
    _install_session(
        monkeypatch,
        hazards=[
            _hazard(TENANT, "flight_ops", "H-OPS"),
            _hazard(TENANT, "maintenance_145", "H-MNT"),
        ],
    )
    _override(_user("TENANT_ADMIN", department="safety"))
    r = client.get("/api/v1/hazards/")
    assert r.status_code == 200, r.text
    refs = {h["hazard_id"] for h in r.json()}
    assert refs == {"H-OPS", "H-MNT"}
