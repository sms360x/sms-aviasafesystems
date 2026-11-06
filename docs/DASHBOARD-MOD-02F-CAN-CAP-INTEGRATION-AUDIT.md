# DASHBOARD-MOD-02F CAN/CAP Integration Audit

## Endpoint map (from source)
- CAN list: GET /api/can-cap/ (can_cap router)
- CAN detail: GET /api/can-cap/{id}
- CAP submit: POST /api/can-cap/caps
- CAP list: GET /api/can-cap/caps (likely)

## Workflow
- Safety issues CAN with responsible department.
- Department users view filtered CANs via backend tenant/department scope.
- can_detail launches cap_submit with can_id.
- CAP submission retains help drawer.

## Empty CAN Register
- Likely cause: department mismatch or tenant/demo isolation; verify backend returns records for user's department. UNVERIFIED live.

## Authorization/isolation
- Firebase claims + backend get_current_user; department scope enforced.

## Minimal plan
- Reuse existing endpoints/pages; no new endpoints unless needed.

## Blockers
- None identified statically; runtime verification required.