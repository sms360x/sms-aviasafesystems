# ============================================================================
# Phase 3A.2 — SUPER_ADMIN console (Audit Chain Viewer + System Configs).
#
# DB-backed: each test uses a throwaway tenant slug and cleans up. The durable
# trail is append-only (BEFORE UPDATE/DELETE trigger), so cleanup disables the
# trigger for the test tenant, deletes, and re-enables it.
#
# Covered:
#   * RBAC — every console endpoint denies TENANT_ADMIN / STATE_SMD / OFFICER
#     / DEPT_ADMIN / ACCOUNTABLE_EXECUTIVE / SAG_MEMBER (403) and serves
#     SUPER_ADMIN (200).
#   * Read-only — the audit router exposes no mutation verb at all, and the
#     append-only trigger on durable_audit_logs is still in force.
#   * Integrity — a freshly written chain verifies "valid"; a tampered row is
#     reported "broken" and is filterable.
#   * Config mutations are audited — every permitted-key change lands as a
#     SYSTEM_CONFIG_UPDATED event on the durable chain with the actor role.
#   * No PII leakage — the console never returns the raw actor id, an email
#     address or a phone number; the actor is a pseudonymous fingerprint.
# ============================================================================

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.db.ids import tenant_uuid
from app.db.rls import clear_current_identity, identity_from_user, set_current_identity
from app.db.session import session_scope
from app.main import app
from app.middleware.auth import get_current_user
from app.services.audit_service import log_audit

from _mbb import cleanup, create_tenant, unique_slug, run

TRIGGER = "durable_audit_no_mutate_trg"
SETUP_KEY = "unit-test-setup-key"

READ_ENDPOINTS = [
    "/api/v1/audit/events",
    "/api/v1/audit/tenants",
    "/api/v1/system-config/registry",
    "/api/v1/system-config/tenants",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _override(user):
    """Override auth and publish the RLS identity the real dependency sets."""

    async def _fake_current_user():
        clear_current_identity()
        set_current_identity(identity_from_user(user))
        return user

    app.dependency_overrides[get_current_user] = _fake_current_user


def _super():
    _override(
        {
            "uid": "u-super",
            "email": "super@console.test",
            "role": "SUPER_ADMIN",
            "tenant_id": None,
        }
    )


def _client() -> TestClient:
    return TestClient(app)


def _durable_rows(slug: str):
    tid = tenant_uuid(slug)

    async def _go():
        async with session_scope() as s:
            r = await s.execute(
                text(
                    "SELECT action, actor_uid, actor_role, resource_type, resource_id, "
                    "metadata, prev_hash, current_hash, id "
                    "FROM public.durable_audit_logs WHERE tenant_id = :t "
                    "ORDER BY timestamp, id"
                ),
                {"t": tid},
            )
            return r.fetchall()

    return run(_go())


def _tenant_modules(slug: str):
    async def _go():
        async with session_scope() as s:
            r = await s.execute(
                text("SELECT modules FROM public.tenants WHERE slug = :s"),
                {"s": slug},
            )
            row = r.fetchone()
            return (row[0] if row else None) or {}

    return run(_go())


def _purge_durable(slug: str):
    tid = tenant_uuid(slug)

    async def _go():
        async with session_scope() as s:
            await s.execute(
                text(f"ALTER TABLE public.durable_audit_logs DISABLE TRIGGER {TRIGGER}")
            )
            await s.execute(
                text("DELETE FROM public.durable_audit_logs WHERE tenant_id = :t"),
                {"t": tid},
            )
            await s.execute(
                text(f"ALTER TABLE public.durable_audit_logs ENABLE TRIGGER {TRIGGER}")
            )

    run(_go())


@pytest.fixture(autouse=True)
def _clean_identity():
    """No test may inherit an RLS identity from the previous one."""
    clear_current_identity()
    yield
    clear_current_identity()
    app.dependency_overrides.clear()


@pytest.fixture
def tenant():
    slug = unique_slug("sac")
    create_tenant(slug)
    try:
        yield slug
    finally:
        _purge_durable(slug)
        cleanup(slug, ("tenants",))


@pytest.fixture
def other_tenant():
    slug = unique_slug("sac-other")
    create_tenant(slug)
    try:
        yield slug
    finally:
        _purge_durable(slug)
        cleanup(slug, ("tenants",))


# ---------------------------------------------------------------------------
# 1. Access control — SUPER_ADMIN only
# ---------------------------------------------------------------------------


def test_console_reads_reject_every_other_role(tenant):
    denied_roles = [
        "TENANT_ADMIN",
        "STATE_SMD",
        "OFFICER",
        "DEPT_ADMIN",
        "ACCOUNTABLE_EXECUTIVE",
        "SAG_MEMBER",
        "USER",
    ]
    for role in denied_roles:
        _override(
            {
                "uid": "u-x",
                "email": "x@console.test",
                "role": role,
                "tenant_id": tenant,
            }
        )
        for endpoint in READ_ENDPOINTS:
            r = _client().get(endpoint)
            assert r.status_code == 403, (role, endpoint, r.status_code, r.text)
        # per-tenant config read is gated as well
        r = _client().get(f"/api/v1/system-config/{tenant}")
        assert r.status_code == 403, (role, r.status_code, r.text)


def test_console_reads_serve_super_admin(tenant):
    _super()
    for endpoint in READ_ENDPOINTS:
        r = _client().get(endpoint)
        assert r.status_code == 200, (endpoint, r.status_code, r.text)


def test_config_write_denied_to_non_super_admin(tenant, monkeypatch):
    monkeypatch.setattr(settings, "SETUP_SECRET", SETUP_KEY)
    _override(
        {
            "uid": "u-ta",
            "email": "ta@console.test",
            "role": "TENANT_ADMIN",
            "tenant_id": tenant,
        }
    )
    r = _client().put(
        f"/api/v1/system-config/{tenant}/keys/module_a_survey",
        json={"setup_key": SETUP_KEY, "value": True},
    )
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# 2. Read-only guarantees
# ---------------------------------------------------------------------------


def test_audit_router_exposes_no_mutation_verb():
    # The OpenAPI schema is the reliable source of paths + methods (a newer
    # FastAPI keeps included routers nested instead of flattening them into
    # `app.routes`).
    paths = app.openapi().get("paths", {})
    audit_paths = {p: ops for p, ops in paths.items() if p.startswith("/api/v1/audit")}
    assert audit_paths, "the audit router must expose at least one route"

    for path, ops in audit_paths.items():
        methods = {
            m.upper()
            for m in ops
            if m.upper() in {"get", "post", "put", "patch", "delete"}
        }
        assert methods <= {"GET"}, (path, methods)

    for verb in ("post", "put", "patch", "delete"):
        r = getattr(_client(), verb)("/api/v1/audit/events")
        assert r.status_code in (404, 405), (verb, r.status_code, r.text)


def test_durable_trail_is_still_append_only(tenant):
    log_audit(
        action="APPEND_ONLY",
        user="u",
        tenant_id=tenant,
        target_type="t",
        target_id="1",
    )

    async def _update():
        async with session_scope() as s:
            await s.execute(
                text(
                    "UPDATE public.durable_audit_logs SET action='TAMPER' "
                    "WHERE tenant_id = :t"
                ),
                {"t": tenant_uuid(tenant)},
            )

    with pytest.raises(Exception):
        run(_update())

    async def _delete():
        async with session_scope() as s:
            await s.execute(
                text("DELETE FROM public.durable_audit_logs WHERE tenant_id = :t"),
                {"t": tenant_uuid(tenant)},
            )

    with pytest.raises(Exception):
        run(_delete())


# ---------------------------------------------------------------------------
# 3. Audit chain viewer — listing, detail, integrity verdicts
# ---------------------------------------------------------------------------


def test_chain_listing_is_tenant_labelled_and_verified(tenant):
    for i in range(3):
        log_audit(
            action=f"CONSOLE_TEST_{i}",
            user="super@console.test",
            tenant_id=tenant,
            target_type="t",
            target_id=str(i),
            metadata={"n": i},
        )

    _super()
    r = _client().get(f"/api/v1/audit/events?tenant_id={tenant}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 3
    assert data["cross_tenant"] is False
    for event in data["events"]:
        assert event["tenant_slug"] == tenant
        assert event["tenant_label"] == tenant
        assert event["verification"] == "valid"
        assert event["prev_hash"]
        assert event["current_hash"]

    # the chain is linked: every row but the first points at its predecessor
    events = data["events"]
    links = {e["current_hash"]: e["prev_hash"] for e in events}
    assert any(p == "GENESIS" for p in links.values())


def test_event_detail_exposes_link_but_not_the_secret(tenant):
    log_audit(
        action="DETAIL_EVENT",
        user="super@console.test",
        tenant_id=tenant,
        target_type="t",
        target_id="1",
    )
    _super()
    listing = _client().get(f"/api/v1/audit/events?tenant_id={tenant}").json()
    event_id = listing["events"][0]["id"]

    r = _client().get(f"/api/v1/audit/events/{event_id}")
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["id"] == event_id
    assert detail["action"] == "DETAIL_EVENT"
    assert detail["verification"] == "valid"
    assert detail["chain"]["predecessor_id"] is None  # first link of the chain
    assert detail["chain"]["successor_count"] == 0

    # The HMAC key must never travel to the client.
    from app.services.audit_service import DEV_AUDIT_HMAC_KEY, hmac_key

    body = r.text
    assert hmac_key() not in body
    assert DEV_AUDIT_HMAC_KEY not in body


def test_unknown_event_returns_404():
    _super()
    r = _client().get("/api/v1/audit/events/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    # A malformed id is a 404 as well — never a 500 from the uuid cast.
    r = _client().get("/api/v1/audit/events/not-a-uuid")
    assert r.status_code == 404


def test_tampered_row_is_reported_broken(tenant):
    log_audit(
        action="TAMPER_TARGET",
        user="u",
        tenant_id=tenant,
        target_type="t",
        target_id="1",
        metadata={"v": 1},
    )
    log_audit(
        action="AFTER_TARGET",
        user="u",
        tenant_id=tenant,
        target_type="t",
        target_id="2",
        metadata={"v": 2},
    )

    rows = _durable_rows(tenant)
    target_id = rows[0].id

    async def _tamper():
        async with session_scope() as s:
            await s.execute(
                text(f"ALTER TABLE public.durable_audit_logs DISABLE TRIGGER {TRIGGER}")
            )
            await s.execute(
                text(
                    "UPDATE public.durable_audit_logs SET metadata = "
                    "'{\"v\": 999}'::jsonb WHERE id = :i"
                ),
                {"i": target_id},
            )
            await s.execute(
                text(f"ALTER TABLE public.durable_audit_logs ENABLE TRIGGER {TRIGGER}")
            )

    run(_tamper())

    _super()
    r = _client().get(f"/api/v1/audit/events?tenant_id={tenant}")
    assert r.status_code == 200, r.text
    verdicts = {e["action"]: e["verification"] for e in r.json()["events"]}
    assert verdicts["TAMPER_TARGET"] == "broken"

    # the verdict is filterable
    r = _client().get(f"/api/v1/audit/events?tenant_id={tenant}&verification=broken")
    assert r.json()["total"] == 1
    assert r.json()["events"][0]["action"] == "TAMPER_TARGET"

    r = _client().get(f"/api/v1/audit/events?tenant_id={tenant}&verification=valid")
    assert r.json()["total"] == 1
    assert r.json()["events"][0]["action"] == "AFTER_TARGET"


def test_tenant_chain_summary(tenant):
    for i in range(2):
        log_audit(
            action=f"SUMMARY_{i}",
            user="u",
            tenant_id=tenant,
            target_type="t",
            target_id=str(i),
        )
    _super()
    r = _client().get("/api/v1/audit/tenants")
    assert r.status_code == 200, r.text
    chains = r.json()["tenants"]
    entry = next(c for c in chains if c["tenant_slug"] == tenant)
    assert entry["events"] == 2
    assert entry["chain_segments"] == 1
    assert entry["forked_links"] == 0
    assert entry["dangling_links"] == 0
    assert entry["status"] == "valid"


def test_cross_tenant_read_is_explicitly_labelled(tenant, other_tenant):
    log_audit(action="A", user="u", tenant_id=tenant, target_type="t", target_id="a")
    log_audit(action="B", user="u", tenant_id=other_tenant, target_type="t", target_id="b")

    _super()
    r = _client().get("/api/v1/audit/events")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["cross_tenant"] is True
    labels = {e["tenant_slug"] for e in data["events"]}
    assert tenant in labels
    assert other_tenant in labels
    for event in data["events"]:
        assert event["tenant_label"], "every cross-tenant row carries a tenant label"


def test_filters_by_action_and_actor_role(tenant):
    log_audit(action="FILTER_A", user="u", tenant_id=tenant, target_type="t", target_id="1")
    set_current_identity(
        {
            "tenant_uuid": tenant_uuid(tenant),
            "tenant_slug": tenant,
            "role": "STATE_SMD",
            "department": "smd",
            "user_uid": "u-smd",
        }
    )
    log_audit(action="FILTER_B", user="u2", tenant_id=tenant, target_type="t", target_id="2")
    clear_current_identity()

    _super()
    r = _client().get(f"/api/v1/audit/events?tenant_id={tenant}&action=FILTER_B")
    assert r.json()["total"] == 1
    assert r.json()["events"][0]["action"] == "FILTER_B"

    r = _client().get(f"/api/v1/audit/events?tenant_id={tenant}&actor_role=STATE_SMD")
    assert r.json()["total"] == 1
    assert r.json()["events"][0]["actor_role"] == "STATE_SMD"


def test_invalid_date_filter_is_rejected():
    _super()
    r = _client().get("/api/v1/audit/events?date_from=not-a-date")
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# 4. No PII leakage
# ---------------------------------------------------------------------------


def test_console_response_carries_no_pii(tenant):
    log_audit(
        action="CONTACT_UPDATE",
        user="officer@secret-tenant.test",
        tenant_id=tenant,
        target_type="user",
        target_id="u1",
        metadata={
            "email": "reporter@secret-tenant.test",
            "note": "call the reporter on 9812345678",
        },
    )
    _super()
    r = _client().get(f"/api/v1/audit/events?tenant_id={tenant}")
    assert r.status_code == 200, r.text
    body = r.text
    assert "secret-tenant.test" not in body
    assert "9812345678" not in body

    event = r.json()["events"][0]
    assert "actor_uid" not in event
    assert event["actor_fingerprint"]
    assert event["payload"]["email"] == "[redacted]"
    assert "reporter@secret-tenant.test" not in str(event["payload"])

    detail = _client().get(f"/api/v1/audit/events/{event['id']}").json()
    assert "actor_uid" not in detail
    assert "secret-tenant.test" not in str(detail)


def test_actor_role_is_recorded_on_request_scoped_events(tenant):
    set_current_identity(
        {
            "tenant_uuid": tenant_uuid(tenant),
            "tenant_slug": tenant,
            "role": "TENANT_ADMIN",
            "department": "safety",
            "user_uid": "u-ta",
        }
    )
    log_audit(
        action="ROLE_CAPTURED",
        user="ta@console.test",
        tenant_id=tenant,
        target_type="t",
        target_id="1",
    )
    clear_current_identity()

    rows = _durable_rows(tenant)
    assert rows[0].action == "ROLE_CAPTURED"
    assert rows[0].actor_role == "TENANT_ADMIN"

    # An anonymous VSR event carries neither an actor nor a role.
    log_audit(
        action="VSR_SUBMITTED",
        user="anon@console.test",
        tenant_id=tenant,
        target_type="report",
        target_id="R-1",
        metadata={"reporter_email": "reporter@console.test"},
    )
    rows = _durable_rows(tenant)
    vsr = rows[-1]
    assert vsr.action == "VSR_SUBMITTED"
    assert vsr.actor_uid is None
    assert vsr.actor_role is None


# ---------------------------------------------------------------------------
# 5. System configs — registry, reads, audited writes
# ---------------------------------------------------------------------------


def test_config_registry_exposes_permitted_keys(tenant):
    _super()
    r = _client().get("/api/v1/system-config/registry")
    assert r.status_code == 200, r.text
    body = r.json()
    keys = {k["key"]: k for k in body["keys"]}
    for expected in (
        "module_a_survey",
        "module_b_srm",
        "module_c_regulator",
        "survey_rate_limit",
        "survey_open_date",
        "survey_close_date",
        "is_survey_active",
        "survey_instructions",
    ):
        assert expected in keys, expected
    # the derived CAN/CAP flag is visible but never editable
    assert keys["module_b_can_cap"]["editable"] is False
    # platform config is read-only visibility, no secrets
    assert "SUPER_ADMIN" in body["platform"]["canonical_roles"]
    assert "hmac_key" not in body["platform"]["audit_chain"]


def test_config_reads_list_tenants(tenant):
    _super()
    r = _client().get("/api/v1/system-config/tenants")
    assert r.status_code == 200, r.text
    slugs = {t["slug"] for t in r.json()["tenants"]}
    assert tenant in slugs

    r = _client().get(f"/api/v1/system-config/{tenant}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["slug"] == tenant
    assert "module_a_survey" in body["values"]
    assert "survey_rate_limit" in body["values"]

    r = _client().get("/api/v1/system-config/does-not-exist")
    assert r.status_code == 404


def test_config_update_is_written_to_the_durable_chain(tenant, monkeypatch):
    monkeypatch.setattr(settings, "SETUP_SECRET", SETUP_KEY)
    _super()

    before = _durable_rows(tenant)
    r = _client().put(
        f"/api/v1/system-config/{tenant}/keys/module_a_survey",
        json={"setup_key": SETUP_KEY, "value": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True
    assert r.json()["value"] is True

    # the flag landed on the tenant row
    assert _tenant_modules(tenant).get("module1") is True

    # the change is on the durable chain, with the actor role
    after = _durable_rows(tenant)
    assert len(after) == len(before) + 1
    event = after[-1]
    assert event.action == "SYSTEM_CONFIG_UPDATED"
    assert event.actor_role == "SUPER_ADMIN"
    assert event.actor_uid == "super@console.test"
    assert event.resource_type == "tenant_config"
    assert event.resource_id == tenant
    assert event.metadata["key"] == "module_a_survey"
    assert event.metadata["value"] is True
    assert event.metadata["target"] == "modules"

    # existing rows are untouched (append-only)
    for old, new in zip(before, after[: len(before)]):
        assert old.current_hash == new.current_hash
        assert old.action == new.action

    # and the change is visible in the console
    listing = _client().get(f"/api/v1/audit/events?tenant_id={tenant}").json()
    top = listing["events"][0]
    assert top["action"] == "SYSTEM_CONFIG_UPDATED"
    assert top["actor_role"] == "SUPER_ADMIN"
    assert top["verification"] == "valid"


def test_config_update_of_a_survey_setting(tenant, monkeypatch):
    monkeypatch.setattr(settings, "SETUP_SECRET", SETUP_KEY)
    _super()
    r = _client().put(
        f"/api/v1/system-config/{tenant}/keys/survey_rate_limit",
        json={"setup_key": SETUP_KEY, "value": 25},
    )
    assert r.status_code == 200, r.text
    assert r.json()["tenant"]["values"]["survey_rate_limit"] == 25

    events = _durable_rows(tenant)
    assert events[-1].action == "SYSTEM_CONFIG_UPDATED"
    assert events[-1].metadata["key"] == "survey_rate_limit"
    assert events[-1].metadata["value"] == 25


def test_config_value_can_be_cleared(tenant, monkeypatch):
    monkeypatch.setattr(settings, "SETUP_SECRET", SETUP_KEY)
    _super()

    r = _client().put(
        f"/api/v1/system-config/{tenant}/keys/survey_rate_limit",
        json={"setup_key": SETUP_KEY, "value": 25},
    )
    assert r.status_code == 200, r.text
    assert r.json()["tenant"]["values"]["survey_rate_limit"] == 25

    # An explicit null clears the value (the platform default applies again).
    r = _client().put(
        f"/api/v1/system-config/{tenant}/keys/survey_rate_limit",
        json={"setup_key": SETUP_KEY, "value": None},
    )
    assert r.status_code == 200, r.text
    assert r.json()["tenant"]["values"]["survey_rate_limit"] is None

    # The clear is audited like any other change.
    events = _durable_rows(tenant)
    assert events[-1].action == "SYSTEM_CONFIG_UPDATED"
    assert events[-1].metadata["key"] == "survey_rate_limit"
    assert events[-1].metadata["value"] is None


def test_config_write_requires_the_setup_key(tenant, monkeypatch):
    monkeypatch.setattr(settings, "SETUP_SECRET", SETUP_KEY)
    _super()

    r = _client().put(
        f"/api/v1/system-config/{tenant}/keys/module_a_survey",
        json={"setup_key": "wrong-key", "value": True},
    )
    assert r.status_code == 403, r.text

    r = _client().put(
        f"/api/v1/system-config/{tenant}/keys/module_a_survey",
        json={"value": True},
    )
    assert r.status_code == 422, r.text

    # nothing was written
    assert not _durable_rows(tenant)


def test_config_write_rejects_unpermitted_keys_and_values(tenant, monkeypatch):
    monkeypatch.setattr(settings, "SETUP_SECRET", SETUP_KEY)
    _super()

    # unknown key
    r = _client().put(
        f"/api/v1/system-config/{tenant}/keys/not_a_real_key",
        json={"setup_key": SETUP_KEY, "value": True},
    )
    assert r.status_code == 404, r.text

    # derived (read-only) key
    r = _client().put(
        f"/api/v1/system-config/{tenant}/keys/module_b_can_cap",
        json={"setup_key": SETUP_KEY, "value": True},
    )
    assert r.status_code == 400, r.text

    # value outside the permitted option set
    r = _client().put(
        f"/api/v1/system-config/{tenant}/keys/survey_rate_limit",
        json={"setup_key": SETUP_KEY, "value": 7},
    )
    assert r.status_code == 400, r.text

    # malformed date
    r = _client().put(
        f"/api/v1/system-config/{tenant}/keys/survey_open_date",
        json={"setup_key": SETUP_KEY, "value": "not-a-date"},
    )
    assert r.status_code == 400, r.text

    # nothing was written
    assert not _durable_rows(tenant)


def test_config_write_to_unknown_tenant_is_404(monkeypatch):
    monkeypatch.setattr(settings, "SETUP_SECRET", SETUP_KEY)
    _super()
    r = _client().put(
        "/api/v1/system-config/no-such-tenant/keys/module_a_survey",
        json={"setup_key": SETUP_KEY, "value": True},
    )
    assert r.status_code == 404, r.text


def test_config_write_without_super_admin_identity_is_refused_by_the_database(tenant):
    """Defence in depth: the SECURITY DEFINER function refuses a non-SUPER_ADMIN."""
    from app.services import system_config_service

    set_current_identity(
        {
            "tenant_uuid": tenant_uuid(tenant),
            "tenant_slug": tenant,
            "role": "TENANT_ADMIN",
            "department": "safety",
            "user_uid": "u-ta",
        }
    )
    with pytest.raises(Exception):
        run(
            system_config_service.apply_key(
                tenant, "module_a_survey", True, actor="ta@console.test", actor_role="TENANT_ADMIN"
            )
        )
    clear_current_identity()
