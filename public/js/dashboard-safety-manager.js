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

        // Card 4: Overdue Actions
        var actionsEl = document.getElementById('s1-action-completion');
        var actionsNote = document.getElementById('s1-action-completion-note');
        if (actionRes && actionRes.ok && actionRes.data) {
            var overdue = actionRes.data.overdue || 0;
            actionsEl.textContent = overdue;
            actionsNote.textContent = overdue > 0 
                ? 'high priority items' 
                : 'No overdue actions';
        } else {
            actionsEl.textContent = '0';
            actionsNote.textContent = 'No overdue actions';
        }

        // Card 5: Regulatory Compliance (static until Compliance module exists)
        var complianceEl = document.getElementById('s1-compliance');
        var complianceNote = document.getElementById('s1-compliance-note');
        complianceEl.textContent = 'On Track';
        complianceNote.textContent = 'No open State Regulator findings';
    }
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

    function renderTrends(trends) {
        var body = document.getElementById('s3-body');
        if (!body) return;
        if (!trends || !trends.ok || !Array.isArray(trends.data)) {
            renderEmpty('s3-body', 'Failed to load', trends && trends.reason ? trends.reason : 'trends unavailable');
            return;
        }
        var rows = trends.data;
        if (!rows.length) {
            renderEmpty('s3-body', 'No data', 'No report trend data in period.');
            return;
        }
        var last = rows.slice(-3);
        var labels = last.map(function (m) { return monthName(m.month) + ' ' + m.year; });
        var values = last.map(function (m) { return m.total; });
        var canvas = document.getElementById('s3-reports-trend');
        if (canvas && window.Chart) {
            destroyChart('reportsTrend');
            charts.reportsTrend = new Chart(canvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Reports',
                        data: values,
                        borderColor: '#235a4b',
                        backgroundColor: 'rgba(35, 90, 75,0.12)',
                        fill: true,
                        tension: 0.25,
                        pointRadius: 3,
                        spanGaps: true
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
            });
        }
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
        }
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
            } catch (e) {
                window.location.href = '/login.html';
                return;
            }
            if (['SUPER_ADMIN', 'TENANT_ADMIN', 'SAFETY_OFFICER', 'STATE_SMD'].indexOf(role) === -1) {
                window.location.href = '/safety.html';
                return;
            }
            tenant = (tr.claims && tr.claims.tenant_id) || '';

            // Hardcoded executive navigation (SME reference; replaces legacy
            // nav-config.js role-based NAV_CONFIG).
            var flatNav = [
                // DASHBOARD
                { id: 'dashboard', label: 'Dashboard', href: '#dashboard', icon: 'fa-table-columns', section: 'Dashboard' },
                { id: 'reports', label: 'Reports', href: '#reports', icon: 'fa-file-lines' },

                // SAFETY
                { id: 'hazards', label: 'Hazards & Risks', href: '#hazards', icon: 'fa-triangle-exclamation', section: 'Safety' },
                { id: 'assurance', label: 'Safety Assurance', href: '#assurance', icon: 'fa-shield-halved' },
                { id: 'performance', label: 'Safety Performance', href: '#performance', icon: 'fa-chart-line' },
                { id: 'actions', label: 'Actions', href: '#actions', icon: 'fa-clipboard-check' },

                // REGULATORY
                { id: 'compliance', label: 'Compliance', href: '#compliance', icon: 'fa-scale-balanced', section: 'Regulatory' },

                // WORKSPACE
                { id: 'surveys', label: 'Surveys', href: '#surveys', icon: 'fa-square-poll-vertical', section: 'Workspace' },
                { id: 'meetings', label: 'Meetings', href: '#meetings', icon: 'fa-users' },
                { id: 'admin', label: 'Settings', href: '#admin', icon: 'fa-gear' }
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

            applyRoute();

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
                loadAll(tenant, 90);
                return;
            }

            DateRangeFilter.mount('#dateFilterContainer', {
                defaultDays: 90,
                onChange: function (days) {
                    // Spec #4e — same date window drives both the dashboard and
                    // the Reports table.
                    var route = (window.location.hash || '').replace(/^#/, '');
                    if (route === 'reports') {
                        renderReports(1);
                    } else {
                        loadAll(tenant, days);
                    }
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
        'surveys':     'surveysView',
        'meetings':    'meetingsView',
        'admin':       'adminView'
    };

    function applyRoute() {
        var hash = (window.location.hash || '#dashboard').replace(/^#/, '');
        var execContent = document.getElementById('execContent');
        if (!execContent) return;

        // 1. Ensure stub container exists inside execContent
        var stubContainer = document.getElementById('stubViews');
        if (!stubContainer) {
            stubContainer = document.createElement('div');
            stubContainer.id = 'stubViews';
            stubContainer.style.display = 'none';
            
            var routes = ['hazards', 'assurance', 'performance', 'actions',
                          'compliance', 'surveys', 'meetings', 'admin'];
            var titles = ['Hazards & Risks', 'Safety Assurance', 'Safety Performance',
                          'Actions', 'Compliance', 'Surveys', 'Meetings', 'Settings'];
            
            for (var i = 0; i < routes.length; i++) {
                var stub = document.createElement('div');
                stub.id = routes[i] + 'View';
                stub.className = 'route-stub';
                stub.style.display = 'none';
                stub.innerHTML = '<h1>' + titles[i] + '</h1><p>Coming Soon — under construction.</p>';
                stubContainer.appendChild(stub);
            }
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
        var dateFilter = document.getElementById('dateFilterContainer');
        if (dateFilter) dateFilter.style.display = 'none';
        
        stubContainer.style.display = 'none';
        var stubs = stubContainer.querySelectorAll('.route-stub');
        for (var j = 0; j < stubs.length; j++) {
            stubs[j].style.display = 'none';
        }

        // 3. Show target
        if (hash === 'dashboard' || !ROUTE_MAP[hash]) {
            if (dashHeader) dashHeader.style.display = '';
            if (dashBento) dashBento.style.display = '';
            if (dateFilter) dateFilter.style.display = 'flex';
        } else {
            var targetId = ROUTE_MAP[hash];
            var target = document.getElementById(targetId);
            if (target) {
                stubContainer.style.display = '';
                target.style.display = 'block';
                if (hash === 'reports') {
                    // The global DateRangeFilter drives the Reports window too.
                    if (dateFilter) dateFilter.style.display = 'flex';
                    renderReports(1);
                }
            }
        }

        setActiveNav(hash);
    }

    function setActiveNav(activeId) {
        var items = document.querySelectorAll('.exec-sidebar-nav a');
        for (var i = 0; i < items.length; i++) {
            var href = items[i].getAttribute('href') || '';
            var itemId = href.replace(/^#/, '').replace(/^.*safety-manager\.html.*$/, 'dashboard');
            if (itemId === activeId) {
                items[i].classList.add('active');
            } else {
                items[i].classList.remove('active');
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

    window.addEventListener('hashchange', applyRoute);

    async function loadAll(tenant, days) {
        if (days === undefined) days = 90;
        var tasks = {
            overview: ApiClient.get('/api/v1/dashboard/overview?days=' + days),
            smsHealth: ApiClient.get('/api/v1/dashboard/sms-health?days=' + days),
            trends: ApiClient.get('/api/v1/dashboard/trends?days=180'),
            riskMatrix: ApiClient.get('/api/v1/dashboard/risk-matrix'),
            keyIssues: ApiClient.get('/api/v1/dashboard/key-issues?days=90&limit=5'),
            actionCompletion: ApiClient.get('/api/v1/dashboard/action-completion'),
            recent: ApiClient.get('/api/v1/dashboard/recent?days=90&page=1&page_size=10')
        };
        if (tenant) {
            tasks.spi = ApiClient.get('/api/v1/spi/tenant/' + encodeURIComponent(tenant) + '/trend?months=12');
        }

        var keys = Object.keys(tasks);
        var settled = await Promise.allSettled(keys.map(function (k) { return tasks[k]; }));
        var results = {};
        settled.forEach(function (r, i) {
            results[keys[i]] = r.status === 'fulfilled'
                ? { ok: true, data: r.value }
                : { ok: false, reason: (r.reason && r.reason.message) || 'request failed' };
        });

        renderKpis(results.overview, results.smsHealth, results.actionCompletion);
        renderTrends(results.trends);
        renderRiskMatrix(results.riskMatrix);
        renderHazards(results.keyIssues);
        renderDonut(results.actionCompletion);
        renderSmsComponents(results.smsHealth);
        renderRecent(results.recent);
        renderSpis(results.spi, tenant);
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
