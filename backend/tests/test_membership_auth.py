# ============================================================================
# 2A.5 — auth boundary reads the users row; memberships is the reporting
# substrate.
#
# SME ruling (2026-10-12): one user = one tenant = one role (ICAO
# accountability). The auth boundary resolves role/tenant from the users row.
# The memberships table is retained as a Super-Admin-only reporting substrate,
# kept in sync by users.ensure_membership on creation and role change. No
# operational code reads it.
#
# Hermetic: the pg bridge reads are monkeypatched, so these tests exercise the
# real resolve_user_context / ensure_membership / upsert_user_doc logic without
# a database.
# ============================================================================

from app.db.db_models import Membership, Tenant, UserProfile
from app.middleware import auth as auth_mod
from app.services import users as users_mod


# ---------------------------------------------------------------------------
# The resolver reads role/tenant from the users row (NOT memberships)
# ---------------------------------------------------------------------------

def test_resolver_reads_role_and_tenant_from_users_row(monkeypatch):
    def fake_fetch_by(model, col, value):
        if model is UserProfile and col == "email":
            return {"uid": "u1", "email": "a@x.com", "id": "uid1",
                    "role": "TENANT_ADMIN", "tenant_id": "tid-1"}
        return None

    def fake_fetch_all(model, *, where=None, order_by=None, limit=None):
        if model is Membership:
            raise AssertionError("the auth boundary must not read memberships")
        if model is Tenant:
            return [{"slug": "sita-air", "id": "tid-1", "name": "Sita Air"}]
        return []

    monkeypatch.setattr(auth_mod.pg, "fetch_by", fake_fetch_by)
    monkeypatch.setattr(auth_mod.pg, "fetch_all", fake_fetch_all)

    ctx = auth_mod.resolve_user_context("a@x.com")
    assert ctx == {"role": "TENANT_ADMIN", "tenant_id": "sita-air"}


def test_resolver_platform_user_has_null_tenant(monkeypatch):
    def fake_fetch_by(model, col, value):
        if model is UserProfile and col == "email":
            return {"uid": "sa", "email": "sa@x.com", "id": "said",
                    "role": "SUPER_ADMIN", "tenant_id": None}
        return None

    monkeypatch.setattr(auth_mod.pg, "fetch_by", fake_fetch_by)

    ctx = auth_mod.resolve_user_context("sa@x.com")
    assert ctx == {"role": "SUPER_ADMIN", "tenant_id": None}


def test_resolver_missing_user_row_is_none_and_warns(monkeypatch):
    warnings = []
    monkeypatch.setattr(auth_mod.logger, "warning",
                        lambda *a, **k: warnings.append(a))
    monkeypatch.setattr(auth_mod.pg, "fetch_by", lambda model, col, value: None)
    monkeypatch.setattr(auth_mod.pg, "fetch_all", lambda *a, **k: [])

    ctx = auth_mod.resolve_user_context("nobody@x.com")
    assert ctx == {"role": None, "tenant_id": None}
    assert warnings, "a warning must be logged for a missing users row"


# ---------------------------------------------------------------------------
# Reference table — keep-alive tests for the reporting substrate
# ---------------------------------------------------------------------------

def test_memberships_one_active_per_user_index_exists():
    names = {i.name for i in Membership.__table__.indexes}
    assert "memberships_one_active_per_user" in names
    idx = next(i for i in Membership.__table__.indexes
               if i.name == "memberships_one_active_per_user")
    assert idx.unique is True


def test_ensure_membership_writes_one_active_row(monkeypatch):
    written = {}

    def fake_fetch_by(model, col, value):
        if model is UserProfile and col == "uid":
            return {"uid": "u1", "id": "uid1"}
        return None

    def fake_upsert(model, key_column, key_value, doc):
        written["model"] = model
        written["key"] = (key_column, key_value)
        written["doc"] = doc

    monkeypatch.setattr(users_mod.pg, "fetch_by", fake_fetch_by)
    monkeypatch.setattr(users_mod.pg, "upsert", fake_upsert)
    users_mod.ensure_membership("u1", "sita-air", "TENANT_ADMIN")

    assert written["model"] is Membership
    assert written["key"] == ("user_id", "uid1")
    assert written["doc"]["user_id"] == "uid1"
    assert written["doc"]["role"] == "TENANT_ADMIN"
    assert written["doc"]["is_active"] is True
    assert written["doc"]["effective_to"] is None


def test_upsert_user_doc_writes_exactly_one_membership(monkeypatch):
    mem_writes = []

    def fake_fetch_by(model, col, value):
        if model is UserProfile and col == "uid":
            return {"uid": "u1", "id": "uid1"}
        return None

    def fake_upsert(model, key_column, key_value, doc):
        if model is Membership:
            mem_writes.append(dict(doc))

    monkeypatch.setattr(users_mod.pg, "fetch_by", fake_fetch_by)
    monkeypatch.setattr(users_mod.pg, "upsert", fake_upsert)
    users_mod.upsert_user_doc(uid="u1", email="a@x.com", role="TENANT_ADMIN",
                              tenant_id="sita-air")

    assert len(mem_writes) == 1
    assert mem_writes[0]["user_id"] == "uid1"
    assert mem_writes[0]["role"] == "TENANT_ADMIN"


def test_upsert_user_doc_syncs_membership_on_role_change(monkeypatch):
    mem_writes = []

    def fake_fetch_by(model, col, value):
        if model is UserProfile and col == "uid":
            return {"uid": "u1", "id": "uid1"}
        return None

    def fake_upsert(model, key_column, key_value, doc):
        if model is Membership:
            mem_writes.append(dict(doc))

    monkeypatch.setattr(users_mod.pg, "fetch_by", fake_fetch_by)
    monkeypatch.setattr(users_mod.pg, "upsert", fake_upsert)

    users_mod.upsert_user_doc(uid="u1", email="a@x.com", role="OFFICER",
                              tenant_id="sita-air")
    users_mod.upsert_user_doc(uid="u1", email="a@x.com", role="TENANT_ADMIN",
                              tenant_id="sita-air")

    assert [m["role"] for m in mem_writes] == ["OFFICER", "TENANT_ADMIN"]
    assert all(m["user_id"] == "uid1" for m in mem_writes)
