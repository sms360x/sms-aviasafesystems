-- Spec #21a — Database Indexing for Dashboard KPIs
-- Apply via Supabase SQL Editor. Idempotent (IF NOT EXISTS).
-- Covers the tenant_isolated + date/status/type filters the
-- dashboard overview, sms-health, needs-attention and trends
-- endpoints perform on every (first-load, cache-miss) request.

-- ─────────────────────────────────────────────────────────────
-- reports: tenant isolation + occurrence_date (overview KPIs, trends)
-- ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_reports_tenant_date
    ON reports (tenant_id, occurrence_date);

-- ─────────────────────────────────────────────────────────────
-- reports: tenant + status / type (KPI counts, reports table filters)
-- ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_reports_tenant_status
    ON reports (tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_reports_tenant_type
    ON reports (tenant_id, report_type);

-- ─────────────────────────────────────────────────────────────
-- hazards: tenant + risk_level + status (significant-risks KPI)
--          tenant + occurrence_date (date-range filters)
-- ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_hazards_tenant_risk_status
    ON hazards (tenant_id, risk_level, status);

CREATE INDEX IF NOT EXISTS idx_hazards_tenant_date
    ON hazards (tenant_id, occurrence_date);

-- ─────────────────────────────────────────────────────────────
-- action_items: tenant + status + due_date (overdue-action alerts)
-- ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_action_items_tenant_status_due
    ON action_items (tenant_id, status, due_date);

-- ─────────────────────────────────────────────────────────────
-- surveys / survey_responses: tenant + submitted_at
-- (SMS maturity aggregation, response counters)
-- ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_surveys_tenant_submitted
    ON surveys (tenant_id, submitted_at);

CREATE INDEX IF NOT EXISTS idx_survey_responses_tenant_submitted
    ON survey_responses (tenant_id, submitted_at);
