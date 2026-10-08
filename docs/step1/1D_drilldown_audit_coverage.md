# 1D — Drill-down Audit Coverage

Read-only. Date: 2026-10-08. Plan item 1D.10.

## Questions and answers

**Is there a drill-down endpoint today?**
Yes — in `backend/app/routes/regulator_dashboard.py`:
- `POST /api/v1/regulator/share/escalate` (`:73-96`) — creates a temporary oversight grant.
- `GET /api/v1/regulator/share/escalate/{escalation_id}` (`:99-110`) — retrieves the grant.
- `GET /api/v1/regulator/share/benchmark/{tenant_id}` (`:50-70`) — per-tenant benchmark with tenant-match enforcement.

**Is every drill-down logged in `audit_logs`?**
- The regulator drill-down endpoints **are** audited: `caan_audit.log_caan_share` on create (`:94`, action `CAAN_SHARE_escalation`), `caan_audit.log_caan_escalated_read` on read (`:108`), and `log_caan_read`/`log_caan_share` on the other regulator routes. These write to Postgres `audit_logs` via `audit_service.log_audit` (`backend/app/services/caan_audit.py:20-63`).
- **But** the other state read surfaces are **not** audited: `/api/v1/state-risk/*` (`backend/app/routes/state_risk.py`, `backend/app/api/v1/state_risk.py`) and `/api/v1/nhrc/*` (`backend/app/api/v1/nhrc.py`) import no `caan_audit`. So "every drill-down/state read is logged" is **not** true today.

**Is it purpose-bound (tied to a specific oversight action)?**
- Partially. `EscalationRequest` carries `item_type`, `item_id`, `reason` (min length 5), and a time window (`window_hours`, default 24) — `regulator_dashboard.py:36-42`. The `reason` is free text; there is no FK to an oversight-action entity. So it is "purpose-declared", not tightly bound to a specific oversight record.

**Is it access-limited by role (STATE_SMD only)?**
- Yes. The drill-down endpoints depend on `get_caan_user` (`regulator_dashboard.py:75,100`), which requires a role in `settings.CROSS_TENANT_ROLES` = `["CAAN_SMD", "STATE_SMD", "SUPER_ADMIN"]` (`backend/app/middleware/auth.py:169-177`; `backend/app/core/config.py:175`). This includes STATE_SMD; it also allows SUPER_ADMIN.

**Is VSR anonymity preserved in the drill-down path?**
- Structurally yes: the grant's scope string is `"full_detail_minus_reporter_identity"` (`regulator_dashboard.py:91`), and the read returns the grant record itself (`:110`), not operator data. VSR reporter identity is not in the internal register, so drill-down cannot surface it — **provided** the underlying data has VSR identity redacted (see `1D_reporter_redaction_check.md`; that redaction is not wired today).

## Plain statement of what is missing
1. **Audit coverage is partial.** Only `/api/v1/regulator/*` writes CAAN read/drill-down audits; `/api/v1/state-risk/*` and `/api/v1/nhrc/*` do not. (Gap → item 1D.10.)
2. **Grants are in-memory and non-durable** (`_ESCALATIONS`, `regulator_dashboard.py:47`); lost on restart, never purged on expiry. (Gap → item 1D.8.)
3. **Purpose-binding is declarative** (free-text `reason`), not bound to an oversight-action record.
4. **VSR anonymity depends on redaction that is not yet wired** (see reporter-redaction check).

Documentation only; no code changed.
