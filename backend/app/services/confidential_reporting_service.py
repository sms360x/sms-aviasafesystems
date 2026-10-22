# ============================================================================
# FILE: confidential_reporting_service.py
# PATH: backend/app/services/confidential_reporting_service.py
# PURPOSE: Module C §5.2.4 (DP-4, P2-25) — confidential / voluntary reporting
#          class. Adds a confidentiality flag + designated custodian to a
#          Module B report; reporter identity is visible ONLY to the custodian
#          (Appendix 3 protection) and downstream consumers see a de-identified
#          projection.
#
#          2D.2 (SME 2026-10-19): the reporter contact for a VSR lives in its own
#          table (`reporter_contacts`, 1:1 with the report) and is custodied by
#          the TENANT_ADMIN of the report's tenant — nothing else. There is no
#          STATE_ADMIN path, no named-custodian column, no department branch and
#          no SUPER_ADMIN break-glass (docs/step2/2D.1_reporter_contact_design.md
#          §16, §17). Custodian reads/writes of the store are audited from day
#          one against the current audit sink (Path C); 2E migrates that sink.
# ============================================================================

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from loguru import logger
from sqlalchemy import select, text

from app.db.db_models import Report, ReporterContact
from app.db.ids import register_tenant
from app.db.runner import run
from app.db.session import session_scope
from app.services.actor import resolve_actor_uuid
from app.services.audit_service import log_audit

# The only role that may hold custody of a VSR reporter contact.
CUSTODIAN_ROLE = "TENANT_ADMIN"

# Reporter-identity fields stripped by de-identification.
_IDENTITY_FIELDS = ("reporter_name", "reporter_email", "reporter_phone",
                    "reporter_role", "reporter_organisation")

# Reporter-contact fields carried by the `reporter_contacts` store.
_CONTACT_FIELDS = ("reporter_name", "reporter_email", "reporter_phone")

# Audit actions (Path C — current sink: pg `audit_logs` + Firestore mirror).
AUDIT_CONTACT_WRITTEN = "REPORTER_CONTACT_WRITTEN"
AUDIT_CONTACT_READ = "REPORTER_CONTACT_READ"
AUDIT_CONTACT_DENIED = "REPORTER_CONTACT_READ_DENIED"


def _to_uuid(value: Any) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _actor_label(user: Optional[Dict[str, Any]]) -> Optional[str]:
    user = user or {}
    return user.get("email") or user.get("uid")


class ConfidentialReportingService:
    """DP-4 confidential reporting — flag + custodian access control."""

    def __init__(self, tenant_id: Optional[str] = None):
        self.tenant_id = tenant_id

    # -- custody ------------------------------------------------------------

    def user_tenant_uuid(self, user: Optional[Dict[str, Any]]):
        """Resolve a request user's tenant (slug) to its deterministic uuid."""
        slug = (user or {}).get("tenant_id")
        if not slug:
            return None
        try:
            return register_tenant(str(slug))
        except Exception:
            return None

    def is_tenant_custodian(self, user: Optional[Dict[str, Any]],
                            tenant_id: Any) -> bool:
        """True iff ``user`` is the TENANT_ADMIN of ``tenant_id``.

        Single-form rule (§16 Q4/Q7): role == TENANT_ADMIN and the user's tenant
        equals the report's tenant. No STATE_ADMIN, no department, no named
        custodian, no SUPER_ADMIN fallback.
        """
        if (user or {}).get("role") != CUSTODIAN_ROLE:
            return False
        user_tid = self.user_tenant_uuid(user)
        if user_tid is None or tenant_id is None:
            return False
        return str(user_tid) == str(tenant_id)

    # -- public -------------------------------------------------------------

    def mark_confidential(self, report_id: str, custodian: Dict[str, Any],
                          user: Dict[str, Any]) -> Dict[str, Any]:
        return run(self._mark_async(report_id, custodian, user))

    def can_view_reporter_identity(self, report: Any,
                                   user: Dict[str, Any]) -> bool:
        """Whether the caller may see raw reporter identity for ``report``.

        Non-confidential reports are unprotected. A confidential (VSR) report's
        identity is visible only to the TENANT_ADMIN of the report's own tenant
        (§16 Q4). `SUPER_ADMIN` is explicitly denied (§16 Q5).
        """
        is_conf = getattr(report, "is_confidential", None)
        tenant_id = getattr(report, "tenant_id", None)
        if isinstance(report, dict):
            is_conf = report.get("is_confidential", is_conf)
            tenant_id = report.get("tenant_id", tenant_id)
        if not is_conf:
            return True
        role = (user or {}).get("role")
        if role != CUSTODIAN_ROLE:
            return False
        # Named-custodian column retired (§16 Q4): custody is the tenant rule.
        return self.is_tenant_custodian(user, tenant_id)

    def deidentify(self, report: Any) -> Dict[str, Any]:
        """Return a reporter-identity-free projection for downstream use."""
        if isinstance(report, dict):
            data = dict(report)
        else:
            data = {c.name: getattr(report, c.name) for c in report.__table__.columns}
        for field in _IDENTITY_FIELDS:
            data[field] = None
        data["is_anonymous"] = True
        data["reporter_identity_protected"] = True
        return data

    def get_for_downstream(self, report_id: str,
                           user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return run(self._downstream_async(report_id, user))

    # -- reporter-contact store (2D.2) --------------------------------------

    def save_reporter_contact(self, report_id: str, tenant_id: Any, payload: Dict[str, Any],
                              user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Write-through a VSR reporter contact at submission (VSR only).

        Idempotent on `report_id` (1:1): a repeat submission updates the row.
        This is the single write site for the store. Audited from day one.
        """
        return run(self._save_contact_async(report_id, tenant_id, payload, user))

    def get_reporter_contact(self, report_id: str,
                             user: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Return the reporter contact for a report iff the caller is the
        TENANT_ADMIN of the report's tenant. Every access attempt is audited.

        Returns None (never raises) when the report has no contact row or the
        caller is not the custodian — a denied read discloses nothing.
        """
        return run(self._get_contact_async(report_id, user))

    # -- internals ----------------------------------------------------------

    async def _mark_async(self, report_id, custodian, user):
        cid = await resolve_actor_uuid(custodian)
        now = datetime.now(timezone.utc)
        async with session_scope() as session:
            row = (await session.execute(
                select(Report).where(Report.id == _to_uuid(report_id))
            )).scalars().first()
            if not row:
                raise ValueError(f"Report {report_id!r} not found")
            row.is_confidential = True
            row.updated_at = now
            await session.flush()
            result = {
                "id": str(row.id),
                "is_confidential": True,
            }
        log_audit(
            action="REPORT_MARKED_CONFIDENTIAL",
            user=(user or {}).get("email") or (user or {}).get("uid"),
            tenant_id=self.tenant_id,
            target_type="report",
            target_id=str(report_id),
            metadata={"custodian_id": str(cid) if cid else None},
        )
        logger.info(f"Report {report_id} marked confidential (custodian={cid})")
        return result

    async def _save_contact_async(self, report_id, tenant_id, payload, user):
        rid = _to_uuid(report_id)
        tid = _to_uuid(tenant_id)
        if rid is None or tid is None:
            raise ValueError(f"Invalid report_id/tenant_id: {report_id!r}/{tenant_id!r}")
        values = {f: payload.get(f) for f in _CONTACT_FIELDS}

        # 2D.2.1 (SME): an anonymous VSR — all contact fields empty — gets NO
        # contact row at all. Never insert a row of nulls or a synthetic
        # "Anonymous" name; there would be nothing for the custodian to follow up
        # on and it would imply a contact exists.
        if not any((str(v).strip() if v is not None else "")
                   for v in values.values()):
            logger.info(
                "Anonymous VSR %s: no reporter contact row written", report_id)
            return {}

        # 2D.2.1: all writes go through the SECURITY DEFINER function. The
        # submitter may be any authenticated tenant member (OFFICER/public
        # intake), so a direct INSERT cannot satisfy the custodial RLS policy.
        # The function re-validates that the report is a VSR, belongs to the
        # supplied tenant, and (when a request identity is present) that the
        # tenant matches it.
        try:
            async with session_scope() as session:
                async with session.begin_nested():
                    result = await session.execute(
                        text(
                            "select public.submit_vsr_contact("
                            ":report_id, :tenant_id, :reporter_name, "
                            ":reporter_email, :reporter_phone)"
                        ),
                        {
                            "report_id": rid,
                            "tenant_id": tid,
                            "reporter_name": values["reporter_name"],
                            "reporter_email": values["reporter_email"],
                            "reporter_phone": values["reporter_phone"],
                        },
                    )
                    contact_id = result.scalar()
        except Exception as exc:
            # The savepoint rolled back: the VSR exists but has NO reporter
            # contact. That is a data-integrity gap the custodian cannot fix
            # from the UI, so log it loudly and specifically rather than
            # silently continuing.
            logger.warning(
                "REPORTER_CONTACT_WRITE_FAILED report_id={} tenant_id={} "
                "error={}: {} — VSR stored without a reporter contact; the "
                "custodian cannot follow up on this report until it is "
                "backfilled",
                report_id, tenant_id, type(exc).__name__, exc)
            return {}
        log_audit(
            action=AUDIT_CONTACT_WRITTEN,
            # 2D.2.1: VSR contact writes are anonymous. Recording the submitter
            # here would re-link the contact row to the person via audit_logs.
            user=None,
            tenant_id=self.tenant_id,
            target_type="reporter_contact",
            target_id=str(report_id),
            metadata={"has_name": bool(values.get("reporter_name")),
                      "has_email": bool(values.get("reporter_email")),
                      "has_phone": bool(values.get("reporter_phone"))},
        )
        logger.info(f"Reporter contact stored for report {report_id}")
        return {"id": str(contact_id),
                "report_id": str(rid), "tenant_id": str(tid)}

    async def _get_contact_async(self, report_id, user):
        rid = _to_uuid(report_id)
        if rid is None:
            return None
        async with session_scope() as session:
            report = (await session.execute(
                select(Report).where(Report.id == rid)
            )).scalars().first()
            if not report:
                return None
            allowed = self.is_tenant_custodian(user, report.tenant_id)
            contact = None
            if allowed:
                contact = (await session.execute(
                    select(ReporterContact).where(ReporterContact.report_id == rid)
                )).scalars().first()
            if (report.report_type or "") != "voluntary":
                # The store is VSR-only (Q1). A non-VSR report can never be a
                # custodian read of this store.
                allowed = False
                contact = None
        if not allowed:
            log_audit(
                action=AUDIT_CONTACT_DENIED,
                user=_actor_label(user),
                tenant_id=self.tenant_id,
                target_type="reporter_contact",
                target_id=str(report_id),
                metadata={"reason": "not_tenant_custodian"},
            )
            return None
        log_audit(
            action=AUDIT_CONTACT_READ,
            user=_actor_label(user),
            tenant_id=self.tenant_id,
            target_type="reporter_contact",
            target_id=str(report_id),
            metadata={"custodian": True},
        )
        if contact is None:
            return None
        return {
            "id": str(contact.id),
            "report_id": str(contact.report_id),
            "tenant_id": str(contact.tenant_id),
            "reporter_name": contact.reporter_name,
            "reporter_email": contact.reporter_email,
            "reporter_phone": contact.reporter_phone,
            "created_at": contact.created_at,
            "updated_at": contact.updated_at,
        }

    async def _downstream_async(self, report_id, user):
        async with session_scope() as session:
            row = (await session.execute(
                select(Report).where(Report.id == _to_uuid(report_id))
            )).scalars().first()
            if not row:
                return None
            if row.is_confidential and not self.can_view_reporter_identity(row, user):
                log_audit(
                    action="CAAN_READ_REPORT_DEIDENTIFIED",
                    user=(user or {}).get("email") or (user or {}).get("uid"),
                    tenant_id=self.tenant_id,
                    target_type="report",
                    target_id=str(report_id),
                    metadata={"deidentified": True},
                )
                return self.deidentify(row)
            return {c.name: (str(getattr(row, c.name))
                             if isinstance(getattr(row, c.name), uuid.UUID)
                             else getattr(row, c.name))
                    for c in row.__table__.columns}
