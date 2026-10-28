/* ============================================================================
   FILE: executive-shell.js
   PURPOSE: Sidebar + topbar executive layout. Extends shell.js — pages that
            opt in get the sidebar; others keep the current top-nav layout.
   USAGE: Load AFTER shell.js. Then call:
              ExecutiveShell.init({
                  brand: 'SMS360X',
                  role: 'Accountable Manager',
                  tenant: 'Tara Air',
                  activeNav: 'dashboard',
                  nav: [ { id, label, icon, href, section? }, ... ]
              });
   ============================================================================ */

window.ExecutiveShell = (function () {
    'use strict';

    var state = {
        brand: 'SMS360X', role: '', tenant: '', activeNav: '', nav: [], user: null
    };

    function esc(v) {
        return String(v == null ? '' : v)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function renderSidebar() {
        var html = '<aside class="exec-sidebar" id="execSidebar">';
        html += '<div class="exec-sidebar-brand">';
        html += '<img src="/images/sms360x-logo.png" alt="SMS360X" onerror="this.style.display=\'none\'">';
        html += '<span>' + esc(state.brand) + '</span>';
        html += '<button id="execSidebarToggle" class="exec-sidebar-toggle" aria-label="Toggle sidebar"><i class="fas fa-bars"></i></button>';
        html += '</div>';
        html += '<nav class="exec-sidebar-nav">';
        var lastSection = null;
        state.nav.forEach(function (item) {
            if (item.section && item.section !== lastSection) {
                html += '<div class="exec-nav-section">' + esc(item.section) + '</div>';
                lastSection = item.section;
            }
            var cls = 'exec-nav-item' + (item.id === state.activeNav ? ' active' : '');
            var icon = item.icon ? '<i class="fas ' + esc(item.icon) + '"></i>' : '';
            html += '<a href="' + esc(item.href || '#') + '" class="' + cls + '">' + icon + '<span>' + esc(item.label) + '</span></a>';
        });
        html += '</nav></aside>';
        return html;
    }

    function renderTopbar() {
        var tenantLabel = state.tenant ? '<div class="exec-topbar-tenant">' + esc(state.tenant) + '</div>' : '';
        var initial = (state.user && state.user.email ? state.user.email.charAt(0).toUpperCase() : 'U');
        return '<header class="exec-topbar">' +
            '<button type="button" class="exec-menu-toggle" onclick="ExecutiveShell.toggleSidebar()" style="background:none;border:none;font-size:1.2rem;cursor:pointer;color:#0b2a42;display:none;" aria-label="Toggle menu"><i class="fas fa-bars"></i></button>' +
            tenantLabel +
            '<div class="exec-topbar-search"><i class="fas fa-search"></i><input type="search" placeholder="Search safety insights..."></div>' +
            '<div class="exec-topbar-actions"><div class="exec-user-profile"><div class="exec-user-avatar">' + esc(initial) + '</div><span style="font-size:0.85rem;font-weight:600;color:#0b2a42;">' + esc(state.role || 'User') + '</span></div></div>' +
            '</header>';
    }

    function render() {
        var root = document.getElementById('execRoot');
        if (!root) {
            root = document.createElement('div');
            root.id = 'execRoot';
            document.body.appendChild(root);
        }
        document.body.classList.add('executive-layout');
        root.innerHTML = renderSidebar() +
            '<div class="exec-main">' + renderTopbar() +
            '<div class="exec-content" id="execContent"></div></div>';

        var target = document.getElementById('execContent');
        var existingPageContent = document.getElementById('pageContent');
        if (target && existingPageContent) {
            target.innerHTML = existingPageContent.innerHTML;
            existingPageContent.remove();
        }

        var toggle = document.querySelector('.exec-menu-toggle');
        if (toggle) {
            toggle.style.display = window.innerWidth <= 768 ? 'block' : 'none';
            window.addEventListener('resize', function () {
                toggle.style.display = window.innerWidth <= 768 ? 'block' : 'none';
            });
        }

        var toggleBtn = document.getElementById('execSidebarToggle');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', function() {
                document.body.classList.toggle('sidebar-collapsed');
            });
        }
    }

    function init(config) {
        Object.assign(state, config || {});
        try {
            if (typeof firebase !== 'undefined' && firebase.auth) {
                firebase.auth().onAuthStateChanged(function (user) {
                    if (user) {
                        state.user = { email: user.email };
                        var els = document.querySelectorAll('.exec-user-avatar');
                        if (els.length && user.email) els[0].textContent = user.email.charAt(0).toUpperCase();
                    }
                });
            }
        } catch (e) {}
        render();
    }

    function toggleSidebar() {
        var sb = document.getElementById('execSidebar');
        if (sb) sb.classList.toggle('open');
    }

    return { init: init, toggleSidebar: toggleSidebar };
})();
