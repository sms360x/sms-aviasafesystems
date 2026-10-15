# ============================================================================
# 3C.2B (F-P1-6) — sensitive admin export authorization + audit regression.
#
# Fully isolated: export queries are blocked by sentinel, audit log and
# settings are monkeypatched, auth uses dependency overrides. No database,
# Firebase, or network contact occurs.
# ============================================================================

import pytest
from fastapi.testclient import TestClient

from app.middleware.auth import get_current_user
import app.routes.admin as admin_routes
import app.services.admin_data_service as ads

KEY = "test-setup-key"


def _boom(*args, **kwargs):
    raise AssertionError("export query must not run on this path")


@pytest.fixture
def ctx(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.SETUP_SECRET", KEY, raising=False)
    audits = []
    monkeypatch.setattr(admin_routes, "log_audit", lambda **kw: audits.append(kw))
    monkeypatch.setattr(ads, "export_all_tables_csv", _boom)
    monkeypatch.setattr(ads, "export_single_table_csv", _boom)
    from app.main import app

    app.dependency_overrides.clear()
    try:
        yield TestClient(app), audits
    finally:
        app.dependency_overrides.clear()


def _as_admin():
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: {
        "uid": "u-admin", "email": "admin@x.test",
        "role": "SUPER_ADMIN", "tenant_id": None,
    }


def _as_role(role):
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: {
        "uid": "u1", "email": "u@x.test",
        "role": role, "tenant_id": "t1",
    }


def _denials(audits):
    return [a for a in audits if a.get("action") == "EXPORT_DENIED"]


def _assert_no_secret(audits):
    assert KEY not in str(audits), "setup key must never appear in audit records"


# ---------------------------------------------------------------------------
# 1/2. Unauthenticated + non-admin rejected; queries never run
# ---------------------------------------------------------------------------

def test_unauthenticated_all_tables_rejected(ctx):
    client, audits = ctx
    r = client.get("/api/v1/admin/export/all-tables")
    assert r.status_code in (401, 403)


def test_unauthenticated_single_table_rejected(ctx):
    client, audits = ctx
    r = client.get("/api/v1/admin/export/table/hazards")
    assert r.status_code in (401, 403)


def test_non_admin_rejected_and_audited(ctx):
    client, audits = ctx
    _as_role("TENANT_ADMIN")
    r = client.get("/api/v1/admin/export/all-tables",
                   headers={"X-Setup-Key": KEY})
    assert r.status_code == 403
    denials = _denials(audits)
    assert len(denials) == 1 and denials[0]["metadata"]["reason"] == "role"
    _assert_no_secret(audits)


# ---------------------------------------------------------------------------
# 3/4. Setup-key gate (fail closed)
# ---------------------------------------------------------------------------

def test_admin_without_setup_key_rejected(ctx):
    client, audits = ctx
    _as_admin()
    r = client.get("/api/v1/admin/export/all-tables")
    assert r.status_code == 403
    denials = _denials(audits)
    assert len(denials) == 1 and denials[0]["metadata"]["reason"] == "setup-key"
    _assert_no_secret(audits)


def test_admin_wrong_setup_key_rejected(ctx):
    client, audits = ctx
    _as_admin()
    r = client.get("/api/v1/admin/export/table/hazards",
                   headers={"X-Setup-Key": "wrong"})
    assert r.status_code == 403
    assert len(_denials(audits)) == 1
    _assert_no_secret(audits)


def test_setup_secret_unset_fails_closed(ctx, monkeypatch):
    client, audits = ctx
    monkeypatch.setattr("app.core.config.settings.SETUP_SECRET", None, raising=False)
    _as_admin()
    r = client.get("/api/v1/admin/export/all-tables",
                   headers={"X-Setup-Key": KEY})
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# 5/7/8. Correct authorization permits only approved exports + audits
# ---------------------------------------------------------------------------

def test_admin_correct_key_all_tables(ctx, monkeypatch):
    client, audits = ctx
    _as_admin()

    async def _csv():
        return "a,b\n1,2\n", "all-tables.csv", 1

    monkeypatch.setattr(ads, "export_all_tables_csv", _csv)
    r = client.get("/api/v1/admin/export/all-tables",
                   headers={"X-Setup-Key": KEY})
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    successes = [a for a in audits if a.get("action") == "EXPORT_ALL_TABLES"]
    assert len(successes) == 1
    assert successes[0]["metadata"] == {"rows": 1}
    assert successes[0]["user"] == "admin@x.test"
    _assert_no_secret(audits)


def test_admin_correct_key_single_table(ctx, monkeypatch):
    client, audits = ctx
    _as_admin()

    async def _csv(name):
        return "a\n1\n", f"{name}.csv", 1

    monkeypatch.setattr(ads, "export_single_table_csv", _csv)
    r = client.get("/api/v1/admin/export/table/hazards",
                   headers={"X-Setup-Key": KEY})
    assert r.status_code == 200
    successes = [a for a in audits if a.get("action") == "EXPORT_TABLE"]
    assert len(successes) == 1 and successes[0]["target_id"] == "table/hazards"
    _assert_no_secret(audits)


def test_unknown_table_404_with_full_auth(ctx, monkeypatch):
    client, audits = ctx
    _as_admin()

    async def _missing(name):
        raise KeyError(f"unknown table: {name}")

    monkeypatch.setattr(ads, "export_single_table_csv", _missing)
    r = client.get("/api/v1/admin/export/table/nope",
                   headers={"X-Setup-Key": KEY})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 10. Unrelated legitimate exports keep working (no key required)
# ---------------------------------------------------------------------------

def test_demo_and_purge_exports_unchanged(ctx, monkeypatch):
    client, audits = ctx
    _as_admin()

    async def _demo(kind, tenant_id):
        return "a\n1\n", "demo.csv", 1

    async def _purge():
        return "t,n\nx,1\n", "purge.csv", 1

    monkeypatch.setattr(ads, "export_demo_data_csv", _demo)
    monkeypatch.setattr(ads, "export_purge_summary_csv", _purge)
    assert client.get("/api/v1/admin/export/dummy-data").status_code == 200
    assert client.get("/api/v1/admin/export/purge-data").status_code == 200
    assert _denials(audits) == []
