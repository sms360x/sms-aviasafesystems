/* ============================================================================
   FILE: dashboard-safety-manager.js
   PATH: public/js/dashboard-safety-manager.js
   PURPOSE: Safety Manager dashboard boot + render. Uses the executive sidebar
            shell (ExecutiveShell.init) and the ApiClient + Chart.js (per-page).
            Auth boot mirrors ae-dashboard.html (Firebase getIdTokenResult
            claims). No globals except window.ExecutiveShell (pre-existing).
   ============================================================================ */
(function () {
    'use strict';

    var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    var charts = {};
    // Monotonic generation for asynchronous data requests. Every route change
    // and every filter change starts a new generation, so responses
    // from an older generation can be rejected before they touch the DOM.
    var currentGeneration = 0;
    var currentTenant = '';
    var currentDays = 90;
    window.__dashboardCharts = charts;

    function esc(v) {
        return String(v == null ? '' : v)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function fmtDate(iso) {
        if (!iso) return '-';
        try { return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }); }
        catch (e) { return String(iso); }
    }

    function truncate(s, n) {
        s = String(s || '');
        return s.length > n ? s.slice(0, n - 1) + '\u2026' : s;
    }

    function monthName(m) {
        var n = parseInt(m, 10);
        return (n >= 1 && n <= 12) ? MONTHS[n - 1] : String(m);
    }

    function destroyChart(key) {
        if (charts[key]) { try { charts[key].destroy(); } catch (e) {} charts[key] = null; }
    }

    function renderEmpty(bodyId, title, note) {
        var el = document.getElementById(bodyId);
        if (!el) return;
        el.innerHTML = '<div class="exec-empty"><div class="exec-empty-title">' + esc(title) +
            '</div><div class="exec-empty-note">' + esc(note) + '</div></div>';
    }

    function renderTableEmpty(bodyId, msg) {
        var el = document.getElementById(bodyId);
        if (!el) return;
        el.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:1.5rem;color:var(--exec-text-muted);">' + esc(msg) + '</td></tr>';
    }

    function humanizeTenant(slug) {
        if (!slug) return '';
        return String(slug).replace(/-/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
    }

    function roleLabel(role) {
        var map = {
            'SUPER_ADMIN': 'Super Admin',
            'TENANT_ADMIN': 'Safety Manager',
            'SAFETY_OFFICER': 'Safety Officer',
            'STATE_SMD': 'State SMD'
        };
        return map[role] || role || 'User';
    }

    // ─── Section renderers ─────────────────────────────────────────────────


    function renderSmsHealth(smsHealth) {
        var val = document.getElementById('s1-sms-health');
        var tier = document.getElementById('s1-sms-health-tier');
        if (!val) return;
        var data = (smsHealth && smsHealth.ok) ? smsHealth.data : null;
        var score = data ? data.overall_score : null;
        if (score == null) {
            val.textContent = '\u2014';
            if (tier) {
                tier.textContent = smsHealth && !smsHealth.ok ? 'Unavailable' : 'No survey data';
                tier.className = 'exec-kpi-trend flat';
            }
            return;
        }
        val.textContent = Math.round(Number(score)) + '%';
        if (tier) {
            tier.textContent = data.tier_label || data.tier || '\u2014';
            tier.className = 'exec-kpi-trend flat';
        }
    }

    function setText(id, text) {
        var el = document.getElementById(id);
        if (el) el.textContent = text;
    }





    function renderSmsComponents(smsHealthResult) {
        var data = (smsHealthResult && smsHealthResult.ok) ? smsHealthResult.data : null;
        var statusEl = document.getElementById('s2b-survey-status');

        var pillars = [
            { key: 'safety_policy',           id: 'policy'    },
            { key: 'safety_risk_management',  id: 'risk'      },
            { key: 'safety_assurance',        id: 'assurance' },
            { key: 'safety_promotion',        id: 'promotion' }
        ];

        var bandColors = {
            green:  '#16a34a',
            yellow: '#d97706',
            red:    '#dc2626',
            empty:  '#d1d5db'
        };

        var hasSurvey = !!(data && Number(data.response_count) > 0);

        if (statusEl) {
            statusEl.textContent = hasSurvey ? '' : 'Last Survey Date: No Survey Data';
        }

        pillars.forEach(function (p) {
            var canvas  = document.getElementById('s2b-' + p.id + '-canvas');
            var center  = document.getElementById('s2b-' + p.id + '-center');
            var labelEl = document.getElementById('s2b-' + p.id + '-label');
            if (!canvas || !center || !labelEl) return;

            var pct  = hasSurvey && data.pillars ? data.pillars[p.key] : null;
            var band = hasSurvey && data.pillar_bands ? data.pillar_bands[p.key] : 'empty';
            var lbl  = hasSurvey && data.pillar_labels ? data.pillar_labels[p.key] : '—';

            if (pct == null) {
                center.textContent = '—';
                labelEl.textContent = '—';
                // Draw flat gray ring
                if (window.Chart) {
                    var existing = Chart.getChart(canvas);
                    if (existing) existing.destroy();
                    new Chart(canvas, {
                        type: 'doughnut',
                        data: { datasets: [{ data: [100], backgroundColor: [bandColors.empty], borderWidth: 0 }] },
                        options: { responsive: true, maintainAspectRatio: false, cutout: '75%', plugins: { legend: { display: false }, tooltip: { enabled: false } } }
                    });
                }
                return;
            }

            center.textContent = Math.round(Number(pct)) + '%';
            labelEl.textContent = lbl;

            if (window.Chart) {
                var existing2 = Chart.getChart(canvas);
                if (existing2) existing2.destroy();
                new Chart(canvas, {
                    type: 'doughnut',
                    data: { datasets: [{ data: [Number(pct), 100 - Number(pct)], backgroundColor: [bandColors[band] || bandColors.empty, '#e5e7eb'], borderWidth: 0 }] },
                    options: { responsive: true, maintainAspectRatio: false, cutout: '75%', plugins: { legend: { display: false }, tooltip: { enabled: false } } }
                });
            }
        });
    }

    function renderNeedsAttention(result) {
        var container = document.getElementById('s6-attention');
        if (!container) return;
        var banner = document.getElementById('attention-banner-container');
        var data = (result && result.ok) ? result.data : null;
        var items = Array.isArray(data) ? data : (data && data.items) || [];

        // Never show the green "All clear" state for a failed or empty fetch:
        // hide the banner unless the API returned actual attention items.
        if (!result || !result.ok || !items.length) {
            container.innerHTML = '';
            if (banner) {
                banner.setAttribute('data-has-data', '0');
                banner.style.display = 'none';
            }
            return;
        }

        if (banner) {
            banner.setAttribute('data-has-data', '1');
            var route = (window.location.hash || '#dashboard').replace(/^#/, '');
            var isDashboardRoute = route === 'dashboard' || route.indexOf('dashboard/') === 0 || !ROUTE_MAP[route];
            banner.style.display = isDashboardRoute ? '' : 'none';
        }

        container.innerHTML = items.map(function (it) {
            return '<div class="exec-alert-card" style="background:#fef2f2;border-left:4px solid #dc2626;padding:8px;margin-bottom:6px;">' +
                '<span>' + (it.message || '') + '</span> ' +
                '<a href="#" onclick="window.location.hash=\'' + (it.link || '#') + '\';return false;" style="color:#dc2626;font-weight:600;">View</a>' +
                '</div>';
        }).join('');
    }

    function renderRecent(recent) {
        var tbody = document.getElementById('s6-body');
        if (!tbody) return;
        if (!recent || !recent.ok || !recent.data) {
            renderTableEmpty('s6-body', 'Failed to load \u2014 ' + (recent && recent.reason ? recent.reason : 'recent unavailable'));
            return;
        }
        var items = (recent.data.items) || [];
        if (!items.length) {
            renderTableEmpty('s6-body', 'No recent reports.');
            return;
        }
        tbody.innerHTML = items.map(function (r) {
            var date = fmtDate(r.created_at || r.occurrence_date);
            var type = esc(r.report_type || '\u2014');
            var desc = esc(truncate(r.narrative || '', 80));
            var status = esc(r.status || '\u2014');
            return '<tr><td>' + date + '</td><td>' + type + '</td><td>' + desc + '</td><td>' + status + '</td></tr>';
        }).join('');
    }

    function renderSpis(spi, tenantId) {
        var body = document.getElementById('s8-body');
        if (!body) return;
        if (!tenantId) {
            renderEmpty('s8-body', 'Not yet wired', 'Tenant unavailable for SPI trends.');
            return;
        }
        if (!spi || !spi.ok || !Array.isArray(spi.data)) {
            renderEmpty('s8-body', 'Failed to load', spi && spi.reason ? spi.reason : 'SPI trends unavailable');
            return;
        }
        var rows = spi.data;
        if (!rows.length) {
            renderEmpty('s8-body', 'No data', 'No SPI trend data for this tenant.');
            return;
        }
        var labels = rows[0].months || [];
        var palette = ['#235a4b', '#16a34a', '#d97706', '#dc2626', '#7c3aed', '#477969', '#ca8a04', '#53685c'];
        var datasets = rows.map(function (row, i) {
            return {
                label: row.name,
                data: row.values || [],
                borderColor: palette[i % palette.length],
                backgroundColor: 'transparent',
                tension: 0.25,
                pointRadius: 2,
                spanGaps: true
            };
        });
        var canvas = document.getElementById('s8-spi-trend');
        if (canvas && window.Chart) {
            destroyChart('spi');
            charts.spi = new Chart(canvas, {
                type: 'line',
                data: { labels: labels, datasets: datasets },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 10 } } } } }
            });
        }
    }

    // ─── Boot ──────────────────────────────────────────────────────────────

    function boot() {
        if (typeof firebase === 'undefined' || !firebase.auth) {
            window.location.href = '/login.html';
            return;
        }
        firebase.auth().onAuthStateChanged(async function (user) {
            if (!user) { window.location.href = '/login.html'; return; }
            var tr, role, tenant;
            try {
                tr = await user.getIdTokenResult();
                role = (tr.claims && tr.claims.role) || 'USER';
                // Store the ID token for API calls (surveys donuts)
                window.__idToken = await user.getIdToken();
            } catch (e) {
                window.location.href = '/login.html';
                return;
            }
            if (['SUPER_ADMIN', 'TENANT_ADMIN', 'SAFETY_OFFICER', 'STATE_SMD'].indexOf(role) === -1) {
                window.location.href = '/dashboard/safety-manager.html';
                return;
            }
            tenant = (tr.claims && tr.claims.tenant_id) || '';
            currentTenant = tenant;

            // Hardcoded executive navigation (SME reference; replaces legacy
            // nav-config.js role-based NAV_CONFIG).
            var flatNav = [
                // Home section — all items are sub-items
                { id: 'dashboard', label: 'KPIs', href: '#dashboard', icon: 'fa-table-columns', section: 'Home', parent: 'home' },
                { id: 'dashboard-tasks', label: 'My Tasks & Approvals', href: '#dashboard/tasks', icon: 'fa-clipboard-check', parent: 'home' },
                { id: 'dashboard-trends', label: 'Reports Trend', href: '#dashboard/trends', icon: 'fa-chart-line', parent: 'home' },
                { id: 'dashboard-issues', label: 'Key Safety Issues', href: '#dashboard/issues', icon: 'fa-triangle-exclamation', parent: 'home' },

                // SMS MATURITY
                { id: 'surveys', label: 'SMS Survey', href: '#surveys', icon: 'fa-square-poll-vertical', section: 'SMS Maturity' },

                // SAFETY RISK MANAGEMENT
                { id: 'reports', label: 'Reports', href: '#reports', icon: 'fa-file-lines', section: 'Safety Risk Management' },
                { id: 'hazards', label: 'Hazards & Risks', href: '#hazards', icon: 'fa-triangle-exclamation' },
                { id: 'actions', label: 'Actions', href: '#actions', icon: 'fa-clipboard-check' },

                // WORKSPACE
                { id: 'data-management', label: 'Data Management', href: '#data-management', icon: 'fa-database', section: 'Workspace' },
                { id: 'admin', label: 'Settings', href: '#settings', icon: 'fa-gear' },
                { id: 'audit', label: 'Audit &amp; Inspection', href: '#audit', icon: 'fa-clipboard-list' }
            ];

            if (window.ExecutiveShell && typeof window.ExecutiveShell.init === 'function') {
                window.ExecutiveShell.init({
                    brand: 'SMS360X',
                    role: roleLabel(role),
                    tenant: humanizeTenant(tenant),
                    activeNav: 'dashboard',
                    nav: flatNav
                });
            }

            // Initial route is loaded by the period filter callback.

            // Re-apply route on hash change (tab clicks, back/forward)
            if (!window.__hashListenerWired) {
                window.__hashListenerWired = true;
                window.addEventListener('hashchange', function () {
                    applyRoute();
                });
            }

            // Spec #4e — Reports type filter (VSR/MOR): reset to page 1 on change.
            var reportsTypeFilter = document.getElementById('reports-type-filter');
            if (reportsTypeFilter && !reportsTypeFilter.dataset.wired) {
                reportsTypeFilter.dataset.wired = '1';
                reportsTypeFilter.addEventListener('change', function () {
                    renderReports(1);
                });
            }
            var reportsStatusFilter = document.getElementById('reports-status-filter');
            if (reportsStatusFilter && !reportsStatusFilter.dataset.wired) {
                reportsStatusFilter.dataset.wired = '1';
                reportsStatusFilter.addEventListener('change', function () {
                    renderReports(1);
                });
            }

            if (!window.__sms360x_loaded) {
                window.__sms360x_loaded = true;
            }

            if (typeof window.DateRangeFilter === 'undefined') {
                console.error('[Boot] DateRangeFilter component not loaded. ' +
                    'Falling back to default 90-day load.');
                applyRoute();
                return;
            }

            DateRangeFilter.mount('#dateFilterContainer', {
                defaultDays: 90,
                onChange: function (days) {
                    changePeriod(days);
                }
            });
        });
    }

    // ============================================================
    // HASH ROUTER (dashboard / stub views)
    // ============================================================
    var ROUTE_MAP = {
        'reports':     'reportsView',
        'hazards':     'hazardsView',
        'assurance':   'assuranceView',
        'performance': 'performanceView',
        'actions':     'actionsView',
        'compliance':  'complianceView',
        'surveys':          'surveysView',
        'meetings':         'meetingsView',
        'admin':            'adminView',
        'data-management':  'dataManagementView',
        'audit':            'auditView'
    };

    var currentModule = null;
    var moduleTemplates = null;

    function captureModuleTemplates() {
        if (moduleTemplates) return;
        var bento = document.getElementById('dashboardBento');
        moduleTemplates = {};
        ['s1', 's3', 's4', 's7'].forEach(function (id) {
            var section = bento.querySelector('[data-section="' + id + '"]');
            moduleTemplates[id] = section.outerHTML;
        });
        bento.innerHTML = '';
    }

    function makeModule(section, title, requests, render) {
        var root;
        var contentTemplate;
        return {
            mount: function (container) {
                container.innerHTML = section;
                root = container.firstElementChild;
                root.style.display = '';
                root.classList.add('exec-solo-view');
                var status = document.createElement('div');
                status.className = 'module-status';
                status.setAttribute('role', 'status');
                root.prepend(status);
                root.style.gridColumn = '1 / -1';
                root.style.minWidth = '0';
                contentTemplate = root.innerHTML;
                document.querySelector('#dashboardHeader h1').textContent = title;
            },
            load: async function (ctx) {
                destroyChart('reportsTrend');
                destroyChart('donut');
                root.innerHTML = contentTemplate;
                var status = root.querySelector('.module-status');
                status.textContent = 'Loading…';
                var paths = requests(ctx);
                var keys = Object.keys(paths);
                // Independent requests render individually; one slow service cannot
                // hold the other KPI cards hostage.
                var results = {};
                await Promise.all(keys.map(async function (key) {
                    try {
                        var data = await ApiClient.get(paths[key]);
                        if (data == null) throw new Error('No response');
                        results[key] = { ok: true, data: data };
                    } catch (error) {
                        results[key] = { ok: false, reason: error.message };
                    }
                    if (ctx.generation !== currentGeneration) return;
                    try { render(results); } catch (error) {
                        status.textContent = 'Unable to display this information. Select this menu again to retry.';
                        console.error('[Dashboard module]', error);
                        return;
                    }
                    var failed = Object.keys(results).some(function (k) { return !results[k].ok; });
                    status.textContent = failed ? 'Some information could not be loaded. Select this menu again to retry.' :
                        (Object.keys(results).length === keys.length ? '' : 'Loading…');
                }));
            },
            dispose: function () {
                destroyChart('reportsTrend');
                destroyChart('donut');
                if (root) root.remove();
                root = null;
            }
        };
    }

    var MODULES;
    function initializeModules() {
        if (MODULES) return;
        // Rendering implementations owned by the modules below. Risk matrix is
        // preserved for the deferred Hazards module; it is not fetched this sprint.
        function renderKpis(overviewRes, smsHealthRes, actionRes) {
            // Card 1: SMS Health (uses overall_score, NOT score)
            var healthEl = document.getElementById('s1-sms-health');
            var healthTier = document.getElementById('s1-sms-health-tier');
            if (smsHealthRes && smsHealthRes.ok && smsHealthRes.data) {
                var score = smsHealthRes.data.overall_score;
                var tier = smsHealthRes.data.tier_label || smsHealthRes.data.tier || 'unknown';
                if (score !== undefined && score !== null) {
                    healthEl.textContent = Math.round(score) + '%';
                    healthTier.textContent = tier;
                } else {
                    healthEl.textContent = 'N/A';
                    healthTier.textContent = 'No survey data';
                }
            } else {
                healthEl.textContent = 'N/A';
                healthTier.textContent = 'No survey data';
            }

            // Card 2: Significant Risks (uses .kpis.high_risk_reports)
            var risksEl = document.getElementById('s1-high-risks');
            var risksNote = document.getElementById('s1-high-risks-note');
            if (overviewRes && overviewRes.ok && overviewRes.data && overviewRes.data.kpis) {
                var highRisks = overviewRes.data.kpis.high_risk_reports || 0;
                risksEl.textContent = highRisks;
                risksNote.textContent = highRisks > 0
                    ? 'require executive attention'
                    : 'No significant risks';
            } else {
                risksEl.textContent = '0';
                risksNote.textContent = 'No significant risks';
            }

            // Card 3: Safety Reports (uses .kpis.total_reports; honest trend)
            var reportsEl = document.getElementById('s1-safety-reports');
            var reportsTrend = document.getElementById('s1-safety-reports-trend');
            if (overviewRes && overviewRes.ok && overviewRes.data && overviewRes.data.kpis) {
                var total = overviewRes.data.kpis.total_reports || 0;
                var prev = overviewRes.data.kpis.previous_period_total;
                reportsEl.textContent = total;
                if (typeof prev === 'number' && prev > 0) {
                    var pct = Math.round(((total - prev) / prev) * 100);
                    var arrow = pct >= 0 ? '\u2191' : '\u2193';
                    reportsTrend.textContent = arrow + ' ' + Math.abs(pct) + '% vs previous period';
                    reportsTrend.className = 'exec-kpi-trend ' + (pct >= 0 ? 'trend-up' : 'trend-down');
                } else {
                    reportsTrend.textContent = 'vs previous period';
                    reportsTrend.className = 'exec-kpi-trend';
                }
            } else {
                reportsEl.textContent = '0';
                reportsTrend.textContent = 'vs previous period';
                reportsTrend.className = 'exec-kpi-trend';
            }

            // Card 4: Overdue Actions (element may be absent from some layouts)
            var actionsEl = document.getElementById('s1-action-completion');
            var actionsNote = document.getElementById('s1-action-completion-note');
            if (actionsEl) {
                if (actionRes && actionRes.ok && actionRes.data) {
                    var overdue = actionRes.data.overdue || 0;
                    actionsEl.textContent = overdue;
                    if (actionsNote) {
                        actionsNote.textContent = overdue > 0
                            ? 'high priority items'
                            : 'No overdue actions';
                    }
                } else {
                    actionsEl.textContent = 'Unavailable';
                    if (actionsNote) actionsNote.textContent = 'CAP data unavailable';
                }
            }

            // Card 5: Regulatory Compliance (static until Compliance module exists)
            var complianceEl = document.getElementById('s1-compliance');
            var complianceNote = document.getElementById('s1-compliance-note');
            complianceEl.textContent = 'On Track';
            complianceNote.textContent = 'No open State Regulator findings';
        }
        function renderTrends(trends) {
            var canvas = document.getElementById('s3-reports-trend');
            if (!canvas || !canvas.parentElement) {
                console.error('[renderTrends] Canvas not found, aborting');
                return;
            }
            if (!window.Chart) {
                console.error('[renderTrends] Chart.js not loaded, aborting');
                return;
            }
            if (!trends || !trends.ok || !Array.isArray(trends.data)) {
                renderEmpty('s3-body', 'Failed to load', trends && trends.reason ? trends.reason : 'trends unavailable');
                return;
            }
            var rows = trends.data;
            var rangeEl = document.getElementById('s3-trend-range');
            if (!rangeEl) {
                rangeEl = document.createElement('div');
                rangeEl.id = 's3-trend-range';
                rangeEl.style.cssText = 'font-size:12px;color:#6b7280;margin:4px 0 8px;';
                if (canvas && canvas.parentElement) canvas.parentElement.insertBefore(rangeEl, canvas);
            }
            if (rows.length) {
                var first = rows[0], last = rows[rows.length - 1];
                var firstLabel = (monthNames[parseInt(first.month, 10) - 1] || first.month) + ' ' + first.year;
                var lastLabel = (monthNames[parseInt(last.month, 10) - 1] || last.month) + ' ' + last.year;
                rangeEl.textContent = 'Period shown: ' + firstLabel + ' - ' + lastLabel + ' (monthly buckets; zero-report months shown as 0).';
            } else {
                rangeEl.textContent = '';
            }
            if (!rows.length) {
                renderEmpty('s3-body', 'No data', 'No report trend data in period.');
                return;
            }
            // Parse API response: [{month:"10", year:2026, voluntary:16, mandatory:14}, ...]
            var monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            var labels = [];
            var voluntaryData = [];
            var mandatoryData = [];
            rows.forEach(function (item) {
                var m = parseInt(item.month, 10) - 1;
                if (m >= 0 && m <= 11) {
                    labels.push(monthNames[m] + ' ' + item.year);
                } else {
                    labels.push(String(item.month) + ' ' + item.year);
                }
                voluntaryData.push(item.voluntary || 0);
                mandatoryData.push(item.mandatory || 0);
            });
            destroyChart('reportsTrend');
            charts.reportsTrend = new Chart(canvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'VSR',
                            data: voluntaryData,
                            borderColor: '#1E6B52',
                            backgroundColor: 'rgba(30, 107, 82, 0.12)',
                            fill: false,
                            tension: 0,
                            pointRadius: 4,
                            pointBackgroundColor: '#1E6B52',
                            spanGaps: false
                        },
                        {
                            label: 'MOR',
                            data: mandatoryData,
                            borderColor: '#EF4444',
                            backgroundColor: 'rgba(239, 68, 68, 0.12)',
                            fill: false,
                            tension: 0.4,
                            pointRadius: 4,
                            pointBackgroundColor: '#EF4444',
                            spanGaps: true
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: true, position: 'top' },
                        tooltip: { mode: 'index', intersect: false }
                    },
                    scales: {
                        y: { beginAtZero: true, ticks: { precision: 0 } },
                        x: { offset: true, grid: { display: false } }
                    }
                }
            });
            charts.reportsTrend.resize();
            charts.reportsTrend.update();
        }
        function renderRiskMatrix(riskMatrix) {
            var el = document.getElementById('s2-matrix');
            var caption = document.getElementById('s2-caption');
            if (!el) return;
            var data = (riskMatrix && riskMatrix.ok) ? riskMatrix.data : null;
            if (!data || !data.severity_scale || !data.probability_scale) {
                el.innerHTML = '<div class="exec-empty" style="grid-column:1 / -1;">' +
                    '<div class="exec-empty-title">Failed to load</div>' +
                    '<div class="exec-empty-note">' + esc(riskMatrix && riskMatrix.reason ? riskMatrix.reason : 'risk matrix unavailable') + '</div></div>';
                if (caption) caption.textContent = '\u2014';
                return;
            }
            // ICAO Doc 9859 orientation: Y-axis severity Catastrophic (A) -> Negligible (E),
            // X-axis probability Frequent (5) -> Extremely Improbable (1).
            var severities = data.severity_scale.slice().sort(function (a, b) { return b.value - a.value; });
            var probabilities = data.probability_scale.slice().sort(function (a, b) { return b.value - a.value; });
            var cells = {};
            (data.cells || []).forEach(function (c) {
                cells[c.probability + '|' + c.severity] = c;
            });
            var letters = { 5: 'A', 4: 'B', 3: 'C', 2: 'D', 1: 'E' };

            var html = '<div class="exec-risk-axis-label"></div>';
            probabilities.forEach(function (p) {
                html += '<div class="exec-risk-axis-label exec-risk-axis-x">' +
                    esc(p.label) + ' (' + esc(p.value) + ')</div>';
            });
            severities.forEach(function (s) {
                var letter = s.letter || letters[s.value] || '';
                html += '<div class="exec-risk-axis-label exec-risk-axis-y">' +
                    esc(s.label) + ' (' + esc(letter) + ')</div>';
                probabilities.forEach(function (p) {
                    var cell = cells[p.value + '|' + s.value] || {};
                    var count = Number(cell.count) || 0;
                    var index = cell.risk_index || (String(p.value) + letter);
                    var tolerability = cell.tolerability || 'Unclassified';
                    var cls = String(tolerability).toLowerCase();
                    var title = index + ' \u2014 ' + p.label + ' \u00d7 ' + s.label +
                        ' (' + tolerability + '): ' + count + ' hazard' + (count === 1 ? '' : 's');
                    html += '<div class="exec-risk-cell ' + esc(cls) + (count === 0 ? ' is-empty' : '') +
                        '" title="' + esc(title) + '">' +
                        '<span class="exec-risk-index">' + esc(index) + '</span>' +
                        '<span class="exec-risk-count">' + count + '</span></div>';
                });
            });
            el.innerHTML = html;
            if (caption) {
                var total = Number(data.total) || 0;
                caption.textContent = total + ' hazard' + (total === 1 ? '' : 's') +
                    ' plotted on the ICAO Doc 9859 tolerability grid.';
            }
        }
        function renderHazards(keyIssues) {
            var tbody = document.getElementById('s4-body');
            if (!tbody) return;
            var data = (keyIssues && keyIssues.ok) ? keyIssues.data : null;
            if (!data) {
                renderTableEmpty('s4-body', 'Failed to load \u2014 ' + (keyIssues && keyIssues.reason ? keyIssues.reason : 'key issues unavailable'));
                return;
            }
            var items = Array.isArray(data) ? data : (data.items || []);
            if (!items.length) {
                renderTableEmpty('s4-body', 'No hazard data in period.');
                return;
            }
            var trendLabel = { rising: '\u25b2 Rising', falling: '\u25bc Falling', flat: '\u25cf Flat' };
            tbody.innerHTML = items.slice(0, 5).map(function (h) {
                var label = h.occurrence_type || h.category || '\u2014';
                var trend = h.trend_direction || h.trend;
                return '<tr><td>' + esc(label) + '</td><td>' + esc(h.count == null ? '\u2014' : String(h.count)) +
                    '</td><td>' + esc(trendLabel[trend] || '\u2014') + '</td></tr>';
            }).join('');
        }
        function renderDonut(actionCompletion) {
            var data = (actionCompletion && actionCompletion.ok) ? actionCompletion.data : null;
            if (!data) {
                renderEmpty('s5-body', 'Failed to load',
                    actionCompletion && actionCompletion.reason ? actionCompletion.reason : 'action completion unavailable');
                return;
            }
            // Server-side CAP state machine (human-in-the-loop): no date math here.
            var order = ['Overdue', 'Due \u226430d', 'On Track', 'Pending Review', 'Closed', 'Missing due date'];
            var colors = {
                'Overdue': '#dc2626',
                'Due \u226430d': '#d97706',
                'On Track': '#16a34a',
                'Pending Review': '#235a4b',
                'Closed': '#53685c',
                'Missing due date': '#83938a'
            };
            var counts = {
                'Overdue': Number(data.overdue) || 0,
                'Due \u226430d': Number(data.due_within_30_days) || 0,
                'On Track': Number(data.on_track) || 0,
                'Pending Review': Number(data.pending_review) || 0,
                'Closed': Number(data.closed) || 0,
                'Missing due date': Number(data.no_due_date) || 0
            };
            var values = order.map(function (k) { return counts[k]; });
            var sum = values.reduce(function (a, b) { return a + b; }, 0);
            var total = (data.total == null) ? sum : (Number(data.total) || 0);

            var center = document.getElementById('s5-donut-center');
            if (center) center.textContent = String(total);

            var legend = document.getElementById('s5-donut-legend');
            if (legend) {
                legend.innerHTML = order.map(function (k) {
                    return '<div class="exec-legend-item"><span class="exec-donut-legend-swatch" style="background:' + colors[k] + ';"></span><span>' + esc(k) + '</span><span style="margin-left:auto;font-weight:600;">' + counts[k] + '</span></div>';
                }).join('');
            }

            var canvas = document.getElementById('s5-donut-canvas');
            if (canvas && window.Chart) {
                    destroyChart('donut');
                charts.donut = new Chart(canvas, {
                    type: 'doughnut',
                    data: {
                        labels: order,
                        datasets: [{ data: values, backgroundColor: order.map(function (k) { return colors[k]; }), borderWidth: 0 }]
                    },
                    options: { responsive: true, maintainAspectRatio: false, cutout: '65%', plugins: { legend: { display: false } } }
                });
                charts.donut.resize();
                charts.donut.update();
            }
        }
        captureModuleTemplates();
        var capNote = '<p>Tenant-wide CAP status as of now. The period filter does not apply. Department tasks and approvals are not included.</p>';
        MODULES = {
            'kpis': makeModule(moduleTemplates.s1, 'Safety Manager Dashboard', function (ctx) {
                return { overview: '/api/v1/dashboard/overview?days=' + ctx.days,
                    health: '/api/v1/dashboard/sms-health?days=' + ctx.days,
                    attention: '/api/v1/dashboard/needs-attention?days=' + ctx.days };
            }, function (r) {
                renderKpis(r.overview, r.health);
                renderNeedsAttention(r.attention);
                if (!r.overview || !r.overview.ok) {
                    setText('s1-high-risks', '—'); setText('s1-high-risks-note', 'Unavailable');
                    setText('s1-safety-reports', '—'); setText('s1-safety-reports-trend', 'Unavailable');
                }
                if (!r.health || !r.health.ok) {
                    setText('s1-sms-health', '—'); setText('s1-sms-health-tier', 'Unavailable');
                }
                setText('s1-compliance', '—');
                setText('s1-compliance-note', 'Compliance data is not connected');
            }),
            // TEMPORARY: will be replaced by /api/v1/dashboard/my-tasks/summary (Safety Department scope) next sprint.
            'tasks-summary': makeModule('<section class="exec-card"><h2>CAP Summary (Tenant-Wide)</h2>' + capNote +
                '<div id="cap-summary-body"></div><a href="#actions">View full CAP status summary</a></section>',
                'CAP Summary (Tenant-Wide)', function () { return { cap: '/api/v1/dashboard/action-completion' }; }, function (r) {
                    var data = r.cap && r.cap.ok ? r.cap.data : null;
                    var buckets = [
                        ['Overdue', 'overdue'], ['Due ≤30d', 'due_within_30_days'],
                        ['On Track', 'on_track'], ['Pending Review', 'pending_review'],
                        ['Closed', 'closed'], ['Missing due date', 'no_due_date']
                    ];
                    document.getElementById('cap-summary-body').innerHTML = data ?
                        '<dl>' + buckets.map(function (bucket) {
                            return '<div class="exec-legend-item"><dt>' + bucket[0] + '</dt><dd>' +
                                esc(data[bucket[1]] == null ? '—' : data[bucket[1]]) + '</dd></div>';
                        }).join('') + '</dl>' : '<p>CAP summary unavailable.</p>';
                }),
            'trends': makeModule(moduleTemplates.s3, 'Reports Trend', function (ctx) {
                return { trends: '/api/v1/dashboard/trends?days=' + ctx.days };
            }, function (r) { renderTrends(r.trends); }),
            'issues': makeModule(moduleTemplates.s4, 'Key Safety Issues', function (ctx) {
                return { issues: '/api/v1/dashboard/key-issues?days=' + ctx.days + '&limit=5' };
            }, function (r) { renderHazards(r.issues); }),
            'actions': makeModule(moduleTemplates.s7
                .replace('href="#dashboard/tasks"', 'href="/can_cap/caps.html"')
                .replace('<div class="exec-card-body"', capNote + '<div class="exec-card-body"'),
                'Actions — CAP Status Summary', function () { return { cap: '/api/v1/dashboard/action-completion' }; },
                function (r) { renderDonut(r.cap); })
        };
    }

    function applyRoute() {
        var hash = (window.location.hash || '#dashboard').replace(/^#/, '');
        var execContent = document.getElementById('execContent');
        if (!execContent) return;
        if (currentModule) currentModule.dispose();
        ++currentGeneration;
        currentModule = null;
        initializeModules();
        var banner = document.getElementById('attention-banner-container');
        banner.style.display = 'none';
        banner.setAttribute('data-has-data', '0');
        var routeModules = { dashboard: 'kpis', 'dashboard/tasks': 'tasks-summary',
            'dashboard/trends': 'trends', 'dashboard/issues': 'issues', actions: 'actions' };
        var name = routeModules[hash];
        if (!name && !ROUTE_MAP[hash]) { hash = 'dashboard'; name = 'kpis'; }
        if (!name) { showLegacyRoute(hash, execContent); return; }
        var reports = document.getElementById('reportsView');
        if (reports) reports.style.display = 'none';
        var stubs = document.getElementById('stubViews');
        if (stubs) stubs.style.display = 'none';
        var host = document.getElementById('dashboardBento');
        host.style.display = '';
        document.getElementById('dashboardHeader').style.display = '';
        currentModule = MODULES[name];
        currentModule.mount(host);
        setActiveNav(hash);
        currentModule.load({ tenant: currentTenant, days: currentDays, generation: currentGeneration });
    }

    function changePeriod(days) {
        currentDays = days;
        if (!currentModule) {
            // Bootstrap, or preserve the filter behavior of out-of-scope routes.
            applyRoute();
            return;
        }
        ++currentGeneration;
        var banner = document.getElementById('attention-banner-container');
        if (banner) banner.style.display = 'none';
        currentModule.load({ tenant: currentTenant, days: currentDays, generation: currentGeneration });
    }

    function showLegacyRoute(hash, execContent) {
        // 1. Ensure stub container exists inside execContent
        var stubContainer = document.getElementById('stubViews');
        if (!stubContainer) {
            stubContainer = document.createElement('div');
            stubContainer.id = 'stubViews';
            stubContainer.style.display = 'none';

            var routes = ['hazards', 'assurance', 'performance', 'actions',
                          'compliance', 'surveys', 'meetings', 'admin', 'data-management', 'audit'];
            var titles = ['Hazards & Risks', 'Safety Assurance', 'Safety Performance',
                          'Actions', 'Compliance', 'SMS Survey Maturity', 'Meetings', 'Settings', 'Data Management'];

            for (var i = 0; i < routes.length; i++) {
                var stub = document.createElement('div');
                stub.id = routes[i] + 'View';
                stub.className = 'route-stub';
                stub.style.display = 'none';

                // Surveys page gets the 2x2 donut grid, not "Coming Soon"
                if (routes[i] === 'surveys') {
                    stub.innerHTML = buildSurveysView();
                } else {
                    stub.innerHTML = '<h1>' + titles[i] + '</h1><p>Coming Soon — under construction.</p>';
                }
                stubContainer.appendChild(stub);
            }
            var dmView = document.getElementById('data-managementView');
            if (dmView) dmView.innerHTML = '<h1>Data Management</h1><p>Data Management: Upload via ETLx Studio and Download Live Data coming soon.</p>';
            var auditView = document.getElementById('auditView');
            if (auditView) auditView.innerHTML = '<h1>Audit & Inspection</h1><p>Last Audit Date: —</p><p>Next Audit Date: —</p>';
            execContent.appendChild(stubContainer);
        }

        // Spec #4e — Reparent hand-written views out of the hidden dashboard container
        var reportsView = document.getElementById('reportsView');
        if (reportsView && reportsView.parentElement !== stubContainer) {
            stubContainer.appendChild(reportsView);
        }

        // 2. Hide ALL views (dashboard children + stubs) — NOT execContent itself
        var dashHeader = execContent.querySelector('.exec-page-header');
        var dashBento = execContent.querySelector('.exec-bento');
        if (dashHeader) dashHeader.style.display = 'none';
        if (dashBento) dashBento.style.display = 'none';

        // Attention banner: visible ONLY when we have real attention data.
        var attentionBanner = document.getElementById('attention-banner-container');
        if (attentionBanner) attentionBanner.style.display = 'none';

        stubContainer.style.display = 'none';
        var stubs = stubContainer.querySelectorAll('.route-stub, #' + routesOrIds().join(', #'));
        for (var j = 0; j < stubs.length; j++) {
            stubs[j].style.display = 'none';
        }

            var targetId = ROUTE_MAP[hash];
            var target = document.getElementById(targetId);
            if (target) {
                stubContainer.style.display = '';
                target.style.display = 'block';
                if (hash === 'reports') {
                    renderReports(1);
                } else if (hash === 'surveys') {
                    loadSmsHealthDonuts();
                }
            }
        setActiveNav(hash);
    }

    // Helper to get all route view IDs for hiding
    function routesOrIds() {
        return Object.values(ROUTE_MAP);
    }

    // ─── Surveys Donut Page ────────────────────────────────────────────────
    function buildSurveysView() {
        var pillars = [
            { id: 'safety_policy', label: 'Safety Policy & Objectives' },
            { id: 'safety_risk_management', label: 'Safety Risk Management' },
            { id: 'safety_assurance', label: 'Safety Assurance' },
            { id: 'safety_promotion', label: 'Safety Promotion' }
        ];

        var html = '<div style="padding: 24px 0;">';
        html += '<h2 style="font-size:1.3rem;font-weight:700;margin-bottom:4px;">SMS Maturity — ICAO SSP Pillars</h2>';
        html += '<p style="color:#6b7280;font-size:0.9rem;margin-bottom:20px;">Aggregated from safety culture survey responses.</p>';
        html += '<div class="donut-grid">';
        for (var i = 0; i < pillars.length; i++) {
            html += '<div class="donut-card" id="donut-' + pillars[i].id + '">';
            html += '<h3>' + pillars[i].label + '</h3>';
            html += '<div class="donut-canvas-wrap"><canvas id="canvas-' + pillars[i].id + '"></canvas></div>';
            html += '<div class="donut-score" id="score-' + pillars[i].id + '">—</div>';
            html += '</div>';
        }
        html += '</div></div>';
        return html;
    }

    function loadSmsHealthDonuts() {
        var days = 90;
        // Try to read the current DateRangeFilter value
        if (window.DateRangeFilter && typeof DateRangeFilter.getCurrentDays === 'function') {
            days = DateRangeFilter.getCurrentDays();
        }
        var apiBase = '';
        if (window.APP_CONFIG && window.APP_CONFIG.apiBaseUrl) {
            apiBase = window.APP_CONFIG.apiBaseUrl;
        } else if (window.API_BASE_URL) {
            apiBase = window.API_BASE_URL;
        }

        fetch(apiBase + '/api/v1/dashboard/sms-health?days=' + days, {
            headers: { 'Authorization': 'Bearer ' + (window.__idToken || '') }
        })
        .then(function (r) { return r.json(); })
        .then(function (resp) {
            renderDonuts(resp && resp.data ? resp.data : null);
        })
        .catch(function (err) {
            console.warn('[Surveys] sms-health fetch failed:', err);
            renderDonuts(null);
        });
    }

    function renderDonuts(data) {
        var pillars = ['safety_policy', 'safety_risk_management', 'safety_assurance', 'safety_promotion'];
        var colors = ['#235a4a', '#2e7d6b', '#3da68f', '#5bc4a8'];

        for (var i = 0; i < pillars.length; i++) {
            var pid = pillars[i];
            var score = (data && data.pillars && data.pillars[pid] != null) ? data.pillars[pid] : null;
            var scoreEl = document.getElementById('score-' + pid);
            if (scoreEl) scoreEl.textContent = score != null ? Math.round(score) + '%' : '—';

            var canvas = document.getElementById('canvas-' + pid);
            if (!canvas || !window.Chart) continue;

            if (charts['donut_' + pid]) {
                charts['donut_' + pid].destroy();
            }

            // Render center-text plugin for each donut
            var centerTextPlugin = {
                id: 'centerText',
                afterDraw: function (chart) {
                    var ctx = chart.ctx;
                    var area = chart.chartArea;
                    var cx = (area.left + area.right) / 2;
                    var cy = (area.top + area.bottom) / 2;
                    var val = score != null ? Math.round(score) : null;
                    ctx.save();
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    if (val != null) {
                        ctx.font = '700 22px system-ui, sans-serif';
                        ctx.fillStyle = '#235a4a';
                        ctx.fillText(val + '%', cx, cy - 6);
                        ctx.font = '500 11px system-ui, sans-serif';
                        ctx.fillStyle = '#6b7280';
                        ctx.fillText('Achieved', cx, cy + 12);
                    } else {
                        ctx.font = '600 14px system-ui, sans-serif';
                        ctx.fillStyle = '#9ca3af';
                        ctx.fillText('No data', cx, cy);
                    }
                    ctx.restore();
                }
            };

            charts['donut_' + pid] = new Chart(canvas, {
                type: 'doughnut',
                data: {
                    labels: ['Achieved', 'Gap'],
                    datasets: [{
                        data: score != null ? [score, 100 - score] : [0, 100],
                        backgroundColor: [colors[i], '#e5e7eb'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '70%',
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function (ctx) {
                                    return ctx.label + ': ' + Math.round(ctx.parsed) + '%';
                                }
                            }
                        }
                    }
                },
                plugins: [centerTextPlugin]
            });
        }
    }

    function setActiveNav(activeId) {
        var isSubRoute = (activeId && activeId.indexOf('dashboard/') === 0);
        var items = document.querySelectorAll('.exec-sidebar-nav a');
        for (var i = 0; i < items.length; i++) {
            var href = items[i].getAttribute('href') || '';
            var itemId = href.replace(/^#/, '').replace(/^.*safety-manager\.html.*$/, 'dashboard');
            items[i].classList.remove('active');

            if (isSubRoute) {
                // Sub-route active: highlight ONLY the matching sub-item, not parent
                if (itemId === activeId) {
                    items[i].classList.add('active');
                }
            } else {
                // Top-level dashboard (or other route): highlight only the matching item
                if (itemId === activeId) {
                    items[i].classList.add('active');
                }
            }
        }
    }

    function renderReports(page) {
        var body = document.getElementById('reports-body');
        var metaEl = document.getElementById('reports-pagination-meta');
        var pageInfo = document.getElementById('reports-page-info');
        var prevBtn = document.getElementById('reports-prev');
        var nextBtn = document.getElementById('reports-next');
        if (!body || !metaEl || !pageInfo || !prevBtn || !nextBtn) return;

        body.innerHTML = '<tr><td colspan="6" style="padding: 20px; text-align: center;">Loading reports...</td></tr>';
        prevBtn.disabled = true;
        nextBtn.disabled = true;

        var days = 90;
        if (window.DateRangeFilter && typeof window.DateRangeFilter.getCurrentDays === 'function') {
            days = DateRangeFilter.getCurrentDays();
        }
        // Backend accepts days 1..365; the filter's "All Time" (0) maps to the max.
        if (days === null || days === undefined) days = 90;
        if (days < 0) days = 0;
        if (days > 365) days = 365;

        // Spec #4e — VSR (voluntary) / MOR (mandatory) type filter.
        var typeEl = document.getElementById('reports-type-filter');
        var reportType = typeEl ? typeEl.value : '';
        if (reportType !== 'voluntary' && reportType !== 'mandatory') reportType = '';

        var statusEl = document.getElementById('reports-status-filter');
        var statusVal = statusEl ? statusEl.value : '';
        if (statusVal !== 'Open' && statusVal !== 'Closed') statusVal = '';

        var pageSize = 20;
        var path = '/api/v1/reports/?days=' + days + '&page=' + page + '&page_size=' + pageSize;
        if (reportType) path += '&report_type=' + encodeURIComponent(reportType);
        if (statusVal) path += '&status=' + encodeURIComponent(statusVal);

        (async function () {
            var token = await ApiClient._getToken();
            if (!token) {
                body.innerHTML = '<tr><td colspan="6" style="padding: 20px; text-align: center;">Not signed in.</td></tr>';
                return;
            }
            var tenantId = await ApiClient._getTenantId();
            var headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            };
            if (tenantId) headers['X-Tenant-Id'] = tenantId;

            var json;
            try {
                var res = await fetch(ApiClient._baseUrl() + path, { headers: headers });
                if (!res.ok) {
                    var err = await res.json().catch(function () { return {}; });
                    throw new Error(err.detail || 'Request failed: ' + res.status);
                }
                json = await res.json();
            } catch (e) {
                body.innerHTML = '<tr><td colspan="6" style="padding: 20px; text-align: center; color: #dc2626;">' + esc(e.message || 'Failed to load reports.') + '</td></tr>';
                return;
            }

            var items = json.data || [];
            var meta = json.meta || {};
            var total = Number(meta.total) || 0;
            var pages = Number(meta.pages) || (total > 0 ? Math.ceil(total / pageSize) : 0);

            if (items.length === 0) {
                body.innerHTML = '<tr><td colspan="6" style="padding: 20px; text-align: center;">No reports found.</td></tr>';
            } else {
                body.innerHTML = '';
                items.forEach(function (r) {
                    var typeLabel = String(r.report_type || '');
                    if (typeLabel) typeLabel = typeLabel.charAt(0).toUpperCase() + typeLabel.slice(1);
                    var riskScore = r.risk_score == null ? '—' : Number(r.risk_score).toFixed(1);
                    var tr = document.createElement('tr');
                    tr.innerHTML =
                        '<td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">' + esc(fmtDate(r.occurrence_date || r.created_at)) + '</td>' +
                        '<td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">' + esc(typeLabel) + '</td>' +
                        '<td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">' + esc(r.location || '—') + '</td>' +
                        '<td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">' + esc(r.status || '—') + '</td>' +
                        '<td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">' + esc(r.risk_level || '—') + '</td>' +
                        '<td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">' + esc(riskScore) + '</td>';
                    body.appendChild(tr);
                });
            }

            metaEl.textContent = total ? ('Showing ' + total + ' report' + (total === 1 ? '' : 's') + ', page ' + page + ' of ' + pages) : 'No reports';
            pageInfo.textContent = 'Page ' + page;
            prevBtn.disabled = page <= 1;
            nextBtn.disabled = page >= pages || total === 0;
            prevBtn.onclick = function () { renderReports(page - 1); };
            nextBtn.onclick = function () { renderReports(page + 1); };
        })();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }

    // Spec #4d — expose for router + console (fixes blank Reports page)
    window.renderReports = renderReports;
    window.fmtDate = fmtDate;
    window.esc = esc;
})();
