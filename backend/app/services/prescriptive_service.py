# ============================================================================
# FILE: prescriptive_service.py
# PATH: backend/app/services/prescriptive_service.py
# PURPOSE: 1C.4 — minimum-viable PRESCRIPTIVE analysis over an EXISTING
#          register. Companion to 1C.3 (predictive): 1C.3 projects forward,
#          1C.4 recommends actions.
#
#          Register: hazards. Rules: a small, DOCUMENTED, deterministic list
#          (see RULES). No ML, no heuristics beyond the documented conditions,
#          no external dependencies.
#
#          Convention follows `predictive_service` / `metrics_service`: the rule
#          arithmetic is a pure, stateless function (`_evaluate_hazard`); the
#          service method only fetches the register and shapes the output.
#
#          This is NOT wired to any endpoint, UI, or scheduler (1C.4 scope).
# ============================================================================

from __future__ import annotations

from datetime import date, datetime, time as _time, timezone
from typing import Any, Dict, List, Optional

from app.db import pg
from app.db.db_models import Hazard
from app.db.ids import tenant_uuid
from app.db.isolation import demo_scope

# Hazard statuses treated as closed; anything else counts as open.
_CLOSED_STATUSES = {"CLOSED", "VERIFIED_CLOSED"}

_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}

# The documented rule list. Each rule: name, condition, action, severity, due_by.
RULES = (
    {
        "name": "corrective_action_missing",
        "condition": (
            "hazard is open AND corrective_action_flag is false "
            "AND age (as_of - created_at) >= no_action_days"
        ),
        "action": "Raise a corrective action (CAN)",
        "severity": "high if priority == 'H' or age >= 2*no_action_days, else medium",
        "due_by": None,
    },
    {
        "name": "review_overdue",
        "condition": "hazard is open AND follow_up_date is set AND follow_up_date < as_of",
        "action": "Complete the overdue hazard review",
        "severity": "high if overdue >= no_action_days, else medium",
        "due_by": "the hazard's follow_up_date",
    },
)

_LIMITATIONS = (
    "Deterministic threshold rules over the hazard register only. They are "
    "process prompts, not safety judgements: thresholds are fixed (no "
    "per-tenant/per-category tuning), the rules read no downstream registers "
    "(CAN/CAP/SRM status), and they do not rank by risk magnitude beyond the "
    "hazard priority. A hazard can fire more than one rule."
)

_STRONGER_METHOD = (
    "Step 4: weight recommendations by risk severity/probability and safety "
    "outcome, join CAN/CAP/SRM status so a rule fires only when the downstream "
    "action is genuinely absent, make thresholds tenant-configurable, and "
    "suppress/merge duplicate prompts per hazard."
)


# -- helpers -----------------------------------------------------------------

def _as_utc(value: Any) -> Optional[datetime]:
    """Coerce a date/datetime (or ISO string) to an aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, _time.min, tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _is_open(status: Optional[str]) -> bool:
    return str(status or "").strip().upper() not in _CLOSED_STATUSES


def _recommendation(rule: str, action: str, hazard_id: str, severity: str,
                    due_by: Optional[datetime]) -> Dict[str, Any]:
    return {
        "action": action,
        "reason": rule,
        "subject": {"id": hazard_id, "type": "hazard"},
        "severity": severity,
        "due_by": due_by.date().isoformat() if due_by else None,
    }


def _evaluate_hazard(row: Dict[str, Any], as_of: datetime,
                     no_action_days: int) -> List[Dict[str, Any]]:
    """Apply the documented rules to one hazard row (pure; no I/O)."""
    if not _is_open(row.get("status")):
        return []

    recs: List[Dict[str, Any]] = []
    hazard_id = str(row.get("hazard_id") or row.get("id") or "")
    created = _as_utc(row.get("created_at"))
    age_days = (as_of - created).days if created else None

    # R1 — corrective_action_missing
    if not row.get("corrective_action_flag") and age_days is not None and age_days >= no_action_days:
        severity = "high" if (
            str(row.get("priority") or "").upper() == "H" or age_days >= 2 * no_action_days
        ) else "medium"
        recs.append(_recommendation(
            "corrective_action_missing", "Raise a corrective action (CAN)",
            hazard_id, severity, None,
        ))

    # R2 — review_overdue
    follow_up = _as_utc(row.get("follow_up_date"))
    if follow_up is not None and follow_up < as_of:
        overdue_days = (as_of - follow_up).days
        severity = "high" if overdue_days >= no_action_days else "medium"
        recs.append(_recommendation(
            "review_overdue", "Complete the overdue hazard review",
            hazard_id, severity, follow_up,
        ))

    return recs


class PrescriptiveService:
    """Tenant-scoped prescriptive analysis over an existing register.

    1C.4 implements exactly one register (``hazards``) and the documented rule
    list in :data:`RULES`. It reads the register only; it writes nothing.
    """

    register = "hazards"

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def _hazard_rows(self) -> List[Dict[str, Any]]:
        """Hazard rows for this tenant (demo-scoped)."""
        tid = tenant_uuid(self.tenant_id)
        return pg.fetch_all(
            Hazard,
            where=[Hazard.tenant_id == tid, Hazard.is_demo == demo_scope()],
        )

    def recommend_hazard_actions(
        self,
        as_of: Optional[Any] = None,
        no_action_days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Recommend actions for a tenant's hazards from a documented rule list.

        Input
        -----
        :param as_of: reference date/datetime; defaults to now (UTC). Pass a
            fixed value for reproducible output.
        :param no_action_days: threshold (days) used by the rules (>= 1).

        Output
        ------
        An ordered ``list`` of recommendation dicts::

            {
                "action":   str,               # short action label
                "reason":   str,               # rule name that fired
                "subject":  {"id": str, "type": "hazard"},
                "severity": "low" | "medium" | "high",
                "due_by":   "YYYY-MM-DD" | None,
            }

        Ordering: by severity (high, medium, low), then action label, then
        subject id — deterministic.

        Rule list
        ---------
        See :data:`RULES`. Two rules over the ``hazards`` register:

        * ``corrective_action_missing`` — open hazard, no corrective action
          flagged, age >= ``no_action_days`` → "Raise a corrective action (CAN)".
        * ``review_overdue`` — open hazard whose ``follow_up_date`` is in the
          past → "Complete the overdue hazard review".

        Method / limitations / Step 4
        -----------------------------
        Deterministic threshold rules; see ``_LIMITATIONS`` and
        ``_STRONGER_METHOD``.
        """
        if no_action_days < 1:
            raise ValueError("no_action_days must be >= 1")

        ref = _as_utc(as_of) or datetime.now(timezone.utc)
        recommendations: List[Dict[str, Any]] = []
        for row in self._hazard_rows():
            recommendations.extend(_evaluate_hazard(row, ref, no_action_days))

        recommendations.sort(
            key=lambda r: (
                -_SEVERITY_RANK.get(r["severity"], 0),
                r["reason"],
                r["subject"]["id"],
            )
        )
        return recommendations
