# ============================================================================
# 1C.2 — AE non-delegability (CAAN SRM Manual §2.3.3).
#
# The Accountable Executive's signature on a risk acceptance cannot be
# delegated. Risk acceptance is graded on the INITIAL risk tolerability by
# `sram_service.AUTHORITY_ROLES`: an Intolerable risk may only be accepted by
# the ACCOUNTABLE_EXECUTIVE. The accepting identity is taken from the session,
# never from a request parameter.
#
# Deterministic (no live DB): the DB helpers used by `accept_risk` are
# monkeypatched; route tests override the auth dependency.
# ============================================================================

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.auth import get_current_user
from app.db.db_models import SramRiskRegisterEntry
from app.services import sram_service

client = TestClient(app)


def _run(coro):
    return asyncio.run(coro)


class _FakeSession:
    async def flush(self):
        return None


class _FakeCtx:
    async def __aenter__(self):
        return _FakeSession()

    async def __aexit__(self, *exc):
        return False


def _entry(tolerability="Intolerable"):
    row = SramRiskRegisterEntry(
        tenant_id=uuid.uuid4(),
        hazard_id="H-1",
        status="in_progress",
        tolerability_current=tolerability,
    )
    # Process-conformance signature (Signature 1) is already present.
    row.process_by = uuid.uuid4()
    row.process_signed_at = datetime.now(timezone.utc)
    return row


def _patch_service(monkeypatch, row, signer=None):
    async def _resolve_entry(session, rid, data, tid):
        return row

    async def _no_bowtie(session, hazard_id, tid):
        return None

    async def _resolve_user(user):
        return signer or uuid.uuid4()

    monkeypatch.setattr(sram_service, "session_scope", lambda: _FakeCtx())
    monkeypatch.setattr(sram_service, "_resolve_risk_entry", _resolve_entry)
    monkeypatch.setattr(sram_service, "_get_bowtie_by_hazard", _no_bowtie)
    monkeypatch.setattr(sram_service, "_resolve_user_uuid", _resolve_user)


def _override(role, tenant_id="air1"):
    app.dependency_overrides[get_current_user] = lambda: {
        "uid": "u1", "email": f"{str(role).lower()}@air1.com",
        "role": role, "tenant_id": tenant_id,
    }


def _clear():
    app.dependency_overrides.clear()


# T1 — The AE of the owning tenant can accept an Intolerable risk; the accepted
#      identity is the session user.
def test_ae_can_accept_intolerable(monkeypatch):
    row = _entry("Intolerable")
    signer = uuid.uuid4()
    _patch_service(monkeypatch, row, signer=signer)
    out = _run(sram_service.accept_risk(
        "H-1", {"alarp_justification": "x" * 20}, "air1",
        {"role": "ACCOUNTABLE_EXECUTIVE", "uid": "ae1", "email": "ae@air1.com"},
    ))
    assert out["accepted"] is True
    assert out["accepted_by"] == str(signer)
    assert out["initial_authority"] == "Accountable Manager"


# T2 — A non-AE user cannot sign off an Intolerable risk acceptance.
@pytest.mark.parametrize("role", [
    "DEPT_ADMIN", "OFFICER", "SAFETY_OFFICER", "TENANT_ADMIN", "SAG_MEMBER",
])
def test_non_ae_cannot_accept_intolerable(monkeypatch, role):
    row = _entry("Intolerable")
    _patch_service(monkeypatch, row)
    with pytest.raises(HTTPException) as exc:
        _run(sram_service.accept_risk(
            "H-1", {"alarp_justification": "x" * 20}, "air1",
            {"role": role, "uid": "u1", "email": "u1@air1.com"},
        ))
    assert exc.value.status_code == 403
    assert row.accepted is not True


# T3 — A same-tenant caller cannot impersonate the AE via request parameters:
#      the session identity is authoritative and unknown fields are dropped.
def test_request_param_cannot_impersonate_ae(monkeypatch):
    captured = {}

    async def fake_accept(rid, data, tenant, user):
        captured["user"] = user
        captured["data"] = data
        return {"accepted": True}

    monkeypatch.setattr(sram_service, "accept_risk", fake_accept)
    _override("DEPT_ADMIN")
    try:
        r = client.post("/api/v1/sram/risk/accept", json={
            "hazard_id": "H-1",
            "alarp_justification": "x" * 20,
            # impersonation attempts — must be ignored
            "accepted_by": "someone-else",
            "signer": "ae@air1.com",
            "role": "ACCOUNTABLE_EXECUTIVE",
            "user": {"role": "ACCOUNTABLE_EXECUTIVE"},
        })
        assert r.status_code == 200, r.text
        assert captured["user"]["role"] == "DEPT_ADMIN"
        assert captured["user"]["email"] == "dept_admin@air1.com"
        assert "accepted_by" not in captured["data"]
        assert "signer" not in captured["data"]
        assert "role" not in captured["data"]
        assert "user" not in captured["data"]
    finally:
        _clear()


# T4 — A cross-tenant caller cannot act as the AE.
def test_cross_tenant_role_cannot_accept(monkeypatch):
    row = _entry("Intolerable")
    _patch_service(monkeypatch, row)
    with pytest.raises(HTTPException) as exc:
        _run(sram_service.accept_risk(
            "H-1", {"alarp_justification": "x" * 20}, "air1",
            {"role": "STATE_SMD", "uid": "c1", "email": "caan@x.com", "tenant_id": None},
        ))
    assert exc.value.status_code == 403


def test_cross_tenant_route_requires_tenant():
    _override("STATE_SMD", tenant_id=None)
    try:
        r = client.post("/api/v1/sram/risk/accept",
                        json={"hazard_id": "H-1", "alarp_justification": "x" * 20})
        assert r.status_code == 403, r.text
    finally:
        _clear()


# T6 — The OFFICER entry of the authority table is a Safety Officer entry: it
#      only applies to an officer of the Safety (Corporate Safety) department.
#      A Flight Ops officer may not accept a Tolerable risk.
def test_officer_authority_is_scoped_to_the_safety_department(monkeypatch):
    row = _entry("Tolerable")
    _patch_service(monkeypatch, row)

    # A Flight Ops officer is not a Safety Officer -> denied.
    with pytest.raises(HTTPException) as exc:
        _run(sram_service.accept_risk(
            "H-1", {"alarp_justification": "x" * 20}, "air1",
            {"role": "OFFICER", "uid": "u1", "email": "u1@air1.com",
             "department": "flight_ops"},
        ))
    assert exc.value.status_code == 403
    assert row.accepted is not True

    # An officer of the Safety department is a Safety Officer -> allowed.
    out = _run(sram_service.accept_risk(
        "H-1", {"alarp_justification": "x" * 20}, "air1",
        {"role": "OFFICER", "uid": "u2", "email": "so@air1.com",
         "department": "safety"},
    ))
    assert out["accepted"] is True


# T5 — No override / delegation path exists for risk acceptance, so there is no
#      override audit to record. (Recorded in docs/step1/1C.2_ae_non_delegability.md.)
def test_get_accountable_executive_admits_only_ae():
    """2B.4b closure fix: the closure dependency admits only an AE for its
    owning tenant; denies the retired TENANT_ADMIN and cross-tenant callers."""
    from app.middleware.auth import get_accountable_executive

    async def _run_gate():
        assert await get_accountable_executive(
            {"role": "ACCOUNTABLE_EXECUTIVE", "tenant_id": "t1"}) == {
                "role": "ACCOUNTABLE_EXECUTIVE", "tenant_id": "t1"}
        for denied in (
            {"role": "ACCOUNTABLE_EXECUTIVE", "tenant_id": None},
            {"role": "TENANT_ADMIN", "tenant_id": "t1"},
            {"role": "STATE_SMD", "tenant_id": None},
            {"role": "SUPER_ADMIN", "tenant_id": None},
        ):
            with pytest.raises(HTTPException) as exc:
                await get_accountable_executive(denied)
            assert exc.value.status_code == 403

    _run(_run_gate())


def test_no_override_or_delegation_endpoint():
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/v1/sram/risk/accept" in paths
    assert not any(
        ("override" in p.lower() or "delegat" in p.lower()) for p in paths
    )
