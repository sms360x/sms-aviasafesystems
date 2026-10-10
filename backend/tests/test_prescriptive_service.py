# ============================================================================
# 1C.4 — minimum-viable prescriptive analysis (prescriptive_service).
#
# Deterministic / no live DB: `pg.fetch_all` is monkeypatched with a fake that
# honours the tenant filter built into the query, so tenant scoping is
# genuinely exercised.
# ============================================================================

from datetime import datetime, timezone

import pytest
from sqlalchemy.dialects import postgresql

from app.db import pg
from app.db.ids import tenant_uuid
from app.services.prescriptive_service import (
    PrescriptiveService,
    _evaluate_hazard,
)

_AIR1 = tenant_uuid("air1")
_AIR2 = tenant_uuid("air2")

_AS_OF = datetime(2026, 6, 15, tzinfo=timezone.utc)

_DATA = {
    "air1": [
        # R1 fires (open, no corrective action, 75 days old, high priority).
        {"hazard_id": "H-1", "status": "Open", "priority": "H",
         "corrective_action_flag": False,
         "created_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
         "follow_up_date": None},
        # R2 fires (open, follow_up_date in the past); R1 does not (14 days).
        {"hazard_id": "H-2", "status": "Open", "priority": "M",
         "corrective_action_flag": False,
         "created_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
         "follow_up_date": datetime(2026, 5, 1, tzinfo=timezone.utc)},
        # Closed → nothing fires.
        {"hazard_id": "H-3", "status": "Closed", "priority": "H",
         "corrective_action_flag": False,
         "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
         "follow_up_date": datetime(2026, 2, 1, tzinfo=timezone.utc)},
        # Corrective action already present → R1 does not fire.
        {"hazard_id": "H-4", "status": "Open", "priority": "M",
         "corrective_action_flag": True,
         "created_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
         "follow_up_date": None},
        # Too young (< no_action_days) and no follow-up → nothing fires.
        {"hazard_id": "H-5", "status": "Open", "priority": "M",
         "corrective_action_flag": False,
         "created_at": datetime(2026, 5, 20, tzinfo=timezone.utc),
         "follow_up_date": None},
    ],
    "air2": [],
}
_TID = {"air1": _AIR1, "air2": _AIR2}


def _sql(where) -> str:
    try:
        return " ".join(
            str(w.compile(dialect=postgresql.dialect(),
                          compile_kwargs={"literal_binds": True}))
            for w in where
        ).lower()
    except Exception:
        return " ".join(str(w) for w in where).lower()


def _install_fake_fetch(monkeypatch):
    def fake_fetch_all(model, *, where=None, order_by=None, limit=None):
        sql = _sql(where) if where else ""
        for slug, tid in _TID.items():
            if str(tid) in sql:
                return [dict(r) for r in _DATA[slug]]
        return []

    monkeypatch.setattr(pg, "fetch_all", fake_fetch_all)


# -- pure rule evaluation ----------------------------------------------------

def test_rule_corrective_action_missing_only():
    row = {"hazard_id": "X", "status": "Open", "priority": "M",
           "corrective_action_flag": False,
           "created_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
           "follow_up_date": None}
    recs = _evaluate_hazard(row, _AS_OF, 30)
    assert len(recs) == 1
    assert recs[0]["reason"] == "corrective_action_missing"
    assert recs[0]["severity"] == "medium"
    assert recs[0]["due_by"] is None


def test_rule_review_overdue_only():
    row = {"hazard_id": "Y", "status": "Open", "priority": "M",
           "corrective_action_flag": False,
           "created_at": datetime(2026, 6, 10, tzinfo=timezone.utc),
           "follow_up_date": datetime(2026, 6, 1, tzinfo=timezone.utc)}
    recs = _evaluate_hazard(row, _AS_OF, 30)
    assert [r["reason"] for r in recs] == ["review_overdue"]
    assert recs[0]["severity"] == "medium"
    assert recs[0]["due_by"] == "2026-06-01"


def test_no_rules_fired_when_resolved():
    row = {"hazard_id": "Z", "status": "Closed", "priority": "H",
           "corrective_action_flag": True,
           "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
           "follow_up_date": None}
    assert _evaluate_hazard(row, _AS_OF, 30) == []


# -- service -----------------------------------------------------------------

def test_recommend_fixed_window(monkeypatch):
    _install_fake_fetch(monkeypatch)
    recs = PrescriptiveService("air1").recommend_hazard_actions(as_of=_AS_OF)
    assert recs == [
        {
            "action": "Raise a corrective action (CAN)",
            "reason": "corrective_action_missing",
            "subject": {"id": "H-1", "type": "hazard"},
            "severity": "high",
            "due_by": None,
        },
        {
            "action": "Complete the overdue hazard review",
            "reason": "review_overdue",
            "subject": {"id": "H-2", "type": "hazard"},
            "severity": "high",
            "due_by": "2026-05-01",
        },
    ]


def test_output_shape(monkeypatch):
    _install_fake_fetch(monkeypatch)
    recs = PrescriptiveService("air1").recommend_hazard_actions(as_of=_AS_OF)
    assert recs  # non-empty
    for rec in recs:
        assert set(rec) == {"action", "reason", "subject", "severity", "due_by"}
        assert set(rec["subject"]) == {"id", "type"}
        assert rec["subject"]["type"] == "hazard"
        assert rec["severity"] in ("low", "medium", "high")


def test_no_rules_fired_returns_empty(monkeypatch):
    _install_fake_fetch(monkeypatch)
    # A window (2026-04-15) before H-2's follow-up and before H-5's creation,
    # where H-1 is still too young and H-4 already has a corrective action.
    recs = PrescriptiveService("air1").recommend_hazard_actions(
        as_of=datetime(2026, 4, 15, tzinfo=timezone.utc))
    assert recs == []


def test_tenant_isolation(monkeypatch):
    _install_fake_fetch(monkeypatch)
    a = PrescriptiveService("air1").recommend_hazard_actions(as_of=_AS_OF)
    b = PrescriptiveService("air2").recommend_hazard_actions(as_of=_AS_OF)
    assert len(a) == 2
    # air2 has no data and must not see air1's recommendations.
    assert b == []


def test_rejects_bad_threshold(monkeypatch):
    _install_fake_fetch(monkeypatch)
    with pytest.raises(ValueError):
        PrescriptiveService("air1").recommend_hazard_actions(as_of=_AS_OF,
                                                             no_action_days=0)
