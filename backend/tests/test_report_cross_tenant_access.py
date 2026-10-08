# ============================================================================
# 1A.7 — VSR cross-tenant exposure guard.
#
# These tests exercise the report-service methods that back
# GET /api/v1/reports/ and GET /api/v1/reports/{report_id}. They are
# deterministic (no live DB): a fake async session is injected and, for the
# list path, the generated SQL is asserted to exclude VSR (voluntary) rows for
# cross-tenant callers.
# ============================================================================

import asyncio
import uuid

from sqlalchemy.dialects import postgresql

from app.services import report_service as rs
from app.services.report_service import ReportService


class _Row:
    def __init__(self, report_type=None, tenant_id=None):
        self.report_type = report_type
        self.tenant_id = tenant_id


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _FakeResult(self._rows)

    async def flush(self):
        return None


class _FakeCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


def _install_fake_session(monkeypatch, rows=None):
    sess = _FakeSession(rows or [])
    monkeypatch.setattr(rs, "session_scope", lambda: _FakeCtx(sess))
    return sess


def _sql(stmt) -> str:
    return str(
        stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    ).lower()


def _svc():
    return ReportService("sita-air")


# T1 — cross-tenant list excludes VSR (voluntary) rows.
def test_cross_tenant_list_excludes_vsr(monkeypatch):
    sess = _install_fake_session(monkeypatch)
    asyncio.run(rs._get_reports_async(_svc(), True, None))
    sql = _sql(sess.statements[0])
    assert "report_type" in sql
    assert "voluntary" in sql
    assert "!=" in sql or "not in" in sql


# T2 — cross-tenant detail of a VSR returns None (route then yields 404).
def test_cross_tenant_detail_vsr_returns_none(monkeypatch):
    _install_fake_session(monkeypatch, rows=[_Row(report_type="voluntary")])
    out = asyncio.run(
        rs._get_report_async(_svc(), None, uuid.uuid4(), cross_tenant=True)
    )
    assert out is None


# T5 — cross-tenant detail of a MOR still returns the report.
def test_cross_tenant_detail_mor_returns_report(monkeypatch):
    _install_fake_session(monkeypatch, rows=[_Row(report_type="mandatory")])
    monkeypatch.setattr(rs, "_report_to_dict", lambda row: {"report_type": row.report_type})
    out = asyncio.run(
        rs._get_report_async(_svc(), None, uuid.uuid4(), cross_tenant=True)
    )
    assert out == {"report_type": "mandatory"}


# T3 — same-tenant list still includes VSRs (filters by tenant, no VSR exclusion).
def test_same_tenant_list_keeps_vsr(monkeypatch):
    sess = _install_fake_session(monkeypatch)
    tid = uuid.uuid4()
    asyncio.run(rs._get_reports_async(_svc(), False, tid))
    sql = _sql(sess.statements[0])
    assert "tenant_id" in sql
    assert "voluntary" not in sql


# T4 — same-tenant detail of a VSR is returned (Safety Department access intact).
def test_same_tenant_detail_vsr_returns_report(monkeypatch):
    _install_fake_session(monkeypatch, rows=[_Row(report_type="voluntary")])
    monkeypatch.setattr(rs, "_report_to_dict", lambda row: {"report_type": row.report_type})
    out = asyncio.run(
        rs._get_report_async(_svc(), uuid.uuid4(), uuid.uuid4(), cross_tenant=False)
    )
    assert out == {"report_type": "voluntary"}


# T6 — Safety Department (same tenant) keeps full VSR access (explicit alias of T4).
def test_safety_department_same_tenant_can_read_vsr(monkeypatch):
    _install_fake_session(monkeypatch, rows=[_Row(report_type="voluntary")])
    monkeypatch.setattr(rs, "_report_to_dict", lambda row: {"report_type": row.report_type})
    out = asyncio.run(
        rs._get_report_async(_svc(), uuid.uuid4(), uuid.uuid4(), cross_tenant=False)
    )
    assert out is not None
    assert out["report_type"] == "voluntary"


# T7 — PUT risk-assessment (backing method) for a cross-tenant caller on a VSR
#      returns None (the route yields 404), and no write/response content occurs.
def test_cross_tenant_put_risk_assessment_vsr_returns_none(monkeypatch):
    _install_fake_session(
        monkeypatch, rows=[_Row(report_type="voluntary", tenant_id=uuid.uuid4())]
    )
    out = asyncio.run(
        rs._confirm_risk_assessment_async(
            _svc(), uuid.uuid4(), 3, 2,
            {"role": "STATE_SMD", "uid": "u1", "tenant_id": None}, "note",
        )
    )
    assert out is None


# T8 — same-tenant caller calling PUT risk-assessment on their own VSR is
#      unaffected (no regression).
def test_same_tenant_put_risk_assessment_vsr_returns_report(monkeypatch):
    _install_fake_session(
        monkeypatch, rows=[_Row(report_type="voluntary", tenant_id=uuid.uuid4())]
    )
    monkeypatch.setattr(rs, "_report_to_dict", lambda row: {"report_type": row.report_type})
    out = asyncio.run(
        rs._confirm_risk_assessment_async(
            _svc(), uuid.uuid4(), 3, 2,
            {"role": "TENANT_ADMIN", "uid": "u1", "tenant_id": "sita-air"}, "note",
        )
    )
    assert out == {"report_type": "voluntary"}
