# ============================================================================
# Shared auth-dependency override helper for tests (2A.4-pre).
#
# After 2A.4, the auth boundary (resolve_user_context) reads role/tenant from
# the memberships table, so tests must install the authenticated user via the
# `get_current_user` dependency override rather than by mocking the Firebase
# token (a mocked token no longer yields a role). Most tests already override
# `get_current_user`; this helper makes that explicit and uniform.
# ============================================================================

from typing import Any, Callable, Dict, Optional, Union

from app.main import app
from app.middleware.auth import get_current_user


def make_user_dict(uid: str = "test-uid", email: str = "test@example.com",
                   role: str = "TENANT_ADMIN", tenant_id: Optional[str] = "sita-air",
                   department: Optional[str] = "Safety",
                   is_developer: bool = False) -> Dict[str, Any]:
    return {
        "uid": uid,
        "email": email,
        "role": role,
        "tenant_id": tenant_id,
        "department": department,
        "is_developer": is_developer,
        "claims": {"role": role, "tenant_id": tenant_id, "department": department},
    }


def use_user(user_or_fn: Union[Dict[str, Any], Callable[[], Dict[str, Any]]]):
    """Install a get_current_user override (a fixed dict or a zero-arg callable)."""
    app.dependency_overrides[get_current_user] = (
        user_or_fn if callable(user_or_fn) else (lambda: user_or_fn)
    )


def clear_user():
    app.dependency_overrides.pop(get_current_user, None)
