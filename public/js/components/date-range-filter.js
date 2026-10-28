// SMS360X Reusable Date-Range Filter
// Usage: DateRangeFilter.mount('#dateFilterContainer', {
//     defaultDays: 90,
//     onChange: function(days) { ... }
// });
(function () {
    'use strict';

    var STORAGE_KEY = 'sms360x_date_range_days';
    var OPTIONS = [
        { value: 30,  label: 'Last 30 days',  short: '30 days' },
        { value: 60,  label: 'Last 60 days',  short: '60 days' },
        { value: 90,  label: 'Last 90 days',  short: '90 days' },
        { value: 120, label: 'Last 120 days', short: '120 days' },
        { value: 150, label: 'Last 150 days', short: '150 days' },
        { value: 180, label: 'Last 180 days', short: '180 days' },
        { value: 365, label: 'Last 365 days', short: '365 days' },
        { value: 0,   label: 'All Time',       short: 'All Time' }
    ];

    var DateRangeFilter = {
        mount: function (containerSelector, opts) {
            var container = document.querySelector(containerSelector);
            if (!container) {
                console.warn('[DateRangeFilter] Container not found:', containerSelector);
                return;
            }
            opts = opts || {};
            var stored = null;
            try { stored = parseInt(localStorage.getItem(STORAGE_KEY), 10); } catch (e) {}
            var current = !isNaN(stored) ? stored : (opts.defaultDays !== undefined ? opts.defaultDays : 90);

            container.innerHTML = '';
            var wrap = document.createElement('div');
            wrap.className = 'date-range-filter';
            wrap.innerHTML =
                '<label class="drf-label" for="drf-select">Period:</label>' +
                '<select id="drf-select" class="drf-select" aria-label="Date range">' +
                OPTIONS.map(function (o) {
                    return '<option value="' + o.value + '"' + (o.value === current ? ' selected' : '') + '>' + o.label + '</option>';
                }).join('') +
                '</select>';
            container.appendChild(wrap);

            var select = wrap.querySelector('#drf-select');
            select.addEventListener('change', function () {
                var days = parseInt(this.value, 10);
                try { localStorage.setItem(STORAGE_KEY, String(days)); } catch (e) {}
                if (typeof opts.onChange === 'function') {
                    opts.onChange(days);
                }
            });

            // Fire initial callback so caller can sync state
            if (typeof opts.onChange === 'function') {
                opts.onChange(current);
            }
        },

        getCurrentDays: function () {
            try {
                var v = parseInt(localStorage.getItem(STORAGE_KEY), 10);
                return isNaN(v) ? 90 : v;
            } catch (e) { return 90; }
        }
    };

    window.DateRangeFilter = DateRangeFilter;
})();
