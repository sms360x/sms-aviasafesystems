#!/usr/bin/env python
# ============================================================================
# FILE: scripts/migrate_role_claims.py
# PATH: scripts/migrate_role_claims.py
# PURPOSE: 2B.3 — one-shot migration of Firebase Auth custom-claim "role"
#          values from legacy names to the canonical 2B.1 role set.
#
#   Legacy                      -> Canonical
#   CAAN_SMD / CAAN_INSPECTOR / CAAN_ADMIN / CAAN_AUDITOR -> STATE_SMD
#   SAFETY_OFFICER              -> OFFICER
#   AIRLINE_ADMIN               -> TENANT_ADMIN
#   USER / CAMO_USER / QA_USER / SAG_MEMBER -> STAFF
#   CAMO_ADMIN / QA_ADMIN       -> DEPT_ADMIN
#   regulator / auditor         -> STATE_SMD
#
#   `safety` is reported but NEVER auto-changed (it is used as a Safety-Manager
#   alias in the code and needs an SME decision before it is rewritten).
#
# Idempotent: re-running changes 0 users. Safe to run with --dry-run first.
#
# USAGE
#   python scripts/migrate_role_claims.py --dry-run
#   python scripts/migrate_role_claims.py
#
# Uses the existing Firebase Admin initialisation (backend/app/firebase.py);
# no new credentials or configuration.
# ============================================================================

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BACKEND = os.path.join(PROJECT_ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.firebase import get_auth  # noqa: E402

LEGACY_MAP = {
    "CAAN_SMD": "STATE_SMD",
    "SAFETY_OFFICER": "OFFICER",
    "AIRLINE_ADMIN": "TENANT_ADMIN",
    "USER": "STAFF",
    "CAMO_ADMIN": "DEPT_ADMIN",
    "CAMO_USER": "STAFF",
    "QA_ADMIN": "DEPT_ADMIN",
    "QA_USER": "STAFF",
    "CAAN_INSPECTOR": "STATE_SMD",
    "CAAN_ADMIN": "STATE_SMD",
    "CAAN_AUDITOR": "STATE_SMD",
    "SAG_MEMBER": "STAFF",
    # lowercase variants
    "regulator": "STATE_SMD",
    "auditor": "STATE_SMD",
}

CANONICAL_ROLES = {
    "SUPER_ADMIN", "STATE_SMD", "TENANT_ADMIN", "DEPT_ADMIN",
    "OFFICER", "ACCOUNTABLE_EXECUTIVE", "STAFF",
}

# Reported, never auto-rewritten: `safety` is a Safety-Manager alias in code
# and needs a decision before it is changed.
REVIEW_ONLY = {"safety"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change without applying")
    args = parser.parse_args()

    auth = get_auth()
    updated = 0
    pending = 0
    canonical = 0
    review = 0
    unknown = 0

    for user in auth.list_users().iterate_all():
        claims = getattr(user, "custom_claims", None) or {}
        role = claims.get("role")
        if role is None:
            continue
        if role in CANONICAL_ROLES:
            canonical += 1
            continue
        if role in REVIEW_ONLY:
            review += 1
            print(f"REVIEW  uid={user.uid} role={role!r} (not changed; needs a decision)")
            continue
        new_role = LEGACY_MAP.get(role)
        if new_role is None:
            unknown += 1
            print(f"UNKNOWN uid={user.uid} role={role!r} (not in map; not changed)")
            continue

        pending += 1
        if args.dry_run:
            print(f"WOULD  uid={user.uid} {role!r} -> {new_role!r}")
            continue

        merged = dict(claims)
        merged["role"] = new_role
        auth.update_user(user.uid, custom_claims=merged)
        updated += 1
        print(f"UPDATED uid={user.uid} {role!r} -> {new_role!r}")

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(
        f"[{mode}] updated={updated} pending={pending} "
        f"already_canonical={canonical} review={review} unknown={unknown}"
    )
    if args.dry_run:
        print(f"pending_changes={pending}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
