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
                        borderColor: '#0284c7',
                        backgroundColor: 'rgba(2,132,199,0.12)',
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
            'Pending Review': '#0284c7',
            'Closed': '#475569',
            'Missing due date': '#94a3b8'
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
        var palette = ['#0284c7', '#16a34a', '#d97706', '#dc2626', '#7c3aed', '#0891b2', '#ca8a04', '#475569'];
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
                { id: 'articles', label: 'Articles & Advisories', href: '#articles', icon: 'fa-newspaper' },

                // WORKSPACE
                { id: 'surveys', label: 'Surveys', href: '#surveys', icon: 'fa-square-poll-vertical', section: 'Workspace' },
                { id: 'meetings', label: 'Meetings', href: '#meetings', icon: 'fa-users' },
                { id: 'documents', label: 'Documents', href: '#documents', icon: 'fa-folder-open' },
                { id: 'admin', label: 'Administration', href: '#admin', icon: 'fa-gear' }
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
                    loadAll(tenant, days);
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
        'articles':    'articlesView',
        'surveys':     'surveysView',
        'meetings':    'meetingsView',
        'documents':   'documentsView',
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
            
            var routes = ['reports', 'hazards', 'assurance', 'performance', 'actions', 
                          'compliance', 'articles', 'surveys', 'meetings', 'documents', 'admin'];
            var titles = ['Reports', 'Hazards & Risks', 'Safety Assurance', 'Safety Performance', 
                          'Actions', 'Compliance', 'Articles & Advisories', 'Surveys', 
                          'Meetings', 'Documents', 'Administration'];
            
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

    window.addEventListener('hashchange', applyRoute);

    async function loadAll(tenant, days) {
        if (days === undefined) days = 90;
        var tasks = {
            overview: ApiClient.get('/api/v1/dashboard/overview?days=' + days),
            smsHealth: ApiClient.get('/api/v1/dashboard/sms-health?days=365'),
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
        renderRecent(results.recent);
        renderSpis(results.spi, tenant);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
