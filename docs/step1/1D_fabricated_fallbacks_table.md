# 1D — Fabricated / Placeholder Fallback Values

Read-only. Date: 2026-10-08. Backs plan item 1D.9.
These are values rendered to a user that are **not** derived from operator registers (synthetic, hardcoded, or non-functional). Each must be removed or explicitly labelled in a later item.

| Value / block | Page(s) | Where produced | Type | Citation |
|---|---|---|---|---|
| Safety-culture SPI score (70–80) | spi-dashboard.html | `SPIService._culture_fallback` — hash-derived synthetic score when no survey scores exist | fabricated value | `backend/app/services/spi_service.py:661-666` |
| SPI 6-month trend chart | spi-dashboard.html | client generates a deterministic synthetic series when `/spi/tenant/{id}/trend` returns empty | placeholder | `public/js/spi-dashboard.js:212-234` |
| N-HRC "Last 6 Months" trend chart | nhrc-kpis.html | client pseudo-random series derived from hazard counts; comment says "Demo trend data" | placeholder | `public/js/nhrc-dashboard.js:35-42,148-178` |
| SSM Risk Trend chart (demo tenants) | safety.html | hardcoded demo series when API empty and tenant ∈ {fixedwing, rotarywing, demoairport} | placeholder | `public/js/dashboard.js:496-509` |
| Hazard Occurrence Frequency chart (demo tenants) | safety.html | hardcoded demo hazards when API empty for demo tenants | placeholder | `public/js/dashboard.js:541-555` |
| AE "Decision Required" scenario banner | ae-dashboard.html | set to literal `'Assessed'` (`:678`) | placeholder | `public/dashboard/ae-dashboard.html:678` |
| Top-hazards aggregation `trend` | regulator shares | hardcoded `[{"period": "Last 90d", ...}]` | placeholder | `backend/app/services/aggregation_service.py:169` |
| Hazard-analysis tolerability index ("4D — Tolerable") | hazard-analysis.html | hardcoded in markup (`:79`) | placeholder | `public/hazard-analysis.html:79` |
| Hazard-analysis HFACS/nanocode dropdowns | hazard-analysis.html | hardcoded `<option>` lists; "Save" button has no handler | placeholder / non-functional | `public/hazard-analysis.html:88-108` |
| PSOE Appendix-10 checklist template | psoe-audit.html | static seed file (reference, legitimately static) | demo-seeded (reference) | `backend/app/data/psoe_appendix10.json` via `psoe_service.py:68` |
| NASP N-HRC reference text (SEIs / contributing factors) | nhrc-kpis.html | hardcoded draft constant (code notes "validate against official NASP") | demo-seeded (reference) | `backend/app/services/nhrc_service.py:22-154,18-19` |
| Department badge | dept-master-register.html | client-derived from claims/email | placeholder | `public/dashboard/dept-master-register.html:186-188` |

Notes:
- "Reference / static" values (PSOE template, NASP text) are legitimately static reference data, not fabricated operator output; they are listed for completeness but are not the 1D.9 concern.
- The 1D.9 concern is the **fabricated operator-facing measured values**: the synthetic culture score, the synthetic trend charts, and the literal scenario banner.
