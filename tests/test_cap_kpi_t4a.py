import sys
from pathlib import Path

# Ensure backend app is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.metrics_service import MetricsService


class DummyDashboardService:
    def get_action_completion(self):
        return {
            "overdue": 2,
            "due_within_30_days": 3,
            "on_track": 5,
            "pending_review": 1,
            "closed": 7,
            "no_due_date": 0,
            "total": 18,
            "as_of_date": "2026-01-01",
            "generated_at": "2026-01-01T00:00:00+00:00",
        }


def test_cap_kpi_open_closed_from_dashboard_service():
    reports = [{"id": 1}]
    svc = DummyDashboardService()
    result = MetricsService.calculate_org_kpis(reports, dashboard_service=svc)
    # corrective_actions_open = overdue + due_within_30_days + on_track + pending_review
    assert result["corrective_actions_open"] == 2 + 3 + 5 + 1
    # corrective_actions_closed = closed
    assert result["corrective_actions_closed"] == 7


def test_cap_kpi_fallback_reads_absent_field():
    """The no-dashboard-service fallback reads r['corrective_actions'], which does
    not exist on Report. It must return 0/0 — documenting the deprecated path so
    a future change cannot silently alter it.
    """
    reports = [{"id": 1}, {"id": 2}, {"id": 3}]
    result = MetricsService.calculate_org_kpis(reports)  # no dashboard_service
    assert result["corrective_actions_open"] == 0
    assert result["corrective_actions_closed"] == 0
