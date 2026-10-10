# ============================================================================
# FILE: predictive_service.py
# PATH: backend/app/services/predictive_service.py
# PURPOSE: 1C.3 — minimum-viable predictive analysis over an EXISTING register.
#          No ML, no statistics libraries, no external dependencies: a
#          per-period count series is projected forward by a simple linear
#          trend (least-squares extrapolation).
#
#          Register: hazards. Measure: open hazards per calendar month.
#          Reads only `hazards` (tenant-scoped, demo-scoped).
#
#          Convention follows `metrics_service`: the projection arithmetic is
#          a pure, stateless function (`_project_counts`); the service method
#          only fetches the register and shapes the documented output.
#
#          This is NOT wired to any endpoint, UI, or scheduler (1C.3 scope).
# ============================================================================

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.db import pg
from app.db.db_models import Hazard
from app.db.ids import tenant_uuid
from app.db.isolation import demo_scope

# Hazard statuses treated as closed; anything else counts as open.
_CLOSED_STATUSES = {"CLOSED", "VERIFIED_CLOSED"}

_METHOD = {
    "no_data": "no_data",
    "constant": "constant",
    "trend": "linear_trend",
}

_LIMITATIONS = (
    "Simple least-squares linear extrapolation of a short monthly count "
    "series; assumes the near-term trend continues. It ignores seasonality, "
    "reporting-rate changes, backlog dynamics, and per-category structure, and "
    "it is bounded at zero. It is a planning indicator, not a safety decision."
)

_STRONGER_METHOD = (
    "Step 4: fit a seasonal/ARIMA model on a longer history, separate "
    "new-occurrence inflow from closure outflow, and project per taxonomy "
    "category with confidence intervals. Optional external leading "
    "indicators (flight hours, reports per 1000 sectors) would normalise the "
    "rate."
)


def _is_open(status: Optional[str]) -> bool:
    return str(status or "").strip().upper() not in _CLOSED_STATUSES


def _period_key(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _shift_month(dt: datetime, months: int) -> datetime:
    """Return the first day of the month `months` after `dt` (UTC, day = 1)."""
    total = (dt.year * 12 + (dt.month - 1)) + months
    year, month0 = divmod(total, 12)
    return datetime(year, month0 + 1, 1, tzinfo=timezone.utc)


def _project_counts(counts: Sequence[int], periods_ahead: int = 1) -> Dict[str, Any]:
    """Project a per-period count series forward (pure; no I/O).

    Method (arithmetic only):
      * 0 points  -> ``no_data``  (projected values are ``None``)
      * 1 point   -> ``constant`` (that count repeated)
      * >=2 points-> ``linear_trend``: least-squares slope/intercept over
                     index 0..n-1, extrapolated to the next periods, clamped
                     at 0 and rounded to the nearest integer.

    Returns ``{"method": str, "projected": List[Optional[int]]}`` with
    ``periods_ahead`` entries.
    """
    if periods_ahead < 1:
        raise ValueError("periods_ahead must be >= 1")

    n = len(counts)
    if n == 0:
        return {"method": _METHOD["no_data"], "projected": [None] * periods_ahead}
    if n == 1:
        value = int(max(0, counts[0]))
        return {"method": _METHOD["constant"], "projected": [value] * periods_ahead}

    mean_x = sum(range(n)) / n
    mean_y = sum(counts) / n
    denom = sum((x - mean_x) ** 2 for x in range(n))
    slope = (
        sum((x - mean_x) * (y - mean_y) for x, y in zip(range(n), counts)) / denom
        if denom
        else 0.0
    )
    intercept = mean_y - slope * mean_x

    projected: List[int] = []
    for step in range(1, periods_ahead + 1):
        value = intercept + slope * (n - 1 + step)
        projected.append(int(round(max(0.0, value))))
    return {"method": _METHOD["trend"], "projected": projected}


class PredictiveService:
    """Tenant-scoped predictive analysis over an existing register.

    1C.3 implements exactly one register (``hazards``) and one measure
    (open hazards per calendar month), projected forward by a simple linear
    trend. It reads the register only; it writes nothing.
    """

    register = "hazards"
    measure = "open_hazards"
    period = "month"

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    # -- data ---------------------------------------------------------------

    def _open_hazard_rows(self) -> List[Dict[str, Any]]:
        """Open hazard rows for this tenant (demo-scoped)."""
        tid = tenant_uuid(self.tenant_id)
        return pg.fetch_all(
            Hazard,
            where=[Hazard.tenant_id == tid, Hazard.is_demo == demo_scope()],
        )

    def _monthly_open_counts(self, periods_back: int,
                             as_of: datetime) -> List[Tuple[str, int]]:
        """Ordered ``(YYYY-MM, count)`` for the window ending at ``as_of``'s
        month (oldest -> newest).

        Each month counts the tenant's *open* hazards (status not closed) that
        were created in that month.
        """
        rows = self._open_hazard_rows()

        periods = [
            _shift_month(as_of, -offset)
            for offset in range(periods_back - 1, -1, -1)
        ]
        keys = [_period_key(p) for p in periods]
        counts: Dict[str, int] = {key: 0 for key in keys}

        for row in rows:
            if not _is_open(row.get("status")):
                continue
            created = row.get("created_at")
            if not isinstance(created, datetime):
                continue
            key = _period_key(created)
            if key in counts:
                counts[key] += 1

        return [(key, counts[key]) for key in keys]

    # -- public -------------------------------------------------------------

    def project_open_hazards(
        self,
        periods_back: int = 6,
        periods_ahead: int = 1,
        as_of: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Project the tenant's open-hazard count forward by a simple trend.

        Input
        -----
        :param periods_back: historical monthly periods to read (>= 1).
        :param periods_ahead: monthly periods to project (>= 1).
        :param as_of: reference datetime; defaults to now (UTC). Pass a fixed
            value for reproducible output.

        Output (documented; stable keys)
        --------------------------------
        ``tenant_id`` (str), ``register`` ("hazards"), ``measure``
        ("open_hazards"), ``period`` ("month"), ``method`` ("no_data" |
        "constant" | "linear_trend"), ``periods_back`` (int), ``periods_ahead``
        (int), ``source_periods`` (list of ``{period, count}`` oldest->newest),
        ``projected_open_count`` (int | None; the next period), ``projected``
        (list of ``{period, count|None}``, ``periods_ahead`` entries),
        ``limitations`` (str), ``stronger_method`` (str).

        Method
        ------
        Arithmetic; see :func:`_project_counts` (least-squares linear
        extrapolation, clamped at 0, rounded to the nearest integer). No ML and
        no external dependencies.

        Limitations / Step 4
        --------------------
        See module-level ``_LIMITATIONS`` and ``_STRONGER_METHOD``.
        """
        if periods_back < 1:
            raise ValueError("periods_back must be >= 1")
        if periods_ahead < 1:
            raise ValueError("periods_ahead must be >= 1")

        ref = as_of or datetime.now(timezone.utc)
        series = self._monthly_open_counts(periods_back, ref)
        result = _project_counts([count for _, count in series], periods_ahead)

        last_period = _shift_month(ref, 0)
        projected = [
            {
                "period": _period_key(_shift_month(last_period, step)),
                "count": value,
            }
            for step, value in enumerate(result["projected"], start=1)
        ]

        return {
            "tenant_id": self.tenant_id,
            "register": self.register,
            "measure": self.measure,
            "period": self.period,
            "method": result["method"],
            "periods_back": periods_back,
            "periods_ahead": periods_ahead,
            "source_periods": [{"period": key, "count": count} for key, count in series],
            "projected_open_count": projected[0]["count"] if projected else None,
            "projected": projected,
            "limitations": _LIMITATIONS,
            "stronger_method": _STRONGER_METHOD,
        }
