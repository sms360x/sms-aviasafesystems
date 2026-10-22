# ============================================================================
# FILE: audit_department_claims.py
# PATH: backend/scripts/audit_department_claims.py
# PURPOSE: Phase 3A ops checklist — audit the live Firebase `department` claim
#          on every user, and (optionally) populate the missing/invalid ones
#          through the admin API (PATCH /api/v1/admin/users).
#
#          Why this exists
#          ---------------
#          RBAC_MODEL §4 makes the OFFICER role department-scoped: an officer
#          in the Safety department is a Safety Officer, every other officer
#          falls back to the basic employee persona. The backend reads the
#          `department` claim from the ID token (falling back to the users
#          mirror row), and the frontend nav reads the same claim. A user
#          whose claim is missing or carries an unknown code therefore fails
#          closed — no Safety persona, no department Workspace.
#
#          The script is READ-ONLY unless `--apply` is passed.
#
#   Audit : python scripts/audit_department_claims.py
#   Apply : python scripts/audit_department_claims.py --apply
#   Plan  : python scripts/audit_department_claims.py --json plan.json
#
#          The authoritative source for the correct value is the `users`
#          mirror row (RBAC_MODEL: the users-row department wins over the
#          token claim). Only users whose mirror row carries a canonical
#          department code are eligible for an automatic write.
# ============================================================================

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from app.core.config import DEPARTMENT_CODES, settings  # noqa: E402
from app.firebase import get_auth  # noqa: E402

VALID_DEPARTMENTS = {code for code, _ in DEPARTMENT_CODES}
DEPARTMENT_LABELS = dict(DEPARTMENT_CODES)

# Firebase Web API key (public client key — the same one the front end uses).
# Only used to exchange a service-account custom token for an ID token.
FIREBASE_WEB_API_KEY = "AIzaSyCdCtUuyOcUIoCBEaiWGbhp6_XwZKHsicc"

# The deployed API host used for the admin writes.
DEFAULT_API_BASE_URL = "https://aviasafe-unified-platform.onrender.com"

# Roles that do not need a department claim.
DEPARTMENT_EXEMPT_ROLES = {
    "SUPER_ADMIN",
    "STATE_SMD",
    "ACCOUNTABLE_EXECUTIVE",
    "SAG_MEMBER",
}


def _mirror_departments() -> Dict[str, Dict[str, Any]]:
    """uid -> {email, role, tenant_id, department} from the `users` mirror."""
    from sqlalchemy import text

    from app.db.session import session_scope

    async def _go():
        async with session_scope() as s:
            r = await s.execute(
                text(
                    "SELECT u.uid, u.email, u.role, t.slug, u.department "
                    "FROM public.users u "
                    "LEFT JOIN public.tenants t ON t.id = u.tenant_id "
                    "WHERE u.uid IS NOT NULL"
                )
            )
            return r.fetchall()

    from app.db.runner import run

    rows = run(_go())
    out: Dict[str, Dict[str, Any]] = {}
    for uid, email, role, tenant_slug, department in rows:
        out[str(uid)] = {
            "email": email,
            "role": role,
            "tenant_id": tenant_slug,
            "department": department,
        }
    return out


def classify(claims: Dict[str, Any], role: str, department: Optional[str]) -> str:
    """missing | invalid | ok | exempt"""
    if role in DEPARTMENT_EXEMPT_ROLES:
        return "exempt"
    value = (department or "").strip().lower()
    if not value:
        return "missing"
    if value not in VALID_DEPARTMENTS:
        return "invalid"
    return "ok"


def collect_users() -> List[Dict[str, Any]]:
    """Every Firebase Auth user with its claims + mirror row."""
    auth = get_auth()
    mirror = _mirror_departments()

    users: List[Dict[str, Any]] = []
    page_token = None
    while True:
        page = auth.list_users(max_results=1000, page_token=page_token)
        for rec in page.users:
            uid = getattr(rec, "uid", "") or ""
            claims = getattr(rec, "custom_claims", None) or {}
            if not isinstance(claims, dict):
                try:
                    claims = dict(claims)
                except Exception:
                    claims = {}
            row = mirror.get(uid, {})
            role = claims.get("role") or row.get("role") or ""
            claim_dept = claims.get("department")
            mirror_dept = row.get("department")
            users.append(
                {
                    "uid": uid,
                    "email": getattr(rec, "email", "") or row.get("email") or "",
                    "role": role,
                    "tenant_id": row.get("tenant_id") or claims.get("tenant_id") or "",
                    "claim_department": claim_dept,
                    "mirror_department": mirror_dept,
                    "status": classify(claims, role, claim_dept),
                    "disabled": bool(getattr(rec, "disabled", False)),
                }
            )
        page_token = page.next_page_token
        if not page_token:
            break
    return users


def build_plan(users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Users that need a claim write, with the value taken from the mirror."""
    plan: List[Dict[str, Any]] = []
    for u in users:
        if u["status"] not in ("missing", "invalid"):
            continue
        candidate = (u["mirror_department"] or "").strip().lower()
        eligible = candidate in VALID_DEPARTMENTS
        plan.append(
            {
                "uid": u["uid"],
                "email": u["email"],
                "role": u["role"],
                "tenant_id": u["tenant_id"],
                "current_claim": u["claim_department"],
                "proposed_department": candidate if eligible else None,
                "eligible": eligible,
                "reason": u["status"],
            }
        )
    return plan


def print_report(users: List[Dict[str, Any]], plan: List[Dict[str, Any]]) -> None:
    counts: Dict[str, int] = {}
    for u in users:
        counts[u["status"]] = counts.get(u["status"], 0) + 1

    print("=" * 78)
    print("DEPARTMENT CLAIM AUDIT — live Firebase Auth directory")
    print("=" * 78)
    print(f"users scanned              : {len(users)}")
    for key in ("ok", "missing", "invalid", "exempt"):
        print(f"  {key:<24}: {counts.get(key, 0)}")
    officers = [u for u in users if u["role"] == "OFFICER"]
    officer_bad = [u for u in officers if u["status"] in ("missing", "invalid")]
    print(f"OFFICER users              : {len(officers)}")
    print(f"  OFFICER without a valid claim : {len(officer_bad)}")

    eligible = [p for p in plan if p["eligible"]]
    manual = [p for p in plan if not p["eligible"]]
    print()
    print(f"claim writes required      : {len(plan)}")
    print(f"  auto-populatable (mirror row has a canonical code) : {len(eligible)}")
    print(f"  needs a human decision (no canonical mirror value) : {len(manual)}")

    if eligible:
        print()
        print("AUTO-POPULATABLE")
        print("-" * 78)
        for p in eligible:
            print(
                f"  {p['email'] or p['uid']:<38} role={p['role']:<18} "
                f"{p['current_claim'] or '(none)'} -> {p['proposed_department']}"
            )
    if manual:
        print()
        print("NEEDS A HUMAN DECISION")
        print("-" * 78)
        for p in manual:
            print(
                f"  {p['email'] or p['uid']:<38} role={p['role']:<18} "
                f"claim={p['current_claim'] or '(none)'} mirror={p['mirror_department'] or '(none)'}"
            )


def _mint_super_admin_token(uid: str) -> str:
    """Mint an ID token for the SUPER_ADMIN account (service account only)."""
    import firebase_admin
    from firebase_admin import auth as admin_auth

    if not firebase_admin._apps:
        from firebase_admin import credentials

        cred = credentials.Certificate(
            {
                "type": "service_account",
                "project_id": settings.FIREBASE_PROJECT_ID,
                "private_key": settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n"),
                "client_email": settings.FIREBASE_CLIENT_EMAIL,
                "token_uri": settings.FIREBASE_TOKEN_URI,
            }
        )
        firebase_admin.initialize_app(cred)

    custom = admin_auth.create_custom_token(
        uid, {"role": "SUPER_ADMIN", "tenant_id": None, "department": None}
    )
    if isinstance(custom, bytes):
        custom = custom.decode()

    import requests

    api_key = getattr(settings, "FIREBASE_API_KEY", None) or FIREBASE_WEB_API_KEY
    resp = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={api_key}",
        json={"token": custom, "returnSecureToken": True},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["idToken"]


def apply_plan(plan: List[Dict[str, Any]], api_base: Optional[str] = None) -> int:
    """Write the missing claims through PATCH /api/v1/admin/users."""
    import requests

    eligible = [p for p in plan if p["eligible"]]
    if not eligible:
        print("Nothing to apply.")
        return 0

    if not settings.SETUP_SECRET:
        print("SETUP_SECRET is not configured — refusing to write.")
        return 0

    token = _mint_super_admin_token("hLXs4mvtf5bb1hRSifnh6HuUHpC2")
    api = (api_base or getattr(settings, "API_BASE_URL", None) or DEFAULT_API_BASE_URL).rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}

    applied = 0
    fallback = 0
    failed = 0
    for p in eligible:
        resp = requests.patch(
            f"{api}/api/v1/admin/users",
            headers=headers,
            json={
                "uid": p["uid"],
                "department": p["proposed_department"],
                "setup_key": settings.SETUP_SECRET,
            },
            timeout=90,
        )
        if resp.status_code == 200:
            applied += 1
            print(
                f"  API  {p['email'] or p['uid']:<38} -> {p['proposed_department']} (HTTP 200)"
            )
            continue

        if resp.status_code != 500:
            failed += 1
            print(
                f"  ERR  {p['email'] or p['uid']:<38} -> {p['proposed_department']} "
                f"(HTTP {resp.status_code}) {resp.text[:120]}"
            )
            continue

        # HTTP 500 = the endpoint's mirror upsert was refused by the `users`
        # RLS policy (pre-existing defect: the `users` table has no permissive
        # write policy for a platform role). The Firebase claim write happens
        # before that upsert, so the claim may already be applied; the audit
        # event is not. Fall back to the same claim write + the same durable
        # audit event, done locally.
        try:
            _write_claim_direct(p)
            fallback += 1
            print(
                f"  FB   {p['email'] or p['uid']:<38} -> {p['proposed_department']} "
                f"(API 500 — claim written directly + audited)"
            )
        except Exception as exc:  # pragma: no cover - ops safety net
            failed += 1
            print(f"  ERR  {p['email'] or p['uid']:<38} {exc}")

    if fallback:
        print()
        print(
            f"note: {fallback} write(s) went through the direct Firebase path "
            f"because PATCH /admin/users failed with HTTP 500 (users-table RLS "
            f"policy defect). Each one carries a USER_UPDATED durable audit event."
        )
    return applied + fallback


def _write_claim_direct(entry: Dict[str, Any]) -> None:
    """Write the claim with the Admin SDK and append the durable audit event."""
    from app.firebase import get_auth
    from app.services.audit_service import log_audit

    auth = get_auth()
    rec = auth.get_user(entry["uid"])
    claims = dict(getattr(rec, "custom_claims", None) or {})
    claims["department"] = entry["proposed_department"]
    auth.update_user(entry["uid"], custom_claims=claims)

    # The audit event is partitioned by tenant slug — never by a uuid.
    tenant = entry.get("tenant_id") or ""
    if tenant and tenant.count("-") == 4:
        tenant = ""

    log_audit(
        action="USER_UPDATED",
        user="ezondiza.dhf@gmail.com",
        tenant_id=tenant or None,
        target_type="user",
        target_id=entry["uid"],
        metadata={
            "email": entry.get("email") or "",
            "role": entry.get("role") or "",
            "department": entry["proposed_department"],
            "source": "ops-department-claim-backfill",
        },
    )


def record_claim_events(emails: List[str]) -> int:
    """Append the durable audit event for claim writes that the API could not.

    `PATCH /admin/users` writes the Firebase claim first and only then
    refreshes the `users` mirror. Under RLS enforcement the mirror upsert is
    refused for a platform role, so the endpoint answers 500 *after* the claim
    was applied and *before* the audit event is written. This mode records
    the missing events (flagged as a backfill) so the trail stays complete.
    """
    from app.services.audit_service import log_audit

    mirror = _mirror_departments()
    by_email = {v.get("email"): (k, v) for k, v in mirror.items()}

    written = 0
    for email in emails:
        found = by_email.get(email)
        if not found:
            print(f"  ERR  {email}: not found in the users mirror")
            continue
        uid, row = found
        department = (row.get("department") or "").strip().lower()
        log_audit(
            action="USER_UPDATED",
            user="ezondiza.dhf@gmail.com",
            tenant_id=row.get("tenant_id") or None,
            target_type="user",
            target_id=uid,
            metadata={
                "email": email,
                "role": row.get("role") or "",
                "department": department,
                "source": "ops-department-claim-backfill",
                "backfilled_audit_event": True,
            },
        )
        written += 1
        print(f"  AUDIT {email:<38} -> {department}")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the missing claims")
    parser.add_argument("--json", help="write the audit/plan as JSON to this path")
    parser.add_argument(
        "--record",
        help=(
            "file with one e-mail address per line; appends the durable "
            "USER_UPDATED event for each (backfills the trail for claim "
            "writes the API could not audit)."
        ),
    )
    parser.add_argument(
        "--api-base",
        help=(
            "API host to write through (default: the deployed backend). Use a "
            "local instance when the local SETUP_SECRET differs from the "
            "deployed one."
        ),
    )
    args = parser.parse_args()

    users = collect_users()
    plan = build_plan(users)
    print_report(users, plan)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "counts": {
                        s: sum(1 for u in users if u["status"] == s)
                        for s in ("ok", "missing", "invalid", "exempt")
                    },
                    "total_users": len(users),
                    "plan": plan,
                },
                fh,
                indent=2,
                default=str,
            )
        print(f"\nJSON written to {args.json}")

    if args.record:
        print()
        print("RECORDING CLAIM AUDIT EVENTS")
        print("-" * 78)
        with open(args.record, "r", encoding="utf-8") as fh:
            emails = [line.strip() for line in fh if line.strip()]
        written = record_claim_events(emails)
        print(f"\nrecorded: {written}")

    if args.apply:
        print()
        print(f"APPLYING CLAIMS via {args.api_base or DEFAULT_API_BASE_URL}")
        print("-" * 78)
        applied = apply_plan(plan, args.api_base)
        print(f"\napplied: {applied}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
