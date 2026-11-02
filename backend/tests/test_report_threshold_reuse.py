# ============================================================================
# Chunk 03A - Reports list must not resolve the risk matrix per row.
#
# The Reports list projection (`routes.occurrence_reports._to_list_item`)
# does not expose `tolerability_tier`. Before the correction the shared
# serializer resolved thresholds for every row, and the nested bridge-loop
# path opened a fresh session/connection for each lookup. These tests pin:
#
#   A3.1  20 list rows -> zero threshold lookups
#   A3.2  cross-tenant pages stay tenant-scoped and VSR-free, zero lookups
#   A3.3  the projected list envelope is byte-for-byte unchanged
#   A3.4  detail still resolves the correct tenant's (custom) matrix once
#   A3.5  list serialization opens exactly one session for any page size
#   A3.6  a simulated-slow lookup is never paid on the list path
#
# Hermetic: the async session is faked and `get_thresholds` is monkeypatched,
# so no database, Firestore or network call occurs.
# ============================================================================

import asyncio
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects import postgresql

from app.db.db_models import Report
from app.db.ids import register_tenant, tenant_uuid
from app.routes.occurrence_reports import _to_list_item
from app.services import report_service as rs
from app.services import risk_matrix as rm
from app.services.report_service import ReportService

DEFAULT = {"low_max": 5, "medium_max": 9, "high_max": 15}
CUSTOM = {"low_max": 3, "medium_max": 6, "high_max": 12}


# ---------------------------------------------------------------------------
# Fixtures / fakes
# ---------------------------------------------------------------------------
def _report_row(slug: str, risk_index: int = 9, **overrides) -> Report:
    """Build an unpersisted Report row with the fields the list reads."""
    tenant_id = uuid.UUID(register_tenant(slug))
    now = datetime.now(timezone.utc)
    values = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        report_type="mandatory",
        status="Open",
        ai_status="COMPLETED",
        narrative="Bird strike on approach",
        location="KTM",
        occurrence_date=now,
        is_anonymous=False,
        severity="High",
        severity_level=3,
        probability_level=3,
        risk_index=risk_index,
        risk_level="High",
        created_at=now,
        updated_at=now,
        is_demo=False,
    )
    values.update(overrides)
    return Report(**values)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def scalars(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar_one(self):
        return len(self._rows)


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _FakeResult(self._rows)

    async def flush(self):
        return None


class _CountingCtx:
    """Async context manager that records every session entered."""

    def __init__(self, session, counter):
        self._session = session
        self._counter = counter

    async def __aenter__(self):
        self._counter.append(self._session)
        return self._session

    async def __aexit__(self, *exc):
        return False


def _install_session(monkeypatch, rows):
    sess = _FakeSession(rows)
    entered = []
    monkeypatch.setattr(
        rs, "session_scope", lambda: _CountingCtx(sess, entered)
    )
    return sess, entered


def _install_thresholds(monkeypatch, thresholds=None, delay=0.0):
    calls = []
    value = DEFAULT if thresholds is None else thresholds

    def fake_get_thresholds(tenant_id):
        calls.append(tenant_id)
        if delay:
            time.sleep(delay)
        return dict(value)

    monkeypatch.setattr(rs, "get_thresholds", fake_get_thresholds)
    return calls


def _svc(slug: str = "tenant-a") -> ReportService:
    return ReportService(slug)


def _envelope(items, payload):
    """Mirror the GET /reports/ envelope in routes.occurrence_reports."""
    return {
        "status": "success",
        "data": [_to_list_item(item) for item in items],
        "meta": {
            "total": payload["total"],
            "page": payload["page"],
            "pages": payload["pages"],
            "page_size": payload["page_size"],
        },
    }


# ---------------------------------------------------------------------------
# A3.1 - no redundant lookup for a 20-row single-tenant page
# ---------------------------------------------------------------------------
def test_a3_1_list_of_20_rows_performs_zero_threshold_lookups(monkeypatch):
    rows = [
        (_report_row("tenant-a", risk_index=(i % 25) + 1), 20)
        for i in range(20)
    ]
    _install_session(monkeypatch, rows)
    calls = _install_thresholds(monkeypatch)

    out = asyncio.run(
        rs._get_reports_async(
            _svc(), False, uuid.UUID(tenant_uuid("tenant-a")), page_size=20
        )
    )

    assert len(out["items"]) == 20
    assert out["total"] == 20
    assert calls == []
    assert all("tolerability_tier" not in item for item in out["items"])


# ---------------------------------------------------------------------------
# A3.2 - cross-tenant page: correct tenants, no reuse, no VSR leak
# ---------------------------------------------------------------------------
def test_a3_2_cross_tenant_list_isolated_and_lookup_free(monkeypatch):
    slugs = ["tenant-a", "tenant-b", "tenant-c"]
    rows = [(_report_row(slug, risk_index=i + 1), 6)
            for i, slug in enumerate(slugs * 2)]
    sess, _ = _install_session(monkeypatch, rows)
    calls = _install_thresholds(monkeypatch, thresholds=CUSTOM)

    out = asyncio.run(rs._get_reports_async(_svc(), True, None))

    assert [item["tenant_id"] for item in out["items"]] == slugs * 2
    assert out["total"] == 6
    assert calls == []
    assert all("tolerability_tier" not in item for item in out["items"])

    sql = str(
        sess.statements[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    # Existing cross-tenant VSR rule is untouched by the optimization.
    assert "report_type" in sql
    assert "voluntary" in sql


# ---------------------------------------------------------------------------
# A3.3 - the projected list contract is unchanged
# ---------------------------------------------------------------------------
def test_a3_3_list_envelope_matches_unoptimized_projection(monkeypatch):
    rows = [
        (
            _report_row(
                "tenant-a", risk_index=index, occurrence_type="Bird Strike"
            ),
            total,
        )
        for index, total in ((9, 3), (16, 3), (4, 3))
    ]
    _install_session(monkeypatch, rows)
    # The "before" side of this comparison genuinely resolves thresholds.
    calls = _install_thresholds(monkeypatch)

    after_payload = asyncio.run(
        rs._get_reports_async(
            _svc(), False, uuid.UUID(tenant_uuid("tenant-a")), page_size=20
        )
    )

    # Reconstruct the pre-optimization item dicts (tier included), then apply
    # the real route projection exactly as production does.
    before_items = [rs._report_to_dict(row) for row, _ in rows]
    before = _envelope(before_items, after_payload)
    after = _envelope(after_payload["items"], after_payload)

    assert before == after
    assert [item["id"] for item in after["data"]] == [
        str(row.id) for row, _ in rows
    ]
    assert all("tolerability_tier" not in item for item in after["data"])
    # Only the explicit "before" reconstruction touched the matrix.
    assert calls == ["tenant-a"] * len(rows)


# ---------------------------------------------------------------------------
# A3.4 - detail (and default serializer callers) keep the correct tier
# ---------------------------------------------------------------------------
def test_a3_4_detail_keeps_custom_matrix_tolerability_tier(monkeypatch):
    row = _report_row("tenant-b", risk_index=9)
    _install_session(monkeypatch, [row])
    calls = _install_thresholds(monkeypatch, thresholds=CUSTOM)

    out = asyncio.run(
        rs._get_report_async(
            _svc("tenant-b"), uuid.UUID(tenant_uuid("tenant-b")), row.id
        )
    )

    assert out["tenant_id"] == "tenant-b"
    assert out["tolerability_tier"] == rm.get_tolerability_tier(9, CUSTOM)
    assert calls == ["tenant-b"]


def test_a3_4_default_serializer_still_includes_tier(monkeypatch):
    row = _report_row("tenant-c", risk_index=9)
    calls = _install_thresholds(monkeypatch, thresholds=CUSTOM)

    serialized = rs._report_to_dict(row)

    expected = rm.get_tolerability_tier(9, CUSTOM)
    assert serialized["tolerability_tier"] == expected
    assert calls == ["tenant-c"]


# ---------------------------------------------------------------------------
# A3.5 - connection/session count does not scale with page size
# ---------------------------------------------------------------------------
def test_a3_5_list_opens_one_session_regardless_of_row_count(monkeypatch):
    rows = [(_report_row("tenant-a"), 20) for _ in range(20)]
    _, entered = _install_session(monkeypatch, rows)
    calls = _install_thresholds(monkeypatch)

    asyncio.run(
        rs._get_reports_async(
            _svc(), False, uuid.UUID(tenant_uuid("tenant-a")), page_size=20
        )
    )

    assert len(entered) == 1
    assert calls == []


# ---------------------------------------------------------------------------
# A3.6 - simulated slow lookup is never paid on the list path
# ---------------------------------------------------------------------------
def test_a3_6_slow_threshold_lookup_does_not_affect_20_row_list(monkeypatch):
    rows = [(_report_row("tenant-a"), 20) for _ in range(20)]
    _install_session(monkeypatch, rows)
    # 3s per lookup: the pre-fix list path would spend ~60s on 20 rows.
    calls = _install_thresholds(monkeypatch, delay=3.0)

    started = time.monotonic()
    out = asyncio.run(
        rs._get_reports_async(
            _svc(), False, uuid.UUID(tenant_uuid("tenant-a")), page_size=20
        )
    )
    elapsed = time.monotonic() - started

    assert len(out["items"]) == 20
    assert calls == []
    assert elapsed < 5.0
