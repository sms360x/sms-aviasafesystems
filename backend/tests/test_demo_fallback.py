# ============================================================================
# Spec #6 - global demo-data fallback for empty tenants.
#
# Hermetic: the pg bridge read is monkeypatched with an in-memory store keyed
# by tenant slug, and the async report-list session is faked. These tests
# exercise the real repository / report-service wiring without a database.
#
# Contract under test:
#   Tenant A (0 reports)      -> demo data, marked demo_fallback=True
#   Tenant B (0 reports)      -> demo data, marked demo_fallback=True
#   Tenant C (1 report)       -> only its own row, no fallback marker
#   cross_tenant/system reads -> never fall back
#   the first real report     -> closes the fallback immediately
#   create_report             -> writes the AUTHENTICATED tenant, never demo
# ============================================================================

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from app.core.config import settings
from app.db import pg
from app.db.ids import tenant_uuid
from app.db.isolation import demo_scope
from app.services import demo_fallback
from app.services import report_service as rs
from app.services.report_service import ReportService
from app.services.repository import ReportFilter, ReportRepository

DEMO = "sita-air"
KNOWN_SLUGS = ("tenant-a", "tenant-b", "tenant-c", DEMO)


def _row(slug: str, report_id: str, days_ago: int = 1) -> dict:
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "id": report_id,
        "tenant_id": tenant_uuid(slug),
        "report_type": "mandatory",
        "status": "NEW",
        "severity": "Major",
        "occurrence_type": "Bird Strike",
        "created_at": ts,
        "occurrence_date": ts,
        "updated_at": ts,
    }


def _store() -> dict:
    return {
        DEMO: [_row(DEMO, "demo-1", 1), _row(DEMO, "demo-2", 2)],
        "tenant-c": [_row("tenant-c", "c-1", 1)],
    }


def _slug_from_where(where) -> str | None:
    """Recover the tenant slug from a `Report.tenant_id == <uuid>` predicate."""
    for cond in where or []:
        left = getattr(cond, "left", None)
        right = getattr(cond, "right", None)
        if getattr(left, "key", None) != "tenant_id":
            continue
        value = getattr(right, "value", None)
        for slug in KNOWN_SLUGS:
            if value is not None and str(value) == tenant_uuid(slug):
                return slug
    return None


def _install_pg(monkeypatch, store: dict) -> dict:
    """In-memory pg.fetch_all. Returns counters for assertion."""
    counts = {"reads": 0, "probes": 0}

    def fake_fetch_all(model, *, where=None, order_by=None, limit=None):
        counts["reads"] += 1
        if limit == 1:
            counts["probes"] += 1
        rows = list(store.get(_slug_from_where(where), []))
        return rows[:limit] if limit else rows

    monkeypatch.setattr(pg, "fetch_all", fake_fetch_all)
    return counts


@pytest.fixture(autouse=True)
def _fresh_fallback(monkeypatch):
    monkeypatch.setattr(settings, "GLOBAL_DEMO_TENANT_ID", DEMO)
    monkeypatch.setattr(settings, "GLOBAL_DEMO_FALLBACK_ENABLED", True)
    ReportRepository._cache.clear()
    demo_fallback.invalidate()
    yield
    demo_fallback.invalidate()
    ReportRepository._cache.clear()


# ---------------------------------------------------------------------------
# Repository (dashboard) reads
# ---------------------------------------------------------------------------
def test_empty_tenant_a_gets_demo_data(monkeypatch):
    _install_pg(monkeypatch, _store())

    rows = ReportRepository().get_all_in_range(ReportFilter(tenant_id="tenant-a"))

    assert [r["id"] for r in rows] == ["demo-1", "demo-2"]
    assert all(r["tenant_id"] == tenant_uuid(DEMO) for r in rows)
    assert all(r["demo_fallback"] is True for r in rows)


def test_empty_tenant_b_gets_demo_data(monkeypatch):
    _install_pg(monkeypatch, _store())

    rows = ReportRepository().get_all_in_range(ReportFilter(tenant_id="tenant-b"))

    assert [r["id"] for r in rows] == ["demo-1", "demo-2"]
    assert all(r["demo_fallback"] is True for r in rows)


def test_tenant_c_with_one_report_gets_only_its_row(monkeypatch):
    _install_pg(monkeypatch, _store())

    rows = ReportRepository().get_all_in_range(ReportFilter(tenant_id="tenant-c"))

    assert [r["id"] for r in rows] == ["c-1"]
    assert rows[0]["tenant_id"] == tenant_uuid("tenant-c")
    # Fallback marker is absent: the UI sees genuine tenant data.
    assert "demo_fallback" not in rows[0]


def test_demo_tenant_reads_its_own_rows(monkeypatch):
    _install_pg(monkeypatch, _store())

    rows = ReportRepository().get_all_in_range(ReportFilter(tenant_id=DEMO))

    assert [r["id"] for r in rows] == ["demo-1", "demo-2"]
    assert all("demo_fallback" not in r for r in rows)


def test_cross_tenant_reads_never_fall_back(monkeypatch):
    _install_pg(monkeypatch, _store())

    rows = ReportRepository().get_all_in_range(
        ReportFilter(tenant_id="tenant-a", cross_tenant=True)
    )

    assert rows == []


def test_kill_switch_disables_the_fallback(monkeypatch):
    monkeypatch.setattr(settings, "GLOBAL_DEMO_FALLBACK_ENABLED", False)
    _install_pg(monkeypatch, _store())

    rows = ReportRepository().get_all_in_range(ReportFilter(tenant_id="tenant-a"))

    assert rows == []


def test_empty_read_is_only_probed_once_per_ttl(monkeypatch):
    counts = _install_pg(monkeypatch, _store())
    repo = ReportRepository()

    repo.get_all_in_range(ReportFilter(tenant_id="tenant-a"))
    ReportRepository._cache.clear()
    repo.get_all_in_range(ReportFilter(tenant_id="tenant-a"))

    assert counts["probes"] == 1


# ---------------------------------------------------------------------------
# ReportService (Reports page) reads
# ---------------------------------------------------------------------------
class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _FakeResult(self._rows)


class _FakeCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


def _install_session(monkeypatch, rows):
    sess = _FakeSession(rows)
    monkeypatch.setattr(rs, "session_scope", lambda: _FakeCtx(sess))
    monkeypatch.setattr(rs, "_report_to_dict", lambda row: {"id": row.id})
    return sess


def _sql(stmt) -> str:
    return str(
        stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    ).lower()


def test_report_list_for_empty_tenant_reads_demo_tenant(monkeypatch):
    _install_pg(monkeypatch, _store())
    sess = _install_session(
        monkeypatch,
        [(SimpleNamespace(id="demo-1"), 2), (SimpleNamespace(id="demo-2"), 2)],
    )
    monkeypatch.setattr(rs, "run", lambda coro: asyncio.run(coro) if asyncio.iscoroutine(coro) else coro)

    out = ReportService("tenant-a").get_reports({"role": "TENANT_ADMIN"})

    assert [item["id"] for item in out["items"]] == ["demo-1", "demo-2"]
    assert out["total"] == 2
    assert out["demo_fallback"] is True
    assert tenant_uuid(DEMO) in _sql(sess.statements[0])
    assert tenant_uuid("tenant-a") not in _sql(sess.statements[0])


def test_report_list_for_tenant_with_report_has_no_fallback(monkeypatch):
    _install_pg(monkeypatch, _store())
    sess = _install_session(monkeypatch, [(SimpleNamespace(id="c-1"), 1)])
    monkeypatch.setattr(rs, "run", lambda coro: asyncio.run(coro) if asyncio.iscoroutine(coro) else coro)

    out = ReportService("tenant-c").get_reports({"role": "TENANT_ADMIN"})

    assert [item["id"] for item in out["items"]] == ["c-1"]
    assert "demo_fallback" not in out
    assert tenant_uuid("tenant-c") in _sql(sess.statements[0])


# ---------------------------------------------------------------------------
# Writes always target the authenticated tenant + close the fallback
# ---------------------------------------------------------------------------
def test_create_report_writes_own_tenant_and_closes_fallback(monkeypatch):
    store = _store()
    _install_pg(monkeypatch, store)
    captured = {}

    async def fake_create(_svc, values):
        captured.update(values)
        return SimpleNamespace(id="new-report")

    monkeypatch.setattr(rs, "_create_report_async", fake_create)
    monkeypatch.setattr(
        rs, "run", lambda coro: asyncio.run(coro) if asyncio.iscoroutine(coro) else coro
    )
    monkeypatch.setattr(rs, "_report_to_dict", lambda row: {"id": row.id})

    # 1. An empty tenant is currently in demo fallback.
    repo = ReportRepository()
    rows = repo.get_all_in_range(ReportFilter(tenant_id="tenant-a"))
    assert [r["id"] for r in rows] == ["demo-1", "demo-2"]

    # 2. The tenant files its first report. The write must use the real tenant
    #    (never the demo tenant), even though reads are falling back.
    ReportService("tenant-a").create_report(
        {"report_type": "mandatory"}, {"uid": "u1"}
    )
    assert captured["tenant_id"] == tenant_uuid("tenant-a")
    assert captured["tenant_id"] != tenant_uuid(DEMO)
    assert captured["is_demo"] == demo_scope()

    # 3. As soon as the row exists, the fallback is closed (cache invalidated).
    store["tenant-a"] = [_row("tenant-a", "a-1", 1)]
    rows = repo.get_all_in_range(ReportFilter(tenant_id="tenant-a"))
    assert [r["id"] for r in rows] == ["a-1"]
    assert rows[0]["tenant_id"] == tenant_uuid("tenant-a")
    assert "demo_fallback" not in rows[0]
