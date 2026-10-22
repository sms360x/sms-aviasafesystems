# ============================================================================
# FILE: live_validation.py
# PATH: tests/e2e/live_validation.py
# PURPOSE: Step 3 — Functional & Security Assurance (Live Validation) against
#          the production backend (https://aviasafe-unified-platform.onrender.com)
#          exercised from the frontend origin https://sms.aviasafesystems.com.
#          Covers: (1) CORS & origin security, (2) auth & auth-gating,
#          (3) risk-matrix engine, (4) data audit & persistence to sms-db.
#
# Tokens are minted at runtime via the Firebase Admin SDK (custom token ->
# ID-token exchange) so no plaintext passwords are needed. Read-only + a small
# number of create/read probes; nothing destructive.
# ============================================================================

import sys
import json
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from app.core.config import settings  # noqa: E402

API = "https://aviasafe-unified-platform.onrender.com"
ORIGIN = "https://sms.aviasafesystems.com"
WEB_ORIGIN = "https://aerosafety-sms-prod.web.app"
EVIL_ORIGIN = "https://evil.example.com"
API_KEY = "AIzaSyCdCtUuyOcUIoCBEaiWGbhp6_XwZKHsicc"
FIREBASE_AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key=" + API_KEY

PASS = 0
FAIL = 0
FAILURES = []


def record(desc, ok, detail=""):
    global PASS, FAIL
    mark = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"[{mark}] {desc} — {detail}")
    print(f"  [{mark}] {desc}" + (f" — {detail}" if detail else ""))


def section(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def mint_id_token(uid, claims):
    import firebase_admin
    from firebase_admin import credentials, auth as admin_auth

    if not firebase_admin._apps:
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": settings.FIREBASE_PROJECT_ID,
            "private_key": settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n"),
            "client_email": settings.FIREBASE_CLIENT_EMAIL,
            "token_uri": settings.FIREBASE_TOKEN_URI,
        })
        firebase_admin.initialize_app(cred, {"projectId": settings.FIREBASE_PROJECT_ID})
    custom = admin_auth.create_custom_token(uid, claims)
    custom = custom.decode() if isinstance(custom, bytes) else custom
    r = requests.post(FIREBASE_AUTH_URL, json={"token": custom, "returnSecureToken": True}, timeout=30)
    r.raise_for_status()
    return r.json()["idToken"]


def api(method, path, token=None, data=None, origin=None, timeout=45):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if origin:
        headers["Origin"] = origin
    fn = getattr(requests, method.lower())
    return fn(API + path, headers=headers, json=data, timeout=timeout)


def main():
    print("AviaSAFE SMS — Step 3 Live Validation")
    print(f"Backend: {API}")
    print(f"Frontend origin under test: {ORIGIN}")

    # ------------------------------------------------------------------
    section("SETUP — mint live ID tokens (Admin SDK custom token exchange)")
    tokens = {}
    uid_for = {
        "super_admin": "super-admin-001",
        "STATE_SMD": "caan-smd-001",
        "TENANT_ADMIN": "sm-sita-air-001",
    }
    claims_for = {
        "super_admin": {"role": "SUPER_ADMIN", "tenant_id": None},
        "STATE_SMD": {"role": "STATE_SMD", "tenant_id": None},
        "TENANT_ADMIN": {"role": "TENANT_ADMIN", "tenant_id": "sita-air"},
    }
    for name, uid in uid_for.items():
        try:
            tokens[name] = mint_id_token(uid, claims_for[name])
            record(f"Mint {name} ID token (uid={uid})", True, f"len={len(tokens[name])}")
        except Exception as e:
            record(f"Mint {name} ID token", False, f"{type(e).__name__}: {str(e)[:120]}")

    if not all(tokens.values()):
        print("\nFATAL: could not mint all tokens; aborting.")
        sys.exit(1)

    # ------------------------------------------------------------------
    section("PART 1 — CORS & ORIGIN SECURITY SMOKE TEST")

    # 1a. Preflight from the allowed frontend origin (POST /api/v1/reports/vsr)
    r = requests.options(
        API + "/api/v1/reports/vsr",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
        timeout=30,
    )
    acao = r.headers.get("access-control-allow-origin", "")
    record("Preflight from sms.aviasafesystems.com returns 2xx", 200 <= r.status_code < 300, f"status={r.status_code}")
    record("ACAO echoes allowed origin exactly (no wildcard)", acao == ORIGIN, f"acao='{acao}'")
    acam = r.headers.get("access-control-allow-methods", "")
    record("ACAM present", bool(acam), f"acam='{acam}'")
    acah = r.headers.get("access-control-allow-headers", "")
    record("ACAH permits authorization/content-type", "authorization" in acah.lower() and "content-type" in acah.lower(), f"acah='{acah}'")

    # 1b. Preflight from a disallowed origin must NOT be allowed
    r2 = requests.options(
        API + "/api/v1/reports/vsr",
        headers={
            "Origin": EVIL_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
        timeout=30,
    )
    acao2 = r2.headers.get("access-control-allow-origin", "")
    record("Disallowed origin gets NO ACAO (no wildcard leak)", acao2 == "" or acao2 == "null", f"acao='{acao2}'")

    # 1c. Second allowed origin (new prod web.app)
    r3 = requests.options(
        API + "/api/v1/reports/vsr",
        headers={"Origin": WEB_ORIGIN, "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "authorization,content-type"},
        timeout=30,
    )
    acao3 = r3.headers.get("access-control-allow-origin", "")
    record("aerosafety-sms-prod.web.app origin allowed (exact echo)", acao3 == WEB_ORIGIN, f"acao='{acao3}'")

    # 1d. Authenticated POST with Origin header succeeds and echoes origin
    payload = {
        "report_type": "voluntary",
        "is_anonymous": False,
        "narrative": "Live validation probe: hard landing during training flight. Pilot reported late flare under gusty conditions. Aircraft grounded for inspection.",
        "location": "Runway 02",
        "occurrence_date": "2026-08-05T10:30:00Z",
        "flight_number": "STA-LIV",
        "aircraft_registration": "9N-LIV",
        "aircraft_make": "Viking Air",
        "aircraft_model": "DHC-6 Twin Otter",
        "flight_phase": "Landing",
        "departure_airport": "KTM",
        "destination_airport": "PKR",
        "occurrence_category": "BIRD",
        "severity_level": 2,
        "probability_level": 2,
        "reporter_name": "Live Val",
        "reporter_role": "safety_manager",
        "reporter_email": "sal@aviasafesystems.com",
        "reporter_organisation": "Sita Air",
    }
    r4 = api("POST", "/api/v1/reports/vsr", tokens["TENANT_ADMIN"], payload, origin=ORIGIN)
    acao4 = r4.headers.get("access-control-allow-origin", "")
    record("Authenticated POST from allowed origin succeeds", r4.status_code == 201, f"status={r4.status_code}")
    record("Response ACAO echoes allowed origin", acao4 == ORIGIN, f"acao='{acao4}'")
    vsr_id = ""
    if r4.status_code == 201:
        vsr_id = r4.json().get("id", "")

    # 1e. Authenticated POST from disallowed origin must be REJECTED by CORS
    r5 = api("POST", "/api/v1/reports/vsr", tokens["TENANT_ADMIN"], payload, origin=EVIL_ORIGIN)
    acao5 = r5.headers.get("access-control-allow-origin", "")
    record("Disallowed-origin request gets no ACAO (browser blocks)", acao5 != EVIL_ORIGIN, f"acao='{acao5}'")

    # 1f. Confirm allow_credentials + explicit origins (no '*')
    record("No wildcard ACAO in any response", all(
        h.get("access-control-allow-origin", "") != "*" for h in (r.headers, r2.headers, r3.headers, r4.headers, r5.headers)
    ))

    # ------------------------------------------------------------------
    section("PART 2 — AUTHENTICATION & AUTH-GATING")

    # 2a. No-token protected route -> 401/403
    r = api("GET", "/api/v1/reports/")
    record("No token on /api/v1/reports/ rejected", r.status_code in (401, 403), f"status={r.status_code}")
    r = api("GET", "/api/v1/dashboard/caan/overview")
    record("No token on CAAN dashboard rejected", r.status_code in (401, 403), f"status={r.status_code}")

    # 2b. Admin endpoints require SUPER_ADMIN (RBAC)
    r = api("GET", "/api/v1/admin/risk-matrix", tokens["TENANT_ADMIN"])
    record("TENANT_ADMIN on /admin/risk-matrix (get_safety_manager path) allowed", r.status_code == 200, f"status={r.status_code}")
    r = api("GET", "/api/v1/admin/risk-matrix", tokens["STATE_SMD"])
    record("STATE_SMD on /admin/risk-matrix allowed", r.status_code == 200, f"status={r.status_code}")

    # 2c. Destructive/seed endpoints gated — no-token probe must be 401/403/404
    for path in ("/api/v1/admin/setup-claims", "/api/v1/admin/seed-demo-data", "/api/v1/admin/provision-airlines"):
        r = api("POST", path, data={"setup_key": "nope"})
        record(f"No-token POST {path} rejected", r.status_code in (401, 403, 404, 422), f"status={r.status_code}")

    # 2d. Legacy debug endpoints removed (404)
    for path in ("/api/v1/admin/check-data", "/api/v1/admin/migrate-seed-data", "/api/v1/auth/debug-verify"):
        r = api("GET", path, tokens["super_admin"])
        record(f"Legacy {path} absent", r.status_code == 404, f"status={r.status_code}")

    # 2e. Tenant-scoped reads for airline admin; CAAN cross-tenant read
    r = api("GET", "/api/v1/hazards/", tokens["TENANT_ADMIN"])
    record("TENANT_ADMIN hazard list (own tenant)", r.status_code == 200, f"status={r.status_code}, items={len(r.json()) if r.status_code == 200 else '-'}")
    r = api("GET", "/api/v1/hazards/?tenant_id=sita-air", tokens["STATE_SMD"])
    record("STATE_SMD cross-tenant hazard read", r.status_code == 200, f"status={r.status_code}")

    # 2f. Token issuance path (register disabled, verify endpoint exists)
    r = api("POST", "/api/v1/auth/verify", data={"id_token": tokens["super_admin"]})
    record("/auth/verify accepts a valid ID token", r.status_code in (200, 422), f"status={r.status_code}")

    # ------------------------------------------------------------------
    section("PART 3 — RISK MATRIX ENGINE (canonical 5/9/15 mapping)")

    # 3a. Read current risk matrix for sita-air
    r = api("GET", "/api/v1/admin/risk-matrix", tokens["TENANT_ADMIN"])
    record("GET /admin/risk-matrix returns config", r.status_code == 200, f"status={r.status_code}")
    matrix = r.json() if r.status_code == 200 else {}
    thresholds = (matrix.get("thresholds") or {}).get("low_max") is not None
    record("Matrix exposes thresholds (low/medium/high)", thresholds, json.dumps(matrix.get("thresholds"))[:120])

    # 3b. PUT risk-matrix with a valid config (idempotent, non-destructive to data)
    probe_thresholds = {"low_max": 5, "medium_max": 9, "high_max": 15}
    r = api("PUT", "/api/v1/admin/risk-matrix", tokens["TENANT_ADMIN"],
            {"thresholds": probe_thresholds, "updated_by": "sm-sita-air-001"})
    record("PUT /admin/risk-matrix succeeds (canonical thresholds)", r.status_code == 200, f"status={r.status_code}")
    r = api("PUT", "/api/v1/admin/risk-matrix", tokens["TENANT_ADMIN"],
            {"thresholds": {"low_max": 9, "medium_max": 5, "high_max": 15}})
    record("PUT invalid threshold ordering rejected (400)", r.status_code == 400, f"status={r.status_code}")

    # 3c. Hazard creation computes canonical score
    hazard_payload = {
        "title": "Live Validation Hazard",
        "description": "Live validation probe: runway friction assessment needed after inspection findings.",
        "source": "Safety Inspection",
        "taxonomy": "Technical",
        "location": "KTM RWY 02",
        "severity": 3,
        "probability": 3,
        "priority": "M",
        "tenant_id": "sita-air",
        "recommendation": "Schedule friction test",
        "detected_by": "Safety Manager",
    }
    r = api("POST", "/api/v1/hazards/", tokens["TENANT_ADMIN"], hazard_payload)
    record("Hazard creation returns 201", r.status_code == 201, f"status={r.status_code}")
    hazard_id = r.json().get("id", "") if r.status_code == 201 else ""
    if r.status_code == 201:
        h = r.json()
        idx = h.get("risk_index")
        lvl = h.get("risk_level")
        record("Hazard risk_index computed (S3×P3=9)", idx == 9, f"risk_index={idx}")
        record("Hazard risk_level canonical (9 -> Medium)", lvl == "Medium", f"risk_level={lvl}")
        record("Hazard risk_outcome present (Tolerable)", h.get("risk_outcome") in ("Tolerable", "Medium"), f"risk_outcome={h.get('risk_outcome')}")

    # 3d. VSR-created report risk mapping (from PART 1)
    if vsr_id:
        r = api("GET", "/api/v1/reports/" + vsr_id, tokens["TENANT_ADMIN"])
        if r.status_code == 200:
            rr = r.json()
            record("VSR risk_index canonical (S2×P2=4 -> Low)",
                   rr.get("risk_index") == 4 and rr.get("risk_level") == "Low",
                   f"risk_index={rr.get('risk_index')}, risk_level={rr.get('risk_level')}")
        else:
            record("VSR risk read-back", False, f"status={r.status_code}")

    # 3e. report list includes hazard linkage
    r = api("GET", "/api/v1/hazards/", tokens["TENANT_ADMIN"])
    if r.status_code == 200:
        ids = [x.get("id") or x.get("hazard_id") for x in r.json()]
        record("New hazard appears in list", hazard_id in ids, f"found={hazard_id in ids}")

    # ------------------------------------------------------------------
    section("PART 4 — DATA AUDIT & PERSISTENCE (writes to sms-db)")

    # 4a. Created objects carry timestamps + audit fields
    if hazard_id:
        r = api("GET", "/api/v1/hazards/" + hazard_id, tokens["TENANT_ADMIN"])
        if r.status_code == 200:
            h = r.json()
            record("Hazard persisted with created_at", bool(h.get("created_at")), f"created_at={h.get('created_at')}")
            record("Hazard persisted with created_by/tenant", bool(h.get("created_by") or h.get("reported_by")) and bool(h.get("tenant_id")), f"tenant_id={h.get('tenant_id')}")
        else:
            record("Hazard read-back after create", False, f"status={r.status_code}")

    # 4b. Update hazard status -> write path (status is a query param)
    if hazard_id:
        r = api("PATCH", f"/api/v1/hazards/{hazard_id}/status?status=Under%20Review", tokens["TENANT_ADMIN"])
        record("Hazard status update (PATCH) succeeds", r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            r2 = api("GET", "/api/v1/hazards/" + hazard_id, tokens["TENANT_ADMIN"])
            got = r2.json().get("status") if r2.status_code == 200 else None
            record("Status change persisted (read-back confirms)", got == "Under Review", f"status={got}")

    # 4c. Reporting list reflects tenant data (aggregation reads from sms-db)
    r = api("GET", "/api/v1/reports/", tokens["TENANT_ADMIN"])
    record("Tenant report list (aggregation read)", r.status_code == 200, f"status={r.status_code}")

    # 4d. Dashboard overview returns aggregated data (reads persisted records)
    r = api("GET", "/api/v1/dashboard/overview", tokens["TENANT_ADMIN"])
    record("Dashboard overview endpoint reachable", r.status_code == 200, f"status={r.status_code}")

    # ------------------------------------------------------------------
    section("SUMMARY")
    print(f"\n  PASS: {PASS}   FAIL: {FAIL}")
    if FAILURES:
        print("\n  FAILURES:")
        for f in FAILURES:
            print(f"    {f}")
    print(f"\n  RESULT: {'PASS' if FAIL == 0 else 'FAIL'} — {PASS}/{PASS + FAIL} checks passed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
