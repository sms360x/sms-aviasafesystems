"""1B.3 — RLS coverage test (configuration, not enforcement).

Asserts that every public table that is not a documented platform exemption
(or reference data) has Row-Level Security ENABLED. It deliberately does NOT
assert that RLS enforces tenant isolation on the application path: the backend
connects as the table owner with ``rls_forced = false``, and the live policies
read Supabase GoTrue claims that the Firebase app path never presents. That
bypass is documented in ``docs/step1/rls_bypass_finding.md`` and
``docs/step1/1B.2_rls_exemptions.md``; the enforcement assertion is skipped
with that reason (never silently passed).

Sources of truth:
  * live state: ``pg_class.relrowsecurity`` for schema ``public``.
  * classification constants below mirror ``docs/step1/1B.1_rls_inventory.md``
    (corrected by 1B.2: ``audit_dispatches`` is tenant-owned, not platform).
"""

import asyncio

import pytest
from sqlalchemy import text

from app.db.session import session_scope


# Platform infrastructure exempted from the RLS assertion (1B.2):
# dead_letter_queue has no tenant_id; sms_dispatches is dispatch infra with a
# dormant tenant_id and no tenant-facing read path.
PLATFORM_EXEMPTED = {
    "dead_letter_queue",
    "sms_dispatches",
}

# Tenant-owned tables with RLS enabled but zero policies — deferred to Step 2.
# The test asserts RLS is ENABLED for these; it does not assert a policy.
DEFERRED_NO_POLICIES = {
    "audit_dispatches",
    "feedback",
    "hazard_assessments",
    "hazard_capas",
    "hazard_rca_entries",
    "hazard_rca_factors",
    "invites",
    "psoe_findings",
}

# Static lookup/reference tables. They currently have RLS enabled (read
# policies), so the honest answer is to ASSERT enabled rather than exempt.
REFERENCE_TABLES = {
    "hfacs_nanocodes",
    "icao_adrep_taxonomies",
    "metric_definitions",
    "psoe_questions",
    # "regulators" removed 2A.3b-cleanup: regulators are now rows in `tenants`
    # (kind = 'regulator'), not a separate reference table.
    "state_risk_categories",
    "taxonomy_mappings",
}

# Tenant-owned operational tables (1B.1 inventory, corrected by 1B.2).
TENANT_OWNED = {
    "action_items",
    "audit_dispatches",
    "barrier_register",
    "bow_tie_analyses",
    "bow_tie_consequences",
    "bow_tie_controls",
    "bow_tie_threats",
    "caan_reports",
    "cans",
    "caps",
    "closures",
    "corrective_actions",
    "feedback",
    "flight_diversions",
    "hazard_adrep_mappings",
    "hazard_assessments",
    "hazard_capas",
    "hazard_hfacs_codes",
    "hazard_rca_entries",
    "hazard_rca_factors",
    "hazard_triage",
    "hazards",
    "import_batches",
    "import_links",
    "import_mappings",
    "import_rows",
    "invites",
    "module_c_aggregates",
    "psoe_assessments",
    "psoe_findings",
    "regulatory_reports",
    "report_adrep_mappings",
    "report_hfacs_codes",
    "reports",
    "risk_register",
    "safety_communications",
    "safety_deficiencies",
    "sag_meetings",
    "sms_maturity",
    "sram_risk_register",
    "srb_meetings",
    "state_risk_register",
    "state_safety_performance_targets",
    "survey_responses",
    "surveys",
    "users",
    "verifications",
}

ENFORCEMENT_SKIP_REASON = (
    "RLS is not enforced on the app path: the backend connects as the table "
    "owner with rls_forced=false and the live policies read Supabase GoTrue "
    "claims that the Firebase app path never presents. Configuration-only "
    "coverage. See docs/step1/rls_bypass_finding.md and "
    "docs/step1/1B.2_rls_exemptions.md."
)


def _run(coro):
    return asyncio.run(coro)


def _public_rls_state() -> dict:
    """Return {table_name: rls_enabled} for base tables in schema public."""

    async def _go():
        async with session_scope() as session:
            rows = (await session.execute(text(
                "SELECT c.relname, c.relrowsecurity "
                "FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind = 'r'"
            ))).all()
            return {r[0]: bool(r[1]) for r in rows}

    return _run(_go())


# ---------------------------------------------------------------------------
# Core coverage assertion
# ---------------------------------------------------------------------------

def test_every_non_exempt_public_table_has_rls_enabled():
    """A tenant-owned table added without RLS (or one whose RLS is disabled)
    fails this test, unless it is a documented platform exemption."""
    state = _public_rls_state()
    assert state, "no public tables returned from the live catalog"
    missing = sorted(
        t for t, rls in state.items()
        if not rls and t not in PLATFORM_EXEMPTED
    )
    assert not missing, f"public tables without RLS enabled: {missing}"


def test_every_tenant_owned_table_exists_and_has_rls_enabled():
    state = _public_rls_state()
    missing_tables = sorted(TENANT_OWNED - state.keys())
    assert not missing_tables, f"expected tenant-owned tables absent: {missing_tables}"
    without_rls = sorted(t for t in TENANT_OWNED if not state[t])
    assert not without_rls, f"tenant-owned tables without RLS enabled: {without_rls}"


def test_reference_tables_have_rls_enabled():
    state = _public_rls_state()
    assert REFERENCE_TABLES <= state.keys(), sorted(REFERENCE_TABLES - state.keys())
    without_rls = sorted(t for t in REFERENCE_TABLES if not state[t])
    assert not without_rls, f"reference tables without RLS enabled: {without_rls}"


def test_deferred_tables_have_rls_enabled():
    """Deferred tables must still be RLS-enabled; only their policies are
    deferred to Step 2. A disabled RLS here is a regression."""
    state = _public_rls_state()
    for table in sorted(DEFERRED_NO_POLICIES):
        assert table in state, f"deferred table missing: {table}"
        assert state[table] is True, f"deferred table RLS disabled: {table}"


def test_platform_exemptions_exist():
    state = _public_rls_state()
    assert PLATFORM_EXEMPTED <= state.keys(), sorted(PLATFORM_EXEMPTED - state.keys())


def test_classification_sets_are_disjoint():
    """Guard against a tenant-owned table being misfiled as exempt/reference,
    which would silently remove it from the RLS assertion."""
    assert TENANT_OWNED.isdisjoint(PLATFORM_EXEMPTED)
    assert TENANT_OWNED.isdisjoint(REFERENCE_TABLES)
    assert PLATFORM_EXEMPTED.isdisjoint(REFERENCE_TABLES)


# ---------------------------------------------------------------------------
# Enforcement is explicitly not asserted (documented skip)
# ---------------------------------------------------------------------------

def test_rls_enforcement_not_assertable_on_app_path():
    pytest.skip(ENFORCEMENT_SKIP_REASON)
