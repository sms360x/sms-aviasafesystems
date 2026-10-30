# ============================================================================
# FILE: user_context_cache.py
# PATH: backend/app/middleware/user_context_cache.py
# PURPOSE: Short-TTL in-memory cache for the per-request auth identity
#          resolution, consumed by auth.resolve_user_context().
#
#          Before this cache, EVERY authenticated request paid two Postgres
#          round-trips before any route logic ran: `users` by email, then
#          `tenants` by id (to map the users-row tenant uuid to its slug).
#          Together with the tenant-status lookup that made auth the dominant
#          constant on every endpoint. The cache collapses that to one pair of
#          queries per TTL window per user.
#
#          Key:   normalised email (the users-row lookup key).
#          Value: {"role", "tenant_id", "department"?}.
#
#          Semantics:
#          - A cache miss falls back to the DB and populates the entry.
#          - Negative results (no users row) are NEVER cached, so a freshly
#            provisioned user is not locked out for a TTL window.
#          - Returned dicts are copies; callers cannot mutate cached state.
#          - Writes that change a user's role/tenant/department invalidate the
#            entry immediately (services.users.upsert_user_doc and admin user
#            deletion). The TTL (AVIASAFE_USER_CONTEXT_CACHE_TTL_SECONDS,
#            default 300s) bounds staleness only for changes made in another
#            process (the cache is per-process; Render runs a single uvicorn
#            worker). Set the TTL to 0 to disable caching entirely.
# ============================================================================

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Optional, Tuple

_TTL_SECONDS = float(os.getenv("AVIASAFE_USER_CONTEXT_CACHE_TTL_SECONDS", "300"))
_MAX_ENTRIES = int(os.getenv("AVIASAFE_USER_CONTEXT_CACHE_MAX_ENTRIES", "5000"))

# email -> (context, expires_at_monotonic)
_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
_lock = threading.Lock()


def _now() -> float:
    return time.monotonic()


def _norm(email: Optional[str]) -> str:
    return (email or "").strip().lower()


def _purge_expired_locked() -> None:
    now = _now()
    for key in [k for k, (_, exp) in _cache.items() if now > exp]:
        _cache.pop(key, None)


def get_cached_context(email: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return a copy of the cached context, or None on miss/expiry/disabled."""
    if _TTL_SECONDS <= 0:
        return None
    key = _norm(email)
    if not key:
        return None
    with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        ctx, expires = entry
        if _now() > expires:
            _cache.pop(key, None)
            return None
        return dict(ctx)


def set_cached_context(email: Optional[str], ctx: Dict[str, Any]) -> None:
    """Store a resolved context for the TTL window (no-op when disabled)."""
    if _TTL_SECONDS <= 0:
        return
    key = _norm(email)
    if not key or ctx is None:
        return
    with _lock:
        if key not in _cache and len(_cache) >= _MAX_ENTRIES:
            _purge_expired_locked()
            if len(_cache) >= _MAX_ENTRIES:
                # Still full: drop the entry that expires soonest.
                oldest = min(_cache, key=lambda k: _cache[k][1])
                _cache.pop(oldest, None)
        _cache[key] = (dict(ctx), _now() + _TTL_SECONDS)


def invalidate_cached_context(email: Optional[str]) -> None:
    """Drop a user's cached context so the next request re-reads the DB."""
    key = _norm(email)
    if not key:
        return
    with _lock:
        _cache.pop(key, None)


def invalidate_all() -> None:
    """Drop every cached context (tests, tenant-wide migrations)."""
    with _lock:
        _cache.clear()
