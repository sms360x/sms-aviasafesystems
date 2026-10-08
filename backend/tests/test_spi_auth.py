# ============================================================================
# 1A.2 — SPI authentication regression tests (H1).
#
# Verifies that every SPI route requires authentication and (for tenant routes)
# tenant scope, using the real FastAPI app. Tokens are simulated by patching
# verify_firebase_token in both the auth dependency and the RBAC middleware.
# The SPI/SPT services are stubbed so no live DB is touched.
# ============================================================================

import pytest

from app.middleware import rbac_middleware as mw
from app.middleware import auth as auth_mw
from app.api.v1 import spi as spi_mod

TOKENS = {
    "reg-token": {"uid": "u-reg", "email": "smd@caanepal.gov.np", "role": "STATE_SMD", "tenant_id": None},
    "tenant-token": {"uid": "u-t", "email": "safety@sita-air.com", "role": "TENANT_ADMIN", "tenant_id": "air1"},
    "other-token": {"uid": "u-o", "email": "safety@other-air.com", "role": "TENANT_ADMIN", "tenant_id": "air2"},
}


def _fake_verify(token):
    return TOKENS.get(token)


class _FakeSPI:
    def __init__(self, *a, **k):
        pass

    def get_spi_definitions(self):
        return []

    def calculate_all_spis(self, *a, **k):
        return {}

    def get_tenant_status(self, *a, **k):
        return []

    def get_tenant_trend(self, *a, **k):
        return []

    def get_state_values(self, *a, **k):
        return {}

    def get_state_status(self, *a, **k):
        return []


class _FakeSPT:
    def __init__(self, *a, **k):
        pass

    def list_state_spts(self, period=None):
        return []


@pytest.fixture
def spi_env(monkeypatch):
    monkeypatch.setattr(auth_mw, "verify_firebase_token", _fake_verify)
    monkeypatch.setattr(mw, "verify_firebase_token", _fake_verify)
    monkeypatch.setattr(auth_mw, "_tenant_is_suspended", lambda tenant_id: False)
    monkeypatch.setattr(spi_mod, "SPIService", _FakeSPI)
    import app.services.state_spt_service as spt
    monkeypatch.setattr(spt, "StateSPTService", _FakeSPT)


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# --- 2.1 State SPI routes -------------------------------------------------

def test_state_values_no_token(client, spi_env):
    assert client.get("/api/v1/spi/state/values").status_code in (401, 403)


def test_state_values_invalid_token(client, spi_env):
    assert client.get("/api/v1/spi/state/values", headers=_h("nonsense")).status_code in (401, 403)


def test_state_values_regulator_200(client, spi_env):
    assert client.get("/api/v1/spi/state/values", headers=_h("reg-token")).status_code == 200


def test_state_values_airline_forbidden(client, spi_env):
    assert client.get("/api/v1/spi/state/values", headers=_h("tenant-token")).status_code == 403


def test_state_targets_regulator_200(client, spi_env):
    assert client.get("/api/v1/spi/state/targets", headers=_h("reg-token")).status_code == 200


# --- 2.2 Tenant SPI routes ------------------------------------------------

def test_tenant_values_no_token(client, spi_env):
    assert client.get("/api/v1/spi/tenant/air1/values").status_code in (401, 403)


def test_tenant_values_own_tenant_200(client, spi_env):
    assert client.get("/api/v1/spi/tenant/air1/values", headers=_h("tenant-token")).status_code == 200


def test_tenant_values_foreign_tenant_403(client, spi_env):
    assert client.get("/api/v1/spi/tenant/air2/values", headers=_h("tenant-token")).status_code == 403


def test_tenant_values_regulator_cross_tenant_200(client, spi_env):
    # Regulator (STATE_SMD) is a cross-tenant role: allow is the intended behaviour.
    assert client.get("/api/v1/spi/tenant/air1/values", headers=_h("reg-token")).status_code == 200


def test_definitions_no_token(client, spi_env):
    assert client.get("/api/v1/spi/definitions").status_code in (401, 403)


def test_definitions_authenticated_200(client, spi_env):
    assert client.get("/api/v1/spi/definitions", headers=_h("tenant-token")).status_code == 200


# --- 2.3 Module gate interaction ------------------------------------------

def test_state_path_is_module_gated(client, spi_env):
    # /spi/state is in ENDPOINT_MODULE_MAP -> module5
    assert mw.get_module_for_path("/api/v1/spi/state/values") == "module5"


def test_tenant_path_not_in_middleware_map(client, spi_env):
    # /spi/tenant is NOT in ENDPOINT_MODULE_MAP; protection is route-level only.
    # Reported as a finding (no middleware entry added without SME approval).
    assert mw.get_module_for_path("/api/v1/spi/tenant/air1/values") == ""
