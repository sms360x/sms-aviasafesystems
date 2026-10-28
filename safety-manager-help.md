# SMS360X Safety Manager Dashboard — Data Source Help

This document maps every dashboard section to its data source and backend logic. It serves as a reference for developers and a help doc for prospective clients.

## Header Row
- **Title/Subtitle:** Static UI.
- **Date Filter:** Global filter (default: Last 90 days).

## Section 1: Top KPI Row
1. **SMS Health:** Derived from Survey Results (Model A). Endpoint: `/api/v1/dashboard/sms-health`.
2. **Significant Risks:** Count of hazards where `risk_level IN ('High', 'Extreme') AND status = 'Open'`. Endpoint: `/api/v1/dashboard/overview`.
3. **Safety Reports:** Count of reports in date range + trend vs previous period. Endpoint: `/api/v1/dashboard/overview`.
4. **Overdue Actions:** Count of CAPs where `due_date < today AND status != 'Closed'`. Endpoint: `/api/v1/dashboard/action-completion`.
5. **Regulatory Compliance:** Count of open findings where `regulator = 'STATE'`. Endpoint: `/api/v1/dashboard/overview`.

## Section 2: SMS Component Effectiveness (Model A Surveys)
- **Source:** Survey Results.
- **Logic:** Scores 0-100% for the 4 ICAO components (Policy, Risk, Assurance, Promotion) based on the latest survey module responses. Server aggregates Likert scale responses.

## Section 3: Top Safety Risks
- **Source:** Hazard/Risk Register.
- **Logic:** Top 5 risks ordered by `risk_index` DESC where `status = 'Open'`. Endpoint: `/api/v1/dashboard/key-issues`.

## Section 4: Safety Performance Trends (SPIs)
- **Source:** SPI Module.
- **Logic:** Monthly aggregated data for SPIs (Serious Incidents, Runway Incursions, Unstable Approaches). Endpoint: `/api/v1/spi/tenant/{tenant}/trend`.

## Section 5: Safety Reporting Overview
- **Source:** Reports Table.
- **Logic:** 
  - Total count & trend: `/api/v1/dashboard/overview`.
  - Bar chart (monthly): `/api/v1/dashboard/trends`.
  - Report sources: Group by `report_source` field.

## Section 6: Corrective Action Status (CANs & CAPs)
- **Source:** CAN/CAP Modules.
- **Logic:** Endpoint `/api/v1/dashboard/action-completion`. Server groups by status (Overdue, Due ≤ 30, On Track). **Server owns the math**.

## Section 7: Regulatory Compliance & Oversight
- **Source:** Compliance/Audit Module (State Regulator findings).
- **Logic:** Query `findings` where `regulator = 'STATE'`. Group by category (CAR-19, Internal Audit, Management Review) and status (Open, On Track).

## Section 8: Safety Culture & Engagement
- **Source:** Survey Results (Culture Module) + Reports Table (Voluntary Reports).
- **Logic:**
  - **Survey Score:** Average of "Safety Culture" survey module.
  - **Reporting Culture:** Count of voluntary reports (`is_voluntary = true`) vs previous period.
  - **Key Takeaway:** Server-side deterministic rule-based text generation based on scores/trends.

## Section 9: Matters Requiring Your Attention
- **Source:** Aggregation of Open CAPs + Open High Risks + Upcoming Audits.
- **Logic:** Server runs a "Decision Matrix" query returning pre-formatted action items with Priority, Issue, Status, Impact, Proposed Action, and Decision Date.
