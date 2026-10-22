# ============================================================================
# FILE: audit_view_service.py
# PATH: backend/app/services/audit_view_service.py
# PURPOSE: Read side of the durable audit trail for the SUPER_ADMIN console
#          (Phase 3A.2). STRICTLY READ-ONLY — there is no mutation path here
#          and none is planned: `durable_audit_logs` is append-only (trigger
#          `durable_audit_no_mutate_trg`) and only `append_audit_event`
#          (SECURITY DEFINER) may write to it.
#
#          Integrity model (evaluated server-side, per row):
#            valid    — the stored HMAC recomputes AND the row links to an
#                       existing predecessor in the same tenant chain
#            broken   — the stored HMAC does NOT recompute (payload tampered)
#            unlinked — the predecessor referenced by `prev_hash` is missing
#
#          The HMAC secret never leaves the server: the client receives a
#          verdict, never the key and never a hash it could recompute itself.
#          Actor identity is returned as a stable pseudonymous fingerprint
#          plus the role — no email addresses, no PII reconstruction.
# ============================================================================

from __future__ import annotations

import hashlib
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from loguru import logger

from app.db.ids import tenant_uuid
from app.db.session import is_transient_conn_error, session_scope
from app.services.audit_service import GLOBAL_TENANT_UUID, hmac_key

# ── Payload redaction (viewer-side safety net) ──────────────────────────────
# Write-side redaction (audit_service._redact) already strips PII from the
# anonymous VSR actions. This is the second layer for everything else: an
# operator action may still carry an email address in its metadata, and the
# console must not become a PII distribution channel.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d\s().\-]{6,}\d(?!\w)")
_PII_KEY_TOKENS = ("email", "phone", "ip", "reporter", "passport", "national_id", "contact")

MAX_LIMIT = 200
DEFAULT_LIMIT = 50

# Tenant partition that holds tenantless events (LOGIN, CAAN reads, …).
GLOBAL_TENANT_LABEL = "platform (global)"


def _is_pii_key(key: str) -> bool:
    lowered = str(key).lower()
    return any(token in lowered for token in _PII_KEY_TOKENS)


def redact_payload(value: Any) -> Any:
    """Return a copy of an audit payload with PII-looking values masked."""
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, item in value.items():
            out[key] = "[redacted]" if _is_pii_key(key) else redact_payload(item)
        return out
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, str):
        masked = _EMAIL_RE.sub("[redacted-email]", value)
        masked = _PHONE_RE.sub("[redacted-phone]", masked)
        return masked
    return value


def actor_fingerprint(actor_uid: Optional[str]) -> Optional[str]:
    """Stable pseudonymous id for an actor (12 hex chars of sha256)."""
    if not actor_uid:
        return None
    return hashlib.sha256(str(actor_uid).encode("utf-8")).hexdigest()[:12]


# ── SQL ─────────────────────────────────────────────────────────────────────
# `base` applies the cheap filters; `computed` adds the two integrity
# expressions (HMAC recompute + predecessor lookup); the outer query turns
# them into the verdict and filters on it. The tenant filter is applied first
# so the HMAC pass only covers the partition being inspected.
#
# The HMAC recompute is the expensive part, so the ordinary path paginates
# FIRST and only verifies the rows on the page (the total is a separate cheap
# COUNT). The verdict filter is an explicit forensic query, so it verifies the
# whole filtered set before paginating.
_FILTERS_SQL = """
     WHERE (CAST(:tenant_id AS uuid) IS NULL OR e.tenant_id = CAST(:tenant_id AS uuid))
       AND (CAST(:action AS text) IS NULL OR e.action = CAST(:action AS text))
       AND (CAST(:actor_role AS text) IS NULL OR e.actor_role = CAST(:actor_role AS text))
       AND (CAST(:date_from AS timestamptz) IS NULL OR e.timestamp >= CAST(:date_from AS timestamptz))
       AND (CAST(:date_to AS timestamptz) IS NULL OR e.timestamp <= CAST(:date_to AS timestamptz))
"""

_PAGE_QUERY = """
WITH page AS (
    SELECT e.id, e.timestamp, e.tenant_id, e.action, e.actor_uid, e.actor_role,
           e.resource_type, e.resource_id, e.metadata, e.prev_hash, e.current_hash
      FROM public.durable_audit_logs e
""" + _FILTERS_SQL + """
     ORDER BY e.timestamp DESC, e.id DESC
     LIMIT :limit OFFSET :offset
), counted AS (
    SELECT count(*) AS n FROM public.durable_audit_logs e
""" + _FILTERS_SQL + """
)
SELECT p.id, p.timestamp, p.tenant_id, p.action, p.actor_uid, p.actor_role,
       p.resource_type, p.resource_id, p.metadata, p.prev_hash, p.current_hash,
       CASE WHEN encode(hmac(convert_to(
                coalesce(p.prev_hash, 'GENESIS')
                || coalesce(p.action, '')
                || '|' || coalesce(p.resource_type, '')
                || '|' || coalesce(p.resource_id, '')
                || '|' || coalesce(p.metadata::text, '')
                || '|' || coalesce(p.actor_uid, ''), 'UTF8'),
                convert_to(CAST(:hmac_key AS text), 'UTF8'), 'sha256'), 'hex')
                 IS DISTINCT FROM p.current_hash
            THEN 'broken'
            WHEN p.prev_hash <> 'GENESIS'
                 AND NOT EXISTS (SELECT 1 FROM public.durable_audit_logs q
                                  WHERE q.tenant_id = p.tenant_id
                                    AND q.current_hash = p.prev_hash)
            THEN 'unlinked'
            ELSE 'valid' END AS verification,
       c.n AS total
  FROM page p CROSS JOIN counted c
"""

_COUNT_QUERY = """
SELECT count(*) AS n FROM public.durable_audit_logs e
""" + _FILTERS_SQL

_VERIFIED_QUERY = """
WITH base AS (
    SELECT e.id, e.timestamp, e.tenant_id, e.action, e.actor_uid, e.actor_role,
           e.resource_type, e.resource_id, e.metadata, e.prev_hash, e.current_hash
      FROM public.durable_audit_logs e
""" + _FILTERS_SQL + """
), computed AS (
    SELECT b.*,
           encode(hmac(convert_to(
               coalesce(b.prev_hash, 'GENESIS')
               || coalesce(b.action, '')
               || '|' || coalesce(b.resource_type, '')
               || '|' || coalesce(b.resource_id, '')
               || '|' || coalesce(b.metadata::text, '')
               || '|' || coalesce(b.actor_uid, ''), 'UTF8'),
               convert_to(CAST(:hmac_key AS text), 'UTF8'), 'sha256'), 'hex') AS expected_hash,
           CASE WHEN b.prev_hash = 'GENESIS' THEN TRUE
                ELSE EXISTS (SELECT 1 FROM public.durable_audit_logs p
                              WHERE p.tenant_id = b.tenant_id
                                AND p.current_hash = b.prev_hash)
           END AS link_ok
      FROM base b
)
SELECT id, timestamp, tenant_id, action, actor_uid, actor_role, resource_type,
       resource_id, metadata, prev_hash, current_hash,
       CASE WHEN expected_hash IS DISTINCT FROM current_hash THEN 'broken'
            WHEN link_ok = FALSE THEN 'unlinked'
            ELSE 'valid' END AS verification,
       COUNT(*) OVER () AS total
  FROM computed
 WHERE (CAST(:verification AS text) IS NULL
        OR (CAST(:verification AS text) = 'broken' AND expected_hash IS DISTINCT FROM current_hash)
        OR (CAST(:verification AS text) = 'unlinked' AND link_ok = FALSE AND expected_hash = current_hash)
        OR (CAST(:verification AS text) = 'valid' AND link_ok = TRUE AND expected_hash = current_hash))
 ORDER BY timestamp DESC, id DESC
 LIMIT :limit OFFSET :offset
"""

_TENANT_CHAINS_QUERY = """
WITH per_tenant AS (
    SELECT tenant_id,
           count(*) AS events,
           min(timestamp) AS first_event_at,
           max(timestamp) AS last_event_at,
           count(*) FILTER (WHERE prev_hash = 'GENESIS') AS chain_segments
      FROM public.durable_audit_logs
     GROUP BY tenant_id
), forks AS (
    SELECT tenant_id, count(*) AS forked_links
      FROM (SELECT tenant_id, prev_hash
              FROM public.durable_audit_logs
             GROUP BY tenant_id, prev_hash
            HAVING count(*) > 1) f
     GROUP BY tenant_id
), dangling AS (
    SELECT d.tenant_id, count(*) AS dangling_links
      FROM public.durable_audit_logs d
     WHERE d.prev_hash <> 'GENESIS'
       AND NOT EXISTS (SELECT 1 FROM public.durable_audit_logs p
                        WHERE p.tenant_id = d.tenant_id
                          AND p.current_hash = d.prev_hash)
     GROUP BY d.tenant_id
)
SELECT t.tenant_id, t.events, t.first_event_at, t.last_event_at,
       t.chain_segments,
       coalesce(f.forked_links, 0) AS forked_links,
       coalesce(d.dangling_links, 0) AS dangling_links
  FROM per_tenant t
  LEFT JOIN forks f ON f.tenant_id = t.tenant_id
  LEFT JOIN dangling d ON d.tenant_id = t.tenant_id
 ORDER BY t.events DESC, t.tenant_id
"""


def _is_transient(exc: Exception) -> bool:
    """True for a connection stall / drop that a read may safely retry."""
    if isinstance(exc, TimeoutError):
        return True
    return is_transient_conn_error(exc)


async def _fetch(query: str, params: Dict[str, Any]):
    """Run a read-only query, retrying once on a transient connection stall.

    Every query in this module is read-only, so a retry can never duplicate a
    write. The retry matters under load: the pooled connection can stall
    behind the remote pooler, which would otherwise surface as a 500 on a
    page load that has not changed anything.
    """
    for attempt in range(2):
        try:
            async with session_scope() as session:
                result = await session.execute(text(query), params)
                return result.fetchall()
        except Exception as exc:  # noqa: BLE001 - re-raised unless transient
            if attempt == 0 and _is_transient(exc):
                logger.warning(
                    "Audit view query stalled ({}) — retrying once", exc
                )
                continue
            raise


async def _fetch_one(query: str, params: Dict[str, Any]):
    rows = await _fetch(query, params)
    return rows[0] if rows else None


def _resolve_tenant_uuid(tenant_slug: Optional[str]) -> Optional[str]:
    """Map a tenant slug to its deterministic partition uuid."""
    if not tenant_slug:
        return None
    slug = str(tenant_slug).strip()
    if not slug:
        return None
    if slug == "__global__":
        return GLOBAL_TENANT_UUID
    return tenant_uuid(slug)


# Tenant labels are read through a SECURITY DEFINER view; they change rarely
# (a tenant is created or renamed), so they are cached briefly to keep the
# console's page load to a single database round trip.
_LABEL_CACHE: Dict[str, Dict[str, Optional[str]]] = {}
_LABEL_CACHE_TS: float = 0.0
_LABEL_CACHE_TTL: float = 60.0


async def _tenant_labels(force: bool = False) -> Dict[str, Dict[str, Optional[str]]]:
    """uuid -> {slug, name} map for every tenant (definer read view)."""
    global _LABEL_CACHE, _LABEL_CACHE_TS

    now = time.monotonic()
    if (
        not force
        and _LABEL_CACHE
        and (now - _LABEL_CACHE_TS) < _LABEL_CACHE_TTL
    ):
        return _LABEL_CACHE

    rows = await _fetch(
        "SELECT tenant_uuid, slug, name FROM public.admin_tenant_view()", {}
    )
    labels = {
        str(row[0]): {"slug": row[1], "name": row[2]}
        for row in rows
    }

    _LABEL_CACHE = labels
    _LABEL_CACHE_TS = now
    return labels


async def _labels_for(tenant_ids) -> Dict[str, Dict[str, Optional[str]]]:
    """Labels for the given partitions, refreshing once if any is unknown.

    A tenant row is created by another process (registration, provisioning),
    so a cached label map can be a moment behind. If a partition we can see is
    missing from the cache, refresh once rather than showing the row as an
    "unknown tenant".
    """
    wanted = {
        str(t) for t in tenant_ids
        if t and str(t) != GLOBAL_TENANT_UUID
    }
    labels = await _tenant_labels()
    if wanted and not wanted.issubset(set(labels.keys())):
        labels = await _tenant_labels(force=True)
    return labels


def _label(tenant_uuid_value: str, labels: Dict[str, Dict[str, Optional[str]]]) -> Dict[str, Optional[str]]:
    info = labels.get(str(tenant_uuid_value))
    if info:
        return {
            "tenant_slug": info.get("slug"),
            "tenant_name": info.get("name"),
            "tenant_label": info.get("slug"),
        }
    if str(tenant_uuid_value) == GLOBAL_TENANT_UUID:
        return {
            "tenant_slug": "__global__",
            "tenant_name": GLOBAL_TENANT_LABEL,
            "tenant_label": GLOBAL_TENANT_LABEL,
        }
    # The partition belongs to a tenant that no longer exists (or predates the
    # tenants table). The row is still shown — labelled by its partition id.
    return {
        "tenant_slug": None,
        "tenant_name": None,
        "tenant_label": f"unknown tenant {str(tenant_uuid_value)[:8]}",
    }


def _event_row(row, labels) -> Dict[str, Any]:
    (event_id, timestamp, tenant_id, action, actor_uid, actor_role,
     resource_type, resource_id, metadata, prev_hash, current_hash,
     verification) = row[:12]
    event = {
        "id": str(event_id),
        "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
        "tenant_id": str(tenant_id),
        "action": action,
        "actor_role": actor_role,
        "actor_present": bool(actor_uid),
        "actor_fingerprint": actor_fingerprint(actor_uid),
        "resource_type": resource_type,
        "resource_id": resource_id,
        "payload": redact_payload(metadata or {}),
        "prev_hash": prev_hash,
        "current_hash": current_hash,
        "verification": verification,
    }
    event.update(_label(str(tenant_id), labels))
    return event


async def list_events(
    *,
    tenant_slug: Optional[str] = None,
    action: Optional[str] = None,
    actor_role: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    verification: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> Dict[str, Any]:
    """Return a filtered, paginated page of durable audit events."""
    limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    offset = max(0, int(offset or 0))
    if verification in ("", "all"):
        verification = None
    if verification is not None and verification not in ("valid", "broken", "unlinked"):
        raise ValueError(f"unsupported verification filter: {verification}")

    params = {
        "tenant_id": _resolve_tenant_uuid(tenant_slug),
        "action": action or None,
        "actor_role": actor_role or None,
        "date_from": date_from or None,
        "date_to": date_to or None,
        "verification": verification,
        "hmac_key": hmac_key(),
        "limit": limit,
        "offset": offset,
    }

    if verification is None:
        # Ordinary path: paginate first, verify only the rows on the page.
        rows = await _fetch(_PAGE_QUERY, params)
        total = int(rows[0][12] or 0) if rows else 0
        if not rows and offset:
            # The page is empty but the filtered set may not be — report the
            # real total so the pager does not jump back to zero.
            counted = await _fetch(_COUNT_QUERY, params)
            total = int(counted[0][0] or 0) if counted else 0
    else:
        # Forensic path: the verdict filter needs the integrity of the whole
        # filtered set before it can be applied.
        rows = await _fetch(_VERIFIED_QUERY, params)
        total = int(rows[0][12] or 0) if rows else 0

    labels = await _labels_for([row[2] for row in rows])

    return {
        "events": [_event_row(row, labels) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def get_event(event_id: str) -> Optional[Dict[str, Any]]:
    """Return one event with its chain neighbours (read-only)."""
    row = await _fetch_one(
        """
        SELECT e.id, e.timestamp, e.tenant_id, e.action, e.actor_uid, e.actor_role,
               e.resource_type, e.resource_id, e.metadata, e.prev_hash, e.current_hash,
               encode(hmac(convert_to(
                   coalesce(e.prev_hash, 'GENESIS')
                   || coalesce(e.action, '')
                   || '|' || coalesce(e.resource_type, '')
                   || '|' || coalesce(e.resource_id, '')
                   || '|' || coalesce(e.metadata::text, '')
                   || '|' || coalesce(e.actor_uid, ''), 'UTF8'),
                   convert_to(CAST(:hmac_key AS text), 'UTF8'), 'sha256'), 'hex') AS expected_hash,
               (SELECT p.id FROM public.durable_audit_logs p
                 WHERE p.tenant_id = e.tenant_id AND p.current_hash = e.prev_hash
                 LIMIT 1) AS predecessor_id,
               (SELECT count(*) FROM public.durable_audit_logs s
                 WHERE s.tenant_id = e.tenant_id AND s.prev_hash = e.current_hash) AS successor_count
          FROM public.durable_audit_logs e
         WHERE e.id = CAST(:event_id AS uuid)
        """,
        {"event_id": event_id, "hmac_key": hmac_key()},
    )
    if row is None:
        return None

    (eid, timestamp, tenant_id, action, actor_uid, actor_role, resource_type,
     resource_id, metadata, prev_hash, current_hash, expected_hash,
     predecessor_id, successor_count) = row

    labels = await _labels_for([tenant_id])

    verification = "valid"
    if expected_hash != current_hash:
        verification = "broken"
    elif predecessor_id is None and prev_hash != "GENESIS":
        verification = "unlinked"

    event = {
        "id": str(eid),
        "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
        "tenant_id": str(tenant_id),
        "action": action,
        "actor_role": actor_role,
        "actor_present": bool(actor_uid),
        "actor_fingerprint": actor_fingerprint(actor_uid),
        "resource_type": resource_type,
        "resource_id": resource_id,
        "payload": redact_payload(metadata or {}),
        "prev_hash": prev_hash,
        "current_hash": current_hash,
        "verification": verification,
        "chain": {
            "predecessor_id": str(predecessor_id) if predecessor_id else None,
            "successor_count": int(successor_count or 0),
        },
    }
    event.update(_label(str(tenant_id), labels))
    return event


async def tenant_chains() -> List[Dict[str, Any]]:
    """Per-tenant chain summary: volume, segments and structural breaks."""
    rows = await _fetch(_TENANT_CHAINS_QUERY, {})

    labels = await _labels_for([row[0] for row in rows])

    out: List[Dict[str, Any]] = []
    for (tenant_id, events, first_at, last_at, segments, forked, dangling) in rows:
        entry: Dict[str, Any] = {
            "tenant_id": str(tenant_id),
            "events": int(events),
            "first_event_at": first_at.isoformat() if hasattr(first_at, "isoformat") else None,
            "last_event_at": last_at.isoformat() if hasattr(last_at, "isoformat") else None,
            "chain_segments": int(segments),
            "forked_links": int(forked),
            "dangling_links": int(dangling),
        }
        entry.update(_label(str(tenant_id), labels))
        if entry.get("tenant_slug") is None and str(tenant_id) == GLOBAL_TENANT_UUID:
            entry["tenant_slug"] = "__global__"
            entry["tenant_name"] = GLOBAL_TENANT_LABEL
        breaks = int(forked) + int(dangling)
        entry["status"] = "valid" if breaks == 0 else "broken"
        entry["status_detail"] = (
            "chain intact" if breaks == 0
            else f"{int(forked)} forked link(s), {int(dangling)} dangling link(s)"
        )
        out.append(entry)
    return out


def summarize_events(events: List[Dict[str, Any]]) -> Tuple[int, int, int]:
    """(valid, broken, unlinked) counts for a page of events."""
    valid = sum(1 for e in events if e.get("verification") == "valid")
    broken = sum(1 for e in events if e.get("verification") == "broken")
    unlinked = sum(1 for e in events if e.get("verification") == "unlinked")
    return valid, broken, unlinked
