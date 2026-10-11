# ============================================================================
# 2A.4 — auth boundary reads from memberships (regression tests).
#
# Hermetic: the pg bridge reads are monkeypatched and the actor-uuid resolver is
# stubbed. These tests exercise the real resolve_user_context / ensure_membership
# logic (the boundary itself), so they do NOT use the get_current_user override.
# ============================================================================

import uuid

from app.db.db_models import Membership, Tenant, UserProfile
from app.middleware import auth as auth_mod
from app.services import users as users_mod


def _install(monkeypatch, *, users_rows, memberships, tenants, actor_uuid):
    def fake_fetch_by(model, col, value):
        if model is UserProfile and col in ("email", "uid"):
            return next(
                (u for u in users_rows if u.get(col) == value), None
            )
        return None

    def fake_fetch_all(model, *, where=None, order_by=None, limit=None):
        if model is Membership:
            return [dict(m) for m in memberships
                    if m.get("is_active") and m.get("effective_to") is None]
        if model is Tenant:
            return [dict(t) for t in tenants]
        return []

    monkeypatch.setattr(auth_mod.pg, "fetch_by", fake_fetch_by)
    monkeypatch.setattr(auth_mod.pg, "fetch_all", fake_fetch_all)

    import app.services.actor as actor

    async def _fake_actor(user):
        return actor_uuid

    monkeypatch.setattr(actor, "resolve_actor_uuid", _fake_actor)


def test_resolve_reads_role_and_tenant_from_membership(monkeypatch):
    _install(
        monkeypatch,
        users_rows=[{"uid": "u1", "email": "a@x.com", "id": "uid1"}],
        memberships=[{"role": "TENANT_ADMIN", "tenant_id": "tid-1", "is_active": True,
                      "effective_to": None,
                      "effective_from": "2026-01-01T00:00:00+00:00", "id": "m1"}],
        tenants=[{"slug": "sita-air", "id": "sita-air"}],
        actor_uuid=uuid.uuid4(),
    )
    ctx = auth_mod.resolve_user_context("a@x.com", "USER", None)
    assert ctx["role"] == "TENANT_ADMIN"
    assert ctx["tenant_id"] == "sita-air"


def test_resolve_missing_membership_is_none_and_warns(monkeypatch):
    warnings = []
    monkeypatch.setattr(auth_mod.logger, "warning",
                        lambda *a, **k: warnings.append(a))
    _install(
        monkeypatch,
        users_rows=[{"uid": "u1", "email": "a@x.com", "id": "uid1"}],
        memberships=[], tenants=[], actor_uuid=uuid.uuid4(),
    )
    ctx = auth_mod.resolve_user_context("a@x.com", "USER", None)
    assert ctx == {"role": None, "tenant_id": None}
    assert warnings, "a warning must be logged for a missing membership"


def test_resolve_state_smd_has_role_and_tenant(monkeypatch):
    _install(
        monkeypatch,
        users_rows=[{"uid": "s1", "email": "smd@x.gov", "id": "sid"}],
        memberships=[{"role": "STATE_SMD", "tenant_id": "caan-uuid", "is_active": True,
                      "effective_to": None,
                      "effective_from": "2026-01-01T00:00:00+00:00", "id": "m2"}],
        tenants=[{"slug": "caan", "id": "caan"}],
        actor_uuid=uuid.uuid4(),
    )
    ctx = auth_mod.resolve_user_context("smd@x.gov", "CAAN_SMD", None)
    assert ctx["role"] == "STATE_SMD"
    assert ctx["tenant_id"] == "caan"


def test_resolve_super_admin_tenant_null(monkeypatch):
    _install(
        monkeypatch,
        users_rows=[{"uid": "sa", "email": "sa@x.com", "id": "said"}],
        memberships=[{"role": "SUPER_ADMIN", "tenant_id": None, "is_active": True,
                      "effective_to": None,
                      "effective_from": "2026-01-01T00:00:00+00:00", "id": "m3"}],
        tenants=[], actor_uuid=uuid.uuid4(),
    )
    ctx = auth_mod.resolve_user_context("sa@x.com", "SUPER_ADMIN", None)
    assert ctx["role"] == "SUPER_ADMIN"
    assert ctx["tenant_id"] is None


def test_ensure_membership_writes(monkeypatch):
    written = {}

    def fake_fetch_by(model, col, value):
        if model is UserProfile and col == "uid":
            return {"uid": "u1", "id": "uid1"}
        return None

    def fake_upsert(model, key_column, key_value, doc):
        written["model"] = model
        written["doc"] = doc

    monkeypatch.setattr(users_mod.pg, "fetch_by", fake_fetch_by)
    monkeypatch.setattr(users_mod.pg, "upsert", fake_upsert)
    users_mod.ensure_membership("u1", "sita-air", "TENANT_ADMIN")

    assert written["model"] is Membership
    assert written["doc"]["role"] == "TENANT_ADMIN"
    assert written["doc"]["is_active"] is True
    assert written["doc"]["effective_to"] is None
    assert written["doc"]["user_id"] == "uid1"


def test_upsert_user_doc_writes_membership_on_creation(monkeypatch):
    calls = {"n": 0}

    def fake_fetch_by(model, col, value):
        calls["n"] += 1
        # 1st call: _existed (None = new user); later calls: the row.
        if calls["n"] == 1:
            return None
        return {"uid": "u1", "id": "uid1"}

    upserts = []

    def fake_upsert(model, key_column, key_value, doc):
        upserts.append(model)

    monkeypatch.setattr(users_mod.pg, "fetch_by", fake_fetch_by)
    monkeypatch.setattr(users_mod.pg, "upsert", fake_upsert)
    users_mod.upsert_user_doc(uid="u1", email="a@x.com", role="TENANT_ADMIN",
                              tenant_id="sita-air")

    assert UserProfile in upserts
    assert Membership in upserts
