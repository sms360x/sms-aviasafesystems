import pytest
from app.db.isolation import demo_scope
from app.services import demo_fallback as df


def test_production_scope_disables_fallback(monkeypatch):
    monkeypatch.setattr("app.services.demo_fallback.demo_scope", lambda: False)
    monkeypatch.setattr(df, "_enabled", lambda: True)
    monkeypatch.setattr(df, "demo_tenant_slug", lambda: "sita-air")
    monkeypatch.setattr(df, "tenant_has_reports", lambda slug: False)
    assert df.fallback_tenant_for("empty-tenant") is None


def test_demo_scope_allows_fallback(monkeypatch):
    monkeypatch.setattr("app.services.demo_fallback.demo_scope", lambda: True)
    monkeypatch.setattr(df, "_enabled", lambda: True)
    monkeypatch.setattr(df, "demo_tenant_slug", lambda: "sita-air")
    monkeypatch.setattr(df, "tenant_has_reports", lambda slug: False)
    assert df.fallback_tenant_for("empty-tenant") == "sita-air"


def test_disabled_fallback(monkeypatch):
    monkeypatch.setattr("app.services.demo_fallback.demo_scope", lambda: True)
    monkeypatch.setattr(df, "_enabled", lambda: False)
    monkeypatch.setattr(df, "demo_tenant_slug", lambda: "sita-air")
    assert df.fallback_tenant_for("empty-tenant") is None


def test_existing_reports_disable_fallback(monkeypatch):
    monkeypatch.setattr("app.services.demo_fallback.demo_scope", lambda: True)
    monkeypatch.setattr(df, "_enabled", lambda: True)
    monkeypatch.setattr(df, "demo_tenant_slug", lambda: "sita-air")
    monkeypatch.setattr(df, "tenant_has_reports", lambda slug: True)
    assert df.fallback_tenant_for("tenant-with-reports") is None
