"""M1 — Firebase ID token revocation regression tests (SECURITY_REVIEW M1).

The single token-verification site is ``app.firebase.verify_firebase_token``
(``backend/app/firebase.py``), which calls
``auth.verify_id_token(token, check_revoked=True)``. Every authentication
caller routes through it (``middleware/auth.py``, ``middleware/rbac_middleware.py``,
``routes/admin.py``, ``routes/auth.py``), so enforcing ``check_revoked=True``
here enforces it everywhere.

This suite pins that contract so a future refactor cannot silently drop
revocation checking (the SDK default is ``check_revoked=False``).

Covers:
  * the verifier passes ``check_revoked=True``                  (core pin)
  * a valid, non-revoked token            -> claims returned, 200
  * a revoked token                       -> rejected, 401
  * a token whose user was deleted        -> rejected, 401
  * an expired token                      -> rejected, 401
  * a malformed token                     -> rejected, 401
"""

import pytest
from fastapi.testclient import TestClient
from firebase_admin import auth as fb_auth

from app.main import app
from app import firebase as app_firebase


# A protected endpoint that requires only a valid ID token: no tenant/DB side
# effects after auth, and no App Check dependency. Used to assert the HTTP
# status the middleware stack produces for each verifier outcome.
PROTECTED_URL = "/api/v1/nhrc/mapping-rules"

VALID_CLAIMS = {
    "uid": "u-tok",
    "email": "smd@caanepal.gov.np",
    "role": "CAAN_SMD",
    "tenant_id": None,
}


# ---------------------------------------------------------------------------
# Failure modes the verifier must map to None (=> 401 at every call site).
# Simulated at the SDK boundary (auth.verify_id_token), which is exactly where
# the real SDK raises them:
#   * RevokedIdTokenError  — token revoked (check_revoked path)
#   * UserNotFoundError    — user record deleted (check_revoked path)
#   * ExpiredIdTokenError  — token past exp
#   * InvalidIdTokenError  — malformed / wrong-signature token
# ---------------------------------------------------------------------------

_REJECTION_CASES = {
    "revoked": lambda: fb_auth.RevokedIdTokenError(
        "The Firebase ID token has been revoked."
    ),
    "deleted_user": lambda: fb_auth.UserNotFoundError("no user record"),
    "expired": lambda: fb_auth.ExpiredIdTokenError("Token expired", Exception("cause")),
    "malformed": lambda: fb_auth.InvalidIdTokenError("Invalid ID token"),
}


def _spy_verify(monkeypatch, *, result=None, exc=None):
    """Patch the SDK call and capture how it was invoked."""
    calls = {}

    def fake_verify_id_token(token, **kwargs):
        calls["token"] = token
        calls["kwargs"] = kwargs
        if exc is not None:
            raise exc
        return result

    monkeypatch.setattr(app_firebase.auth, "verify_id_token", fake_verify_id_token)
    return calls


# ---------------------------------------------------------------------------
# Core regression pin: check_revoked must be True
# ---------------------------------------------------------------------------

def test_verifier_passes_check_revoked_true(monkeypatch):
    calls = _spy_verify(monkeypatch, result=dict(VALID_CLAIMS))
    app_firebase.verify_firebase_token("a-token")
    assert calls["kwargs"].get("check_revoked") is True


# ---------------------------------------------------------------------------
# Accepted token
# ---------------------------------------------------------------------------

def test_valid_non_revoked_token_accepted(monkeypatch):
    _spy_verify(monkeypatch, result=dict(VALID_CLAIMS))
    assert app_firebase.verify_firebase_token("a-token") == VALID_CLAIMS


def test_valid_token_accepted_over_http(monkeypatch):
    _spy_verify(monkeypatch, result=dict(VALID_CLAIMS))
    resp = TestClient(app).get(
        PROTECTED_URL, headers={"Authorization": "Bearer a-token"}
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Rejected tokens — verifier maps the SDK error to None
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", list(_REJECTION_CASES))
def test_rejected_token_returns_none(monkeypatch, mode):
    _spy_verify(monkeypatch, exc=_REJECTION_CASES[mode]())
    assert app_firebase.verify_firebase_token("a-token") is None


# ---------------------------------------------------------------------------
# Rejected tokens — end to end, the HTTP surface answers 401
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", list(_REJECTION_CASES))
def test_rejected_token_gets_401_over_http(monkeypatch, mode):
    _spy_verify(monkeypatch, exc=_REJECTION_CASES[mode]())
    resp = TestClient(app).get(
        PROTECTED_URL, headers={"Authorization": "Bearer a-token"}
    )
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_missing_token_rejected_over_http():
    # HTTPBearer auto-rejects a missing header with 403; an invalid one is
    # mapped to 401 by get_current_user. Both are "rejected".
    resp = TestClient(app).get(PROTECTED_URL)
    assert resp.status_code in (401, 403)
