# ============================================================================
# FILE: setup_key.py
# PATH: backend/app/services/setup_key.py
# PURPOSE: Shared second factor for admin provisioning endpoints (RC-1).
#
#          The setup key is a defense-in-depth secret loaded from the
#          environment (SETUP_SECRET). It never grants access by itself —
#          callers must also present a SUPER_ADMIN Firebase ID token
#          (enforced by the `get_admin_user` dependency).
#
#          Extracted from app/routes/admin.py so other SUPER_ADMIN surfaces
#          (e.g. the Phase 3A.2 System Configs console) use exactly the same
#          check instead of re-implementing it.
# ============================================================================

import secrets

from fastapi import HTTPException, status

from app.core.config import settings


def verify_setup_key(setup_key: str) -> None:
    """Second factor for admin provisioning endpoints.

    Raises 503 when the server has no setup secret configured and 403 when the
    supplied key does not match.
    """
    if not settings.SETUP_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin setup is not configured on this server",
        )
    if not setup_key or not secrets.compare_digest(setup_key, settings.SETUP_SECRET):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid setup key")
