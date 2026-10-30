# ============================================================================
# FILE: demo_fallback.py
# PATH: backend/app/services/demo_fallback.py
# PURPOSE: Spec #6 - global demo-data fallback for empty tenant dashboards.
#
#          A newly onboarded tenant owns no reports, so its dashboard would be
#          empty. Tenant-scoped READ paths therefore resolve an "effective read
#          tenant": the caller's own tenant when it owns at least one report in
#          the current write scope, otherwise the configured global demo tenant
#          (GLOBAL_DEMO_TENANT_ID, default "sita-air" - the seeded pilot data).
#
#          Once the tenant creates its first report the probe turns true and
#          the fallback closes permanently (1 real report > demo data).
#
#          READ-ONLY BY CONSTRUCTION. Nothing here is imported by a write path:
#          create/update/delete always resolve the authenticated tenant
#          (ReportService.tenant_id / register_tenant) so a tenant account can
#          never edit or delete the global demo rows.
#
#          The "does this tenant own any report?" probe runs at most once per
#          GLOBAL_DEMO_FALLBACK_TTL_SECONDS per tenant. Report creation calls
#          invalidate() immediately, so the first real report is visible without
#          waiting out the TTL. Only tenant-scoped reads that returned zero rows
#          ever probe, so tenants with data pay no extra query.
# ============================================================================

from __future__ import annotations

import threading
import time
from typing import Dict, Optional, Tuple

from loguru import logger

from app.core.config import settings
from app.db import pg
from app.db.db_models import Report
from app.db.ids import tenant_uuid
from app.db.isolation import demo_scope

_TTL_SECONDS = float(
    getattr(settings, "GLOBAL_DEMO_FALLBACK_TTL_SECONDS", 60) or 0
)

# slug -> (has_any_report, expires_at_monotonic)
_has_reports: Dict[str, Tuple[bool, float]] = {}
_lock = threading.Lock()


def demo_tenant_slug() -> Optional[str]:
    """The configured global demo tenant slug (None when unset)."""
    slug = (getattr(settings, "GLOBAL_DEMO_TENANT_ID", None) or "").strip().lower()
    return slug or None


def _enabled() -> bool:
    return bool(getattr(settings, "GLOBAL_DEMO_FALLBACK_ENABLED", False))


def _norm(slug: Optional[str]) -> str:
    return (slug or "").strip().lower()


def tenant_has_reports(tenant_slug: str) -> bool:
    """True when the tenant owns >= 1 report in the current write scope.

    Uses a LIMIT 1 existence probe (not a COUNT) and caches the answer for a
    short TTL. On a probe error the answer fails closed (treated as "has
    reports") so a database hiccup never silently swaps data sources.
    """
    slug = _norm(tenant_slug)
    if not slug:
        return False

    now = time.monotonic()
    with _lock:
        entry = _has_reports.get(slug)
        if entry is not None and now <= entry[1]:
            return entry[0]

    try:
        rows = pg.fetch_all(
            Report,
            where=[
                Report.tenant_id == tenant_uuid(slug),
                Report.is_demo == demo_scope(),
            ],
            limit=1,
        )
        has_reports = bool(rows)
    except Exception as exc:
        logger.warning(
            f"Demo-fallback probe failed for tenant {slug}: {exc} "
            "(failing closed: no demo fallback)"
        )
        return True

    with _lock:
        _has_reports[slug] = (has_reports, now + _TTL_SECONDS)
    return has_reports


def fallback_tenant_for(tenant_slug: Optional[str]) -> Optional[str]:
    """Return the demo tenant slug to read instead of `tenant_slug`, or None.

    None means "read the caller's own tenant": the fallback is disabled, the
    caller already is the demo tenant, or the caller owns at least one report.
    """
    slug = _norm(tenant_slug)
    demo = demo_tenant_slug()
    if not _enabled() or not slug or not demo or slug == demo:
        return None
    if tenant_has_reports(slug):
        return None
    return demo


def resolve_read_tenant(tenant_slug: Optional[str]) -> Tuple[Optional[str], bool]:
    """Resolve the tenant a read should use: (effective_slug, used_fallback)."""
    demo = fallback_tenant_for(tenant_slug)
    if demo:
        return demo, True
    return tenant_slug, False


def invalidate(tenant_slug: Optional[str] = None) -> None:
    """Drop the cached probe for one tenant (or every tenant when None).

    Called by ReportService.create_report so a tenant's first real report
    closes the fallback on the very next request.
    """
    if tenant_slug is None:
        with _lock:
            _has_reports.clear()
        return
    key = _norm(tenant_slug)
    if not key:
        return
    with _lock:
        _has_reports.pop(key, None)
