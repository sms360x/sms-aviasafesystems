# ============================================================================
# 1C.3 — minimum-viable predictive analysis (predictive_service).
#
# Deterministic / no live DB: `pg.fetch_all` is monkeypatched with a fake that
# honours the tenant filter built into the query, so the service's tenant
# scoping is genuinely exercised.
# ============================================================================

from datetime import datetime, timezone

import pytest
from sqlalchemy.dialects import postgresql

from app.db import pg
from app.db.ids import tenant_uuid
from app.services.predictive_service import PredictiveService, _project_counts

_AIR1 = tenant_uuid("air1")
_AIR2 = tenant_uuid("air2")

_DATA = {
    "air1": [
        {"created_at": datetime(2026, 4, 10, tzinfo=timezone.utc), "status": "Open"},
        {"created_at": datetime(2026, 4, 20, tzinfo=timezone.utc), "status": "Closed"},
        {"created_at": datetime(2026, 5, 5, tzinfo=timezone.utc), "status": "Processing"},
        {"created_at": datetime(2026, 6, 1, tzinfo=timezone.utc), "status": "Open"},
        {"created_at": datetime(2026, 6, 20, tzinfo=timezone.utc), "status": "Reopened"},
    ],
    "air2": [],
}
_TID = {"air1": _AIR1, "air2": _AIR2}

_AS_OF = datetime(2026, 6, 15, tzinfo=timezone.utc)


def _sql(where) -> str:
    try:
        return " ".join(
            str(w.compile(dialect=postgresql.dialect(),
                          compile_kwargs={"literal_binds": True}))
            for w in where
        ).lower()
    except Exception:
        return " ".join(str(w) for w in where).lower()


def _install_fake_fetch(monkeypatch):
    def fake_fetch_all(model, *, where=None, order_by=None, limit=None):
        sql = _sql(where) if where else ""
        for slug, tid in _TID.items():
            if str(tid) in sql:
                return [dict(r) for r in _DATA[slug]]
        return []

    monkeypatch.setattr(pg, "fetch_all", fake_fetch_all)


# -- pure projection ---------------------------------------------------------

def test_project_counts_fixed_input():
    out = _project_counts([1, 1, 2], 1)
    assert out["method"] == "linear_trend"
    assert out["projected"] == [2]


def test_project_counts_linear_series():
    assert _project_counts([2, 4, 6], 1)["projected"] == [8]


def test_project_counts_empty_is_no_data():
    out = _project_counts([], 1)
    assert out["method"] == "no_data"
    assert out["projected"] == [None]


def test_project_counts_single_is_constant():
    out = _project_counts([5], 2)
    assert out["method"] == "constant"
    assert out["projected"] == [5, 5]


def test_project_counts_rejects_bad_periods_ahead():
    with pytest.raises(ValueError):
        _project_counts([1, 2], 0)


# -- service -----------------------------------------------------------------

def test_project_open_hazards_fixed_window(monkeypatch):
    _install_fake_fetch(monkeypatch)
    out = PredictiveService("air1").project_open_hazards(
        periods_back=3, periods_ahead=1, as_of=_AS_OF)

    assert out["register"] == "hazards"
    assert out["measure"] == "open_hazards"
    assert out["period"] == "month"
    assert out["method"] == "linear_trend"
    assert out["source_periods"] == [
        {"period": "2026-04", "count": 1},
        {"period": "2026-05", "count": 1},
        {"period": "2026-06", "count": 2},
    ]
    assert out["projected_open_count"] == 2
    assert out["projected"] == [{"period": "2026-07", "count": 2}]


def test_output_shape(monkeypatch):
    _install_fake_fetch(monkeypatch)
    out = PredictiveService("air1").project_open_hazards(as_of=_AS_OF)
    assert set(out) == {
        "tenant_id", "register", "measure", "period", "method",
        "periods_back", "periods_ahead", "source_periods",
        "projected_open_count", "projected", "limitations", "stronger_method",
    }
    assert out["tenant_id"] == "air1"
    assert isinstance(out["source_periods"], list)
    assert out["limitations"] and out["stronger_method"]


def test_zero_data_defaults_to_zero(monkeypatch):
    _install_fake_fetch(monkeypatch)
    out = PredictiveService("air1").project_open_hazards(
        periods_back=3, periods_ahead=2,
        as_of=datetime(2027, 1, 15, tzinfo=timezone.utc))
    assert all(p["count"] == 0 for p in out["source_periods"])
    assert out["projected_open_count"] == 0
    assert out["projected"] == [
        {"period": "2027-02", "count": 0},
        {"period": "2027-03", "count": 0},
    ]


def test_tenant_isolation(monkeypatch):
    _install_fake_fetch(monkeypatch)
    a = PredictiveService("air1").project_open_hazards(periods_back=3, as_of=_AS_OF)
    b = PredictiveService("air2").project_open_hazards(periods_back=3, as_of=_AS_OF)

    assert [p["count"] for p in a["source_periods"]] == [1, 1, 2]
    # air2 has no data and must not see air1's rows.
    assert [p["count"] for p in b["source_periods"]] == [0, 0, 0]
    assert b["projected_open_count"] == 0


def test_rejects_bad_windows(monkeypatch):
    _install_fake_fetch(monkeypatch)
    svc = PredictiveService("air1")
    with pytest.raises(ValueError):
        svc.project_open_hazards(periods_back=0)
    with pytest.raises(ValueError):
        svc.project_open_hazards(periods_ahead=0)
