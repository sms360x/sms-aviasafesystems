"""TREND-02 deterministic trend date-range tests (read-only implementation)."""

from datetime import datetime, timezone

from app.services.dashboard_service import DashboardService


def test_pad_monthly_trends_fills_zero_months():
    trends = [
        {"month": "10", "year": 2026, "total": 5, "voluntary": 3,
         "mandatory": 2, "high_risk": 1, "prediction": None},
        {"month": "7", "year": 2026, "total": 2, "voluntary": 1,
         "mandatory": 1, "high_risk": 0, "prediction": None},
    ]
    out = DashboardService._pad_monthly_trends(
        trends,
        datetime(2026, 7, 5, tzinfo=timezone.utc),
        datetime(2026, 11, 2, tzinfo=timezone.utc),
    )
    assert [(r["year"], int(r["month"])) for r in out] == [
        (2026, 7), (2026, 8), (2026, 9), (2026, 10), (2026, 11),
    ]
    assert out[1]["total"] == 0
    assert out[2]["total"] == 0
    assert out[3]["total"] == 5
    assert out[4]["total"] == 0


def test_pad_monthly_trends_single_month():
    trends = []
    out = DashboardService._pad_monthly_trends(
        trends,
        datetime(2026, 10, 1, tzinfo=timezone.utc),
        datetime(2026, 10, 31, tzinfo=timezone.utc),
    )
    assert len(out) == 1
    assert (out[0]["year"], int(out[0]["month"])) == (2026, 10)
    assert out[0]["total"] == 0
