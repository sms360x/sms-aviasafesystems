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

    // ─── Corrective-action donut bucketing ──────────────────────────────────
    function isClosed(item) {
        var s = String(item.status || '').toLowerCase();
        return s === 'closed' || s === 'completed';
    }

    function bucketItem(item) {
        if (isClosed(item)) return 'Closed';
        var tcd = item.target_completion_date;
        if (tcd) {
            var d = new Date(tcd);
            if (!isNaN(d.getTime())) {
                var today = new Date();
                today.setHours(0, 0, 0, 0);
                var diffDays = (d.getTime() - today.getTime()) / 86400000;
                if (diffDays < 0) return 'Overdue';
                if (diffDays <= 30) return 'Due \u226430d';
            }
        }
        return 'On Track';
    }

    // ─── Section renderers ─────────────────────────────────────────────────

    function renderKpis(overview, smsHealth) {
        renderSmsHealth(smsHealth);
        var s1 = document.getElementById('s1-body');
        if (!s1) return;
        if (!overview || !overview.ok || !overview.data) {
            renderEmpty('s1-body', 'Failed to load', overview && overview.reason ? overview.reason : 'overview unavailable');
            return;
        }
        var kpis = overview.data.kpis || {};
        var org = overview.data.org_kpis || {};

        var totalReports = kpis.total_reports;
        var highRisks = kpis.high_risk_reports;

        var closed = org.corrective_actions_closed || 0;
        var open = org.corrective_actions_open || 0;
        var total = closed + open;
        var completion = total > 0 ? Math.round(closed / total * 100) + '%' : '\u2014';

        var trend = kpis.reporting_rate_trend;

        setText('s1-safety-reports', totalReports == null ? '\u2014' : String(totalReports));
        setText('s1-high-risks', highRisks == null ? '\u2014' : String(highRisks));
        setText('s1-action-completion', completion);

        var trendEl = document.getElementById('s1-safety-reports-trend');
        if (trendEl) {
            if (trend == null) { trendEl.textContent = '\u2014'; trendEl.className = 'exec-kpi-trend flat'; }
            else { trendEl.textContent = String(trend); trendEl.className = 'exec-kpi-trend flat'; }
        }
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
        var severities = data.severity_scale.slice().sort(function (a, b) { return a.value - b.value; });
        var probabilities = data.probability_scale.slice().sort(function (a, b) { return b.value - a.value; });
        var counts = {};
        (data.cells || []).forEach(function (c) {
            counts[c.probability + '|' + c.severity] = Number(c.count) || 0;
        });

        var html = '<div class="exec-risk-axis-label"></div>';
        severities.forEach(function (s) {
            html += '<div class="exec-risk-axis-label">' + esc(s.label) + '</div>';
        });
        probabilities.forEach(function (p) {
            html += '<div class="exec-risk-axis-label">' + esc(p.label) + '</div>';
            severities.forEach(function (s) {
                var count = counts[p.value + '|' + s.value] || 0;
                var cls = String(s.label || '').toLowerCase();
                var title = p.label + ' \u00d7 ' + s.label + ': ' + count + ' hazard' + (count === 1 ? '' : 's');
                html += '<div class="exec-risk-cell ' + esc(cls) + '" title="' + esc(title) + '">' + count + '</div>';
            });
        });
        el.innerHTML = html;
        if (caption) {
            caption.textContent = (data.total == null ? 0 : data.total) + ' hazard' +
                (data.total === 1 ? '' : 's') + ' plotted by severity and probability.';
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

    function renderDonut(cansResult, capsResult) {
        var cans = (cansResult && cansResult.ok) ? (cansResult.data || []) : null;
        var caps = (capsResult && capsResult.ok) ? (capsResult.data || []) : null;
        if (cans === null || caps === null) {
            var reason = (cansResult && !cansResult.ok) ? cansResult.reason : ((capsResult && !capsResult.ok) ? capsResult.reason : 'request failed');
            renderEmpty('s5-body', 'Failed to load', reason);
            return;
        }
        var items = (cans || []).concat(caps || []);
        var order = ['Overdue', 'Due \u226430d', 'On Track', 'Closed'];
        var colors = { 'Overdue': '#dc2626', 'Due \u226430d': '#d97706', 'On Track': '#16a34a', 'Closed': '#475569' };
        var counts = { 'Overdue': 0, 'Due \u226430d': 0, 'On Track': 0, 'Closed': 0 };
        items.forEach(function (item) { counts[bucketItem(item)]++; });
        var values = order.map(function (k) { return counts[k]; });
        var total = values.reduce(function (a, b) { return a + b; }, 0);

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
                { id: 'dashboard', label: 'Dashboard', href: '/dashboard/safety-manager.html', icon: 'fa-table-columns', section: 'Dashboard' },
                { id: 'reports', label: 'Reports', href: '#', icon: 'fa-file-lines' },

                // SAFETY
                { id: 'hazards', label: 'Hazards & Risks', href: '#', icon: 'fa-triangle-exclamation', section: 'Safety' },
                { id: 'assurance', label: 'Safety Assurance', href: '#', icon: 'fa-shield-halved' },
                { id: 'performance', label: 'Safety Performance', href: '#', icon: 'fa-chart-line' },
                { id: 'actions', label: 'Actions', href: '#', icon: 'fa-clipboard-check' },

                // REGULATORY
                { id: 'compliance', label: 'Compliance', href: '#', icon: 'fa-scale-balanced', section: 'Regulatory' },
                { id: 'articles', label: 'Articles & Advisories', href: '#', icon: 'fa-newspaper' },

                // WORKSPACE
                { id: 'surveys', label: 'Surveys', href: '#', icon: 'fa-square-poll-vertical', section: 'Workspace' },
                { id: 'meetings', label: 'Meetings', href: '#', icon: 'fa-users' },
                { id: 'documents', label: 'Documents', href: '#', icon: 'fa-folder-open' },
                { id: 'admin', label: 'Administration', href: '#', icon: 'fa-gear' }
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

            loadAll(tenant);
        });
    }

    async function loadAll(tenant) {
        var tasks = {
            overview: ApiClient.get('/api/v1/dashboard/overview'),
            smsHealth: ApiClient.get('/api/v1/dashboard/sms-health?days=365'),
            trends: ApiClient.get('/api/v1/dashboard/trends?days=180'),
            riskMatrix: ApiClient.get('/api/v1/dashboard/risk-matrix'),
            keyIssues: ApiClient.get('/api/v1/dashboard/key-issues?days=90&limit=5'),
            cans: ApiClient.get('/api/v1/cans/'),
            caps: ApiClient.get('/api/v1/cans/caps'),
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

        renderKpis(results.overview, results.smsHealth);
        renderTrends(results.trends);
        renderRiskMatrix(results.riskMatrix);
        renderHazards(results.keyIssues);
        renderDonut(results.cans, results.caps);
        renderRecent(results.recent);
        renderSpis(results.spi, tenant);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
