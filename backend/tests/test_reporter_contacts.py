# ============================================================================
# 2D.2 — VSR reporter-contact store (schema + custodian + audit write-through).
#
# Design of record: docs/step2/2D.1_reporter_contact_design.md §16 (SME
# 2026-10-19). Custody of a report's reporter contact is the TENANT_ADMIN of the
# report's tenant and nobody else: no STATE_ADMIN path, no department branch, no
# named-custodian column, no SUPER_ADMIN break-glass.
#
# DB-backed (the store is a real table with RLS); each test uses a throwaway
# tenant slug and cleans up. Service-level assertions are deterministic.
# ============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.db_models import Report, ReporterContact
from app.db.isolation import demo_scope
from app.db.session import session_scope
from app.services.confidential_reporting_service import (
    AUDIT_CONTACT_DENIED,
    AUDIT_CONTACT_READ,
    AUDIT_CONTACT_WRITTEN,
    ConfidentialReportingService,
)

from _mbb import cleanup, create_tenant, create_user, run, unique_slug

TABLES = ("reporter_contacts", "reports")


def _seed_report(tid, report_type="voluntary"):
    rid = uuid.uuid4()
    now = datetime.now(timezone.utc)

    async def _go():
        async with session_scope() as s:
            s.add(Report(
                id=rid, tenant_id=tid, report_type=report_type, status="NEW",
                narrative="confidential narrative", location="KTM",
                occurrence_date=now, created_by="system", is_demo=demo_scope(),
                reporter_name="Jane Reporter", reporter_email="jane@x.com"))

    run(_go())
    return str(rid)


def _contact_row(report_id):
    async def _go():
        async with session_scope() as s:
            return (await s.execute(
                select(ReporterContact).where(ReporterContact.report_id == uuid.UUID(report_id))
            )).scalars().first()

    return run(_go())


def _audit_actions(monkeypatch):
    """Capture log_audit calls made by the service module."""
    seen = []
    import app.services.confidential_reporting_service as mod

    monkeypatch.setattr(
        mod, "log_audit",
        lambda **kw: seen.append(kw.get("action")),
    )
    return seen


def test_vsr_contact_written_at_submission():
    slug = unique_slug("rc-write")
    tid = create_tenant(slug)
    rid = _seed_report(tid)
    try:
        svc = ConfidentialReportingService(slug)
        out = svc.save_reporter_contact(
            rid, tid,
            {"reporter_name": "Jane Reporter", "reporter_email": "jane@x.com",
             "reporter_phone": "+977-9800000000"},
            {"role": "STAFF", "tenant_id": slug, "uid": "u1"})
        assert out["report_id"] == rid

        row = _contact_row(rid)
        assert row is not None
        assert row.reporter_name == "Jane Reporter"
        assert row.reporter_email == "jane@x.com"
        assert row.reporter_phone == "+977-9800000000"
        assert str(row.tenant_id) == str(tid)
    finally:
        cleanup(slug, TABLES)


def test_contact_write_is_idempotent_1_to_1():
    slug = unique_slug("rc-idem")
    tid = create_tenant(slug)
    rid = _seed_report(tid)
    try:
        svc = ConfidentialReportingService(slug)
        svc.save_reporter_contact(rid, tid, {"reporter_email": "a@x.com"}, None)
        svc.save_reporter_contact(rid, tid, {"reporter_email": "b@x.com"}, None)

        async def _count():
            async with session_scope() as s:
                return len((await s.execute(
                    select(ReporterContact).where(
                        ReporterContact.report_id == uuid.UUID(rid))
                )).scalars().all())

        assert run(_count()) == 1
        assert _contact_row(rid).reporter_email == "b@x.com"
    finally:
        cleanup(slug, TABLES)


def test_tenant_admin_reads_contact(monkeypatch):
    slug = unique_slug("rc-admin")
    tid = create_tenant(slug)
    rid = _seed_report(tid)
    try:
        svc = ConfidentialReportingService(slug)
        svc.save_reporter_contact(rid, tid, {"reporter_name": "Jane"}, None)
        actions = _audit_actions(monkeypatch)

        out = svc.get_reporter_contact(
            rid, {"role": "TENANT_ADMIN", "tenant_id": slug, "uid": "admin"})
        assert out is not None
        assert out["reporter_name"] == "Jane"
        assert AUDIT_CONTACT_READ in actions
    finally:
        cleanup(slug, TABLES)


def test_non_custodian_roles_denied(monkeypatch):
    """Every non-TENANT_ADMIN role is denied — including SUPER_ADMIN and the
    state regulator, which see aggregates, never reporter identity."""
    slug = unique_slug("rc-deny")
    tid = create_tenant(slug)
    rid = _seed_report(tid)
    try:
        svc = ConfidentialReportingService(slug)
        svc.save_reporter_contact(rid, tid, {"reporter_name": "Jane"}, None)
        actions = _audit_actions(monkeypatch)

        for role in ("SUPER_ADMIN", "STATE_SMD", "CAAN_SMD", "OFFICER",
                     "DEPT_ADMIN", "STAFF", "ACCOUNTABLE_EXECUTIVE"):
            assert svc.get_reporter_contact(
                rid, {"role": role, "tenant_id": slug, "uid": "x"}) is None, role
        assert actions.count(AUDIT_CONTACT_DENIED) == 7
    finally:
        cleanup(slug, TABLES)


def test_tenant_admin_of_another_tenant_denied(monkeypatch):
    slug_a = unique_slug("rc-a")
    slug_b = unique_slug("rc-b")
    tid_a = create_tenant(slug_a)
    create_tenant(slug_b)
    rid = _seed_report(tid_a)
    try:
        svc = ConfidentialReportingService(slug_a)
        svc.save_reporter_contact(rid, tid_a, {"reporter_name": "Jane"}, None)
        _audit_actions(monkeypatch)

        # A TENANT_ADMIN of a *different* tenant is not the custodian.
        assert svc.get_reporter_contact(
            rid, {"role": "TENANT_ADMIN", "tenant_id": slug_b, "uid": "b"}) is None
    finally:
        cleanup(slug_a, TABLES)
        cleanup(slug_b, TABLES)


def test_mor_is_not_a_contact_store_read(monkeypatch):
    """The store is VSR-only (Q1): a MOR report never yields a contact read."""
    slug = unique_slug("rc-mor")
    tid = create_tenant(slug)
    rid = _seed_report(tid, report_type="mandatory")
    try:
        svc = ConfidentialReportingService(slug)
        svc.save_reporter_contact(rid, tid, {"reporter_name": "Jane"}, None)
        _audit_actions(monkeypatch)

        assert svc.get_reporter_contact(
            rid, {"role": "TENANT_ADMIN", "tenant_id": slug, "uid": "admin"}) is None
    finally:
        cleanup(slug, TABLES)


def test_can_view_reporter_identity_is_tenant_custodian_only():
    svc = ConfidentialReportingService("air1")
    report = {"is_confidential": True, "tenant_id": "TID"}

    # Non-confidential reports are unprotected.
    assert svc.can_view_reporter_identity(
        {"is_confidential": False}, {"role": "STAFF"}) is True

    # SUPER_ADMIN is denied outright (Q5) — no break-glass in 2D.2.
    assert svc.can_view_reporter_identity(
        report, {"role": "SUPER_ADMIN", "tenant_id": "air1"}) is False

    # The department branch is retired (Q4/Q7).
    assert svc.can_view_reporter_identity(
        report, {"role": "OFFICER", "tenant_id": "air1",
                 "department": "safety"}) is False


def test_write_audit_is_emitted(monkeypatch):
    slug = unique_slug("rc-audit")
    tid = create_tenant(slug)
    rid = _seed_report(tid)
    try:
        svc = ConfidentialReportingService(slug)
        actions = _audit_actions(monkeypatch)
        svc.save_reporter_contact(rid, tid, {"reporter_name": "Jane"}, None)
        assert AUDIT_CONTACT_WRITTEN in actions
    finally:
        cleanup(slug, TABLES)


def test_create_report_writes_store_and_sets_flag():
    """The submission path (single write site) must populate the store and set
    `is_confidential`, while leaving `reports.reporter_*` populated (Q2:
    deprecate now, drop later — no reader changes in 2D.2)."""
    from app.services.report_service import ReportService

    slug = unique_slug("rc-submit")
    tid = create_tenant(slug)
    try:
        stored = ReportService(slug).create_report(
            {
                "report_type": "voluntary",
                "narrative": "bird strike on approach",
                "location": "KTM",
                "occurrence_date": datetime.now(timezone.utc),
                "reporter_name": "Jane Reporter",
                "reporter_email": "jane@x.com",
                "reporter_phone": "+977-9800000000",
                "is_anonymous": False,
            },
            {"uid": "reporter-1", "email": "jane@x.com", "role": "STAFF",
             "tenant_id": slug},
        )
        rid = stored["id"]
        assert stored["is_confidential"] is True

        row = _contact_row(rid)
        assert row is not None
        assert row.reporter_name == "Jane Reporter"
        assert row.reporter_email == "jane@x.com"
        assert row.reporter_phone == "+977-9800000000"

        # Q2: the legacy columns remain populated for now.
        async def _report():
            async with session_scope() as s:
                return (await s.execute(
                    select(Report).where(Report.id == uuid.UUID(rid))
                )).scalars().first()

        legacy = run(_report())
        assert legacy.reporter_name == "Jane Reporter"
        assert legacy.reporter_email == "jane@x.com"
    finally:
        cleanup(slug, TABLES)


def test_create_mor_does_not_write_store():
    """The store is VSR-only (Q1/Q6): a MOR submission writes no contact row and
    is not marked confidential."""
    from app.services.report_service import ReportService

    slug = unique_slug("rc-submit-mor")
    tid = create_tenant(slug)
    try:
        stored = ReportService(slug).create_report(
            {
                "report_type": "mandatory",
                "narrative": "runway incursion",
                "location": "KTM",
                "occurrence_date": datetime.now(timezone.utc),
                "reporter_name": "Jane Reporter",
                "reporter_email": "jane@x.com",
            },
            {"uid": "reporter-2", "email": "jane@x.com", "role": "STAFF",
             "tenant_id": slug},
        )
        assert not stored.get("is_confidential")
        assert _contact_row(stored["id"]) is None
    finally:
        cleanup(slug, TABLES)
