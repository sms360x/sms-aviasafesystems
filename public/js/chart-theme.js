/* ============================================================================
   FILE: chart-theme.js
   PATH: public/js/chart-theme.js
   PURPOSE: ICAO Clean Light chart theming. Forces Chart.js grid lines to
            #d7e4dc and axis/label text to #53685c regardless of inline chart
            options, so every chart matches the locked light design system.
   LOAD AFTER: chart.js (chart.umd.min.js). No-op when Chart is unavailable.
   AUTHOR: AviaSAFE Systems
   ============================================================================ */

(function () {
    if (typeof Chart === 'undefined' || !Chart.defaults) return;

    if (Chart.defaults.scale) {
        if (Chart.defaults.scale.grid) {
            Chart.defaults.scale.grid.color = '#d7e4dc';
        }
        if (Chart.defaults.scale.ticks) {
            Chart.defaults.scale.ticks.color = '#53685c';
        }
    }
    Chart.defaults.color = '#53685c';
    if (Chart.defaults.font) {
        Chart.defaults.font.family = "'DM Sans', sans-serif";
    }
})();
