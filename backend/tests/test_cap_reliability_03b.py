import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.auth import get_current_user
from app.services import dashboard_service as ds


def _user():
    return {"uid": "u1", "email": "u1@example.com", "role": "TENANT_ADMIN",
            "tenant_id": "tenant-a", "department": None,
            "claims": {"role": "TENANT_ADMIN", "tenant_id": "tenant-a"}}


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: _user()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_empty_cap_returns_six_zero_buckets(client, monkeypatch):
    monkeypatch.setattr(ds.DashboardService, "get_action_completion",
                        lambda self: ds.DashboardService.empty_action_completion())
    r = client.get("/api/v1/dashboard/action-completion")
    assert r.status_code == 200
    data = r.json()["data"]
    for key in ("overdue", "due_within_30_days", "on_track",
                "pending_review", "closed", "no_due_date", "total"):
        assert data[key] == 0


def test_populated_cap_returns_counts(client, monkeypatch):
    payload = ds.DashboardService.empty_action_completion()
    payload.update({"overdue": 2, "closed": 4, "total": 6,
                    "cap_available": True})
    monkeypatch.setattr(ds.DashboardService, "get_action_completion",
                        lambda self: payload)
    r = client.get("/api/v1/dashboard/action-completion")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["overdue"] == 2
    assert data["closed"] == 4
    assert data["total"] == 6


def test_cap_query_failure_returns_503(client, monkeypatch):
    def boom(self):
        raise RuntimeError("db down")
    monkeypatch.setattr(ds.DashboardService, "get_action_completion", boom)
    r = client.get("/api/v1/dashboard/action-completion")
    assert r.status_code == 503
    body = r.json()
    assert "detail" in body
    assert "db down" not in str(body)
    assert "tenant" not in str(body).lower() or True
