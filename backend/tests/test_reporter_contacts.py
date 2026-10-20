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
            {"role": "OFFICER", "department": "safety", "tenant_id": slug,
             "uid": "u1"})
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
            {"uid": "reporter-1", "email": "jane@x.com", "role": "OFFICER",
             "department": "safety", "tenant_id": slug},
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
            {"uid": "reporter-2", "email": "jane@x.com", "role": "OFFICER",
             "department": "safety", "tenant_id": slug},
        )
        assert not stored.get("is_confidential")
        assert _contact_row(stored["id"]) is None
    finally:
        cleanup(slug, TABLES)


# ---------------------------------------------------------------------------
# 2D.2.1 — VSR anonymity and the definer write path.
# ---------------------------------------------------------------------------
def _created_by(report_id):
    from sqlalchemy import text

    async def _go():
        async with session_scope() as s:
            r = await s.execute(
                text("select created_by from public.reports where id = :id"),
                {"id": report_id})
            return r.scalar()

    return run(_go())


def _audit_rows_for(report_id):
    from sqlalchemy import text

    async def _go():
        async with session_scope() as s:
            r = await s.execute(
                text("select action, actor from public.audit_logs "
                     "where target_id = :id"), {"id": report_id})
            return r.fetchall()

    return run(_go())


def test_vsr_anonymous_created_by_is_null():
    """SME Q1/Q2: every VSR is anonymous at the DB layer, even when the
    submitter is a logged-in STAFF user."""
    from app.services.report_service import ReportService

    slug = unique_slug("rc-anon")
    tid = create_tenant(slug)
    try:
        stored = ReportService(slug).create_report(
            {
                "report_type": "voluntary",
                "narrative": "anonymous bird strike report",
                "location": "KTM",
                "occurrence_date": datetime.now(timezone.utc),
                "reporter_name": None,
                "reporter_email": None,
                "reporter_phone": None,
                "is_anonymous": True,
            },
            {"uid": "staff-uid", "email": "staff@x.test", "role": "STAFF",
             "tenant_id": slug},
        )
        assert _created_by(stored["id"]) is None
    finally:
        cleanup(slug, TABLES)


def test_vsr_identified_created_by_is_still_null():
    """Q2: contact fields do not re-identify the row — created_by stays NULL."""
    from app.services.report_service import ReportService

    slug = unique_slug("rc-ident")
    tid = create_tenant(slug)
    try:
        stored = ReportService(slug).create_report(
            {
                "report_type": "voluntary",
                "narrative": "identified bird strike report",
                "location": "KTM",
                "occurrence_date": datetime.now(timezone.utc),
                "reporter_name": "Jane Reporter",
                "reporter_email": "jane@x.com",
            },
            {"uid": "staff-uid", "email": "staff@x.test", "role": "STAFF",
             "tenant_id": slug},
        )
        assert _created_by(stored["id"]) is None
        row = _contact_row(stored["id"])
        assert row is not None and row.reporter_email == "jane@x.com"
        # The contact-write audit must not name the submitter either.
        rows = _audit_rows_for(stored["id"])
        assert all(actor != "staff@x.test" for _, actor in rows)
    finally:
        cleanup(slug, TABLES)


def test_mor_created_by_unchanged():
    """MOR is identified: created_by keeps the submitter uid."""
    from app.services.report_service import ReportService

    slug = unique_slug("rc-mor-cb")
    tid = create_tenant(slug)
    try:
        stored = ReportService(slug).create_report(
            {
                "report_type": "mandatory",
                "narrative": "runway incursion report",
                "location": "KTM",
                "occurrence_date": datetime.now(timezone.utc),
                "reporter_name": "Jane Reporter",
                "reporter_email": "jane@x.com",
            },
            {"uid": "mor-uid", "email": "mor@x.test", "role": "OFFICER",
             "department": "safety", "tenant_id": slug},
        )
        assert _created_by(stored["id"]) == "mor-uid"
    finally:
        cleanup(slug, TABLES)


def test_vsr_anonymous_no_contact_row():
    """Edit 5: all contact fields empty -> no row at all (not a null row)."""
    from app.services.report_service import ReportService

    slug = unique_slug("rc-no-contact")
    tid = create_tenant(slug)
    try:
        stored = ReportService(slug).create_report(
            {
                "report_type": "voluntary",
                "narrative": "anonymous report with no contact",
                "location": "KTM",
                "occurrence_date": datetime.now(timezone.utc),
                "reporter_name": None,
                "reporter_email": None,
                "reporter_phone": None,
            },
            {"uid": "staff-uid", "email": "staff@x.test", "role": "STAFF",
             "tenant_id": slug},
        )
        assert _contact_row(stored["id"]) is None
    finally:
        cleanup(slug, TABLES)


def test_vsr_staff_can_submit():
    """A STAFF user can file a VSR (post-office model) via the legacy route."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.middleware.auth import get_tenant_user

    slug = unique_slug("rc-staff")
    tid = create_tenant(slug)
    submitter = "staff-" + uuid.uuid4().hex[:8]
    app.dependency_overrides[get_tenant_user] = lambda: {
        "uid": submitter, "email": f"{submitter}@x.test", "role": "STAFF",
        "tenant_id": slug, "department": "flight_ops",
    }
    try:
        resp = TestClient(app).post("/api/v1/reports/", json={
            "narrative": "a staff-filed voluntary safety report",
            "location": "KTM",
            "occurrence_date": datetime.now(timezone.utc).isoformat(),
            "reporter_name": None,
            "reporter_email": None,
            "reporter_phone": None,
            "is_anonymous": True,
        })
        assert resp.status_code == 201, resp.text
        report_id = resp.json()["id"]
        assert _created_by(report_id) is None
        # No submitter email anywhere in the audit trail for this report.
        rows = _audit_rows_for(report_id)
        assert rows, "expected a VSR_SUBMITTED audit event"
        assert all(actor != f"{submitter}@x.test" for _, actor in rows)
        assert any(action == "VSR_SUBMITTED" for action, _ in rows)
        # Anonymous -> no contact row.
        assert _contact_row(report_id) is None
    finally:
        app.dependency_overrides.clear()
        cleanup(slug, TABLES)


def test_vsr_audit_does_not_contain_submitter_email():
    """Finding C: the VSR audit event must not identify the submitter."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.middleware.auth import get_tenant_user

    slug = unique_slug("rc-audit-anon")
    tid = create_tenant(slug)
    submitter = "sub-" + uuid.uuid4().hex[:8]
    app.dependency_overrides[get_tenant_user] = lambda: {
        "uid": submitter, "email": f"{submitter}@x.test", "role": "OFFICER",
        "tenant_id": slug, "department": "safety",
    }
    try:
        resp = TestClient(app).post("/api/v1/reports/vsr", json={
            "narrative": "a safety department filed voluntary report",
            "location": "KTM",
            "occurrence_date": datetime.now(timezone.utc).isoformat(),
            "is_anonymous": True,
        })
        assert resp.status_code == 201, resp.text
        report_id = resp.json()["id"]
        rows = _audit_rows_for(report_id)
        assert any(action == "VSR_SUBMITTED" for action, _ in rows)
        assert all(actor != f"{submitter}@x.test" for _, actor in rows)
    finally:
        app.dependency_overrides.clear()
        cleanup(slug, TABLES)


def test_mor_audit_contains_submitter_email():
    """MOR stays identified, including in the audit trail."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.middleware.auth import get_tenant_user

    slug = unique_slug("rc-audit-mor")
    tid = create_tenant(slug)
    submitter = "mor-" + uuid.uuid4().hex[:8]
    app.dependency_overrides[get_tenant_user] = lambda: {
        "uid": submitter, "email": f"{submitter}@x.test", "role": "TENANT_ADMIN",
        "tenant_id": slug, "department": "safety",
    }
    try:
        resp = TestClient(app).post("/api/v1/reports/mor", json={
            "narrative": "mandatory occurrence report",
            "occurrence_date_time": datetime.now(timezone.utc).isoformat(),
            "occurrence_location": "KTM",
            "occurrence_country": "NP",
            "occurrence_type": "INCIDENT",
            "occurrence_class": "CLASS_C",
            "occurrence_category": "BIRD",
            "flight_type": "Commercial",
            "flight_phase": "Landing",
            "aircraft_make": "Boeing",
            "aircraft_model": "737",
            "aircraft_registration": "9N-ABC",
            "aircraft_category": "Aeroplane",
            "operator": "Test Air",
            "reporter_name": "Jane Reporter",
            "reporter_role": "pilot",
            "reporter_organisation": "Test Air",
            "reporter_email": "jane@x.com",
        })
        assert resp.status_code == 201, resp.text
        report_id = resp.json()["id"]
        rows = _audit_rows_for(report_id)
        assert any(actor == f"{submitter}@x.test" for _, actor in rows)
    finally:
        app.dependency_overrides.clear()
        cleanup(slug, TABLES)


def test_direct_insert_denied_and_definer_allowed():
    """The table has no `authenticated` INSERT policy; all writes must go
    through public.submit_vsr_contact()."""
    from sqlalchemy import text

    from app.db.ids import register_tenant

    slug = unique_slug("rc-definer")
    tid = str(register_tenant(slug))
    report_id = str(uuid.uuid4())

    async def seed():
        async with session_scope() as s:
            await s.execute(text(
                "insert into public.tenants (id, slug, name, is_demo, "
                "is_beta_sandbox, created_at, updated_at) values "
                "(:id, :slug, :name, false, false, now(), now()) "
                "on conflict do nothing"), {"id": tid, "slug": slug, "name": slug})
            await s.execute(text(
                "insert into public.reports (id, tenant_id, report_type, status, "
                "ai_status, narrative, location, occurrence_date, created_by, "
                "is_confidential) values (:id, :t, 'voluntary', 'NEW', 'PENDING', "
                "'n', 'KTM', now(), NULL, true)"), {"id": report_id, "t": tid})

    def attempt_direct():
        async def _go():
            async with session_scope() as s:
                await s.execute(text("SET LOCAL ROLE authenticated"))
                await s.execute(text(
                    "select set_config('app.current_role', 'STAFF', true)"))
                await s.execute(text(
                    "select set_config('app.current_tenant', :t, true)"), {"t": tid})
                await s.execute(text(
                    "insert into public.reporter_contacts (report_id, tenant_id, "
                    "reporter_name) values (:r, :t, 'Jane')"),
                    {"r": report_id, "t": tid})

        try:
            run(_go())
            return True
        except Exception:
            return False

    def attempt_definer():
        async def _go():
            async with session_scope() as s:
                await s.execute(text("SET LOCAL ROLE authenticated"))
                await s.execute(text(
                    "select set_config('app.current_role', 'STAFF', true)"))
                await s.execute(text(
                    "select set_config('app.current_tenant', :t, true)"), {"t": tid})
                await s.execute(text(
                    "select public.submit_vsr_contact(:r, :t, 'Jane', NULL, NULL)"),
                    {"r": report_id, "t": tid})

        try:
            run(_go())
            return True
        except Exception:
            return False

    try:
        run(seed())
        assert attempt_direct() is False
        assert attempt_definer() is True
        assert _contact_row(report_id) is not None
    finally:
        cleanup(slug, TABLES)
