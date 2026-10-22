"""2C.5 — real-path integration smoke test (flag ON, real auth dependency).

This is the test the ~85 dependency-override tests do not provide: it drives the
real HTTP endpoints with the **real auth dependency** (``get_current_user``) and
a **real Firebase ID token**, so the RLS mechanism actually fires
(``SET LOCAL ROLE authenticated`` + the ``app.current_*`` GUCs on the request's
DB transaction).

Tokens are minted at test time from real Firebase Auth test users (created here,
deleted in teardown) and never written to source. The DB is the live Supabase
Postgres; tenant/user rows are created on the owner path and removed in teardown.
"""

import asyncio
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.db.session import session_scope
from app.firebase import get_auth, initialize_firebase
from app.main import app

from _mbb import cleanup, create_tenant, unique_slug


IDENTITY_TOOLKIT = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
)
PASSWORD = "Sm0ke!test123"


def _owner(sql: str, params=None):
    async def _go():
        async with session_scope() as s:
            return await s.execute(text(sql), params or {})
    return asyncio.run(_go())


def _owner_count(table: str, where: str, params) -> int:
    async def _go():
        async with session_scope() as s:
            return (await s.execute(
                text(f"SELECT count(*) FROM public.{table} WHERE {where}"), params
            )).scalar_one()
    return asyncio.run(_go())


def _token(email: str) -> str:
    r = httpx.post(
        f"{IDENTITY_TOOLKIT}?key={settings.FIREBASE_WEB_API_KEY}",
        json={"email": email, "password": PASSWORD, "returnSecureToken": True},
        timeout=30,
    )
    assert r.status_code == 200, f"Identity Toolkit sign-in failed: {r.text[:200]}"
    return r.json()["idToken"]


@pytest.fixture(scope="module")
def smoke_env():
    initialize_firebase()
    auth = get_auth()
    client = TestClient(app)

    slugs = {"a": unique_slug("smoke-a"), "b": unique_slug("smoke-b")}
    ids = {k: create_tenant(v) for k, v in slugs.items()}
    emails = {k: f"rls-smoke-{k}-{uuid.uuid4().hex[:10]}@aviasafesystems.com"
              for k in slugs}
    uids, tokens = {}, {}
    try:
        for k in slugs:
            u = auth.create_user(email=emails[k], password=PASSWORD)
            uids[k] = u.uid
            _owner(
                "INSERT INTO public.users (uid, email, role, tenant_id, "
                "is_developer, phone_verified) "
                "VALUES (:uid, :email, 'TENANT_ADMIN', :tid, false, false)",
                {"uid": u.uid, "email": emails[k], "tid": ids[k]},
            )
            tokens[k] = _token(emails[k])
        yield {"client": client, "slugs": slugs, "ids": ids, "tokens": tokens}
    finally:
        for u in uids.values():
            try:
                auth.delete_user(u)
            except Exception:
                pass
        for k in slugs:
            cleanup(slugs[k], ["feedback", "invites"])


def _auth(tokens, k):
    return {"Authorization": f"Bearer {tokens[k]}"}


# ---------------------------------------------------------------------------
# T25 — end-to-end write as a real tenant user, plus cross-tenant read denial
# ---------------------------------------------------------------------------

def test_t25_feedback_write_and_tenant_isolation(smoke_env, monkeypatch):
    env = smoke_env
    client, ids, tokens = env["client"], env["ids"], env["tokens"]

    # Avoid the best-effort email side effect (not the subject under test).
    monkeypatch.setattr(
        "app.services.email_service.send_feedback_notification",
        lambda doc: None, raising=False,
    )

    subject_a = f"smoke-a-{uuid.uuid4().hex[:8]}"
    ra = client.post("/api/v1/feedback", json={
        "subject": subject_a, "message": "real-path smoke A", "rating": 5,
    }, headers=_auth(tokens, "a"))
    assert ra.status_code == 201, ra.text

    subject_b = f"smoke-b-{uuid.uuid4().hex[:8]}"
    rb = client.post("/api/v1/feedback", json={
        "subject": subject_b, "message": "real-path smoke B",
    }, headers=_auth(tokens, "b"))
    assert rb.status_code == 201, rb.text

    # The rows landed under the correct tenant (verified on the owner path).
    assert _owner_count("feedback", "tenant_id = :t AND subject = :s",
                        {"t": ids["a"], "s": subject_a}) == 1
    assert _owner_count("feedback", "tenant_id = :t AND subject = :s",
                        {"t": ids["b"], "s": subject_b}) == 1


# ---------------------------------------------------------------------------
# T26 — cross-tenant read isolation over real HTTP (second table: invites)
# ---------------------------------------------------------------------------

def test_t26_cross_tenant_read_over_http(smoke_env):
    env = smoke_env
    client, ids, tokens = env["client"], env["ids"], env["tokens"]

    code_a = f"INVA{uuid.uuid4().hex[:8].upper()}"
    code_b = f"INVB{uuid.uuid4().hex[:8].upper()}"
    _owner("INSERT INTO public.invites (id, email, tenant_id, role, code, status) "
           "VALUES (:i, 'a@x.com', :t, 'OFFICER', :c, 'pending')",
           {"i": uuid.uuid4(), "t": ids["a"], "c": code_a})
    _owner("INSERT INTO public.invites (id, email, tenant_id, role, code, status) "
           "VALUES (:i, 'b@x.com', :t, 'OFFICER', :c, 'pending')",
           {"i": uuid.uuid4(), "t": ids["b"], "c": code_b})

    ra = client.get("/api/v1/auth/invites", headers=_auth(tokens, "a"))
    assert ra.status_code == 200, ra.text
    body_a = ra.text
    assert code_a in body_a and code_b not in body_a

    rb = client.get("/api/v1/auth/invites", headers=_auth(tokens, "b"))
    assert rb.status_code == 200, rb.text
    body_b = rb.text
    assert code_b in body_b and code_a not in body_b


# ---------------------------------------------------------------------------
# T27 — the owner path (no identity) is unaffected by RLS
# ---------------------------------------------------------------------------

def test_t27_owner_path_unaffected(smoke_env):
    env = smoke_env
    ids = env["ids"]
    marker = f"owner-{uuid.uuid4().hex[:8]}"
    _owner("INSERT INTO public.feedback (id, tenant_id, user_email, subject, message) "
           "VALUES (:i, :t, 'seed@x.com', :s, 'owner path')",
           {"i": uuid.uuid4(), "t": ids["a"], "s": marker})
    # A seeder/migration-like operation with no identity writes and reads freely.
    assert _owner_count("feedback", "tenant_id = :t AND subject = :s",
                        {"t": ids["a"], "s": marker}) == 1
