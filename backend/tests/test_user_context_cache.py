# ============================================================================
# Spec #5 - auth user/tenant resolution cache.
#
# Hermetic: the pg bridge reads are monkeypatched, so these tests exercise the
# real resolve_user_context + user_context_cache logic without a database.
# ============================================================================

from app.db.db_models import Tenant, UserProfile
from app.middleware import auth as auth_mod
from app.middleware import user_context_cache as cache_mod


def _install(monkeypatch, user_row, tenant_rows):
    calls = {"users": 0, "tenants": 0}

    def fake_fetch_by(model, col, value):
        if model is UserProfile and col == "email":
            calls["users"] += 1
            return user_row
        return None

    def fake_fetch_all(model, *, where=None, order_by=None, limit=None):
        if model is Tenant:
            calls["tenants"] += 1
            return tenant_rows
        return []

    monkeypatch.setattr(auth_mod.pg, "fetch_by", fake_fetch_by)
    monkeypatch.setattr(auth_mod.pg, "fetch_all", fake_fetch_all)
    cache_mod.invalidate_all()
    return calls


_USER = {
    "uid": "u-cache-1",
    "email": "cached@x.com",
    "role": "TENANT_ADMIN",
    "tenant_id": "tid-1",
    "department": "safety",
}


def test_resolved_context_is_cached_and_skips_db(monkeypatch):
    calls = _install(monkeypatch, _USER, [{"slug": "sita-air", "id": "tid-1"}])

    first = auth_mod.resolve_user_context("cached@x.com")
    second = auth_mod.resolve_user_context("cached@x.com")

    assert first == second == {
        "role": "TENANT_ADMIN", "tenant_id": "sita-air", "department": "safety",
    }
    # One users lookup + one tenants lookup total, not one pair per call.
    assert calls == {"users": 1, "tenants": 1}


def test_cache_key_is_case_insensitive(monkeypatch):
    calls = _install(monkeypatch, _USER, [{"slug": "sita-air", "id": "tid-1"}])

    auth_mod.resolve_user_context("Cached@X.com")
    auth_mod.resolve_user_context("cached@x.com")

    assert calls == {"users": 1, "tenants": 1}


def test_invalidation_forces_a_db_reread(monkeypatch):
    calls = _install(monkeypatch, _USER, [{"slug": "sita-air", "id": "tid-1"}])

    auth_mod.resolve_user_context("cached@x.com")
    cache_mod.invalidate_cached_context("cached@x.com")
    auth_mod.resolve_user_context("cached@x.com")

    assert calls == {"users": 2, "tenants": 2}


def test_missing_user_is_not_negative_cached(monkeypatch):
    calls = _install(monkeypatch, None, [])

    assert auth_mod.resolve_user_context("ghost@x.com") == {"role": None, "tenant_id": None}
    assert auth_mod.resolve_user_context("ghost@x.com") == {"role": None, "tenant_id": None}

    # A freshly provisioned user must be visible immediately: no negative cache.
    assert calls["users"] == 2


def test_cached_dict_is_not_mutable_shared_state(monkeypatch):
    _install(monkeypatch, _USER, [{"slug": "sita-air", "id": "tid-1"}])

    first = auth_mod.resolve_user_context("cached@x.com")
    first["role"] = "SUPER_ADMIN"

    assert auth_mod.resolve_user_context("cached@x.com")["role"] == "TENANT_ADMIN"
