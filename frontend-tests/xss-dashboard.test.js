/**
 * 3C.1B — XSS escaping + dashboard integrity regression tests (F-P1-1, F-P2-2).
 *
 * Strategy: the escaping helpers shipped in public/js are pure top-level
 * function declarations, so this suite extracts and evaluates the ACTUAL
 * shipped implementations (not copies) and runs malicious vectors through
 * them. Wiring (sinks call the helpers; integrity guards exist) is asserted
 * statically against the shipped sources and labeled as such.
 *
 * Run: node frontend-tests/xss-dashboard.test.js (no browser, no network).
 */
'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', 'public');
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');

function extractFn(src, name) {
    const re = new RegExp(
        'function ' + name + '\\s*\\([^)]*\\)\\s*\\{[\\s\\S]*?\\n\\}'
    );
    const m = src.match(re);
    assert.ok(m, 'shipped helper not found: ' + name);
    return new Function(m[0] + '\nreturn ' + name + ';')();
}

const canCap = read('js/can_cap.js');
const dashboard = read('js/dashboard.js');
const spi = read('js/spi-dashboard.js');
const nhrc = read('js/nhrc-dashboard.js');
const ae = read('dashboard/ae-dashboard.html');

const escHtml = extractFn(canCap, 'escHtml');
const escText = extractFn(dashboard, 'escText');
const kpiCountDisplay = extractFn(dashboard, 'kpiCountDisplay');
const spiEscape = extractFn(spi, 'escapeHtml');

const VECTORS = [
    '<script>alert(1)</script>',
    '<img src=x onerror=alert(2)>',
    '"><svg onload=alert(3)>',
    "';alert(4);//",
    'Fish & Chips <b>bold</b>',
];

for (const [label, fn] of [['can_cap escHtml', escHtml], ['dashboard escText', escText], ['spi escapeHtml', spiEscape]]) {
    for (const v of VECTORS) {
        const out = fn(v);
        assert.ok(!out.includes('<script'), label + ' must neutralize script: ' + v);
        assert.ok(!out.includes('<img'), label + ' must neutralize tags: ' + v);
        assert.ok(!out.includes('<svg'), label + ' must neutralize svg: ' + v);
        assert.ok(out.includes('&lt;') || !v.includes('<'), label + ' must escape <: ' + v);
    }
    assert.strictEqual(fn(null), '', label + ' null -> empty');
    assert.strictEqual(fn(undefined), '', label + ' undefined -> empty');
    assert.strictEqual(fn('plain CAN-2026-001'), 'plain CAN-2026-001', label + ' plain text untouched');
}
console.log('ok - escaping helpers neutralize markup, preserve plain text');

// ---- F-P1-1 wiring: every record-field sink must call the helper ----------

for (const field of ['c.can_reference', 'c.title', 'c.priority', 'c.status', 'c.assigned_to']) {
    assert.ok(canCap.includes('escHtml(' + field + ')'), 'can_cap sink must wrap ' + field);
}
assert.ok(canCap.includes('escHtml(err.message)'), 'can_cap error sink must wrap err.message');
for (const field of ['r.occurrence_type', 'r.location', 'r.status']) {
    assert.ok(dashboard.includes('escText(' + field + ')'), 'dashboard sink must wrap ' + field);
}
assert.ok(dashboard.includes('escText(riskLevel)'), 'dashboard sink must wrap riskLevel');
console.log('ok - CAN/CAP + report table sinks call escaping helpers (static)');

// ---- F-P2-2 functional: genuine zero vs failed response ---------------------

assert.strictEqual(kpiCountDisplay({ total: 0 }), 0, 'genuine zero stays 0');
assert.strictEqual(kpiCountDisplay({ total: 7 }), 7, 'count passes through');
assert.strictEqual(kpiCountDisplay(null), '—', 'failed response shows unavailable');
assert.strictEqual(kpiCountDisplay(undefined), '—', 'missing response shows unavailable');
assert.strictEqual(kpiCountDisplay({}), 0, 'successful response without total stays 0');
assert.ok(dashboard.includes('kpiCountDisplay(vsr)') && dashboard.includes('kpiCountDisplay(mor)'),
    'loadKpis must use kpiCountDisplay for VSR/MOR cards');
console.log('ok - zero-vs-unavailable display rule (functional)');

// ---- F-P2-2 static: outage must not render all-clear ------------------------

assert.ok(ae.includes('gLoadErrors'), 'ae-dashboard must track load failures');
assert.ok(ae.includes('Data unavailable'), 'ae-dashboard must render unavailable state');
assert.ok(ae.includes("'Unknown'"), 'ae-dashboard banner must support Unknown chips');
assert.ok(spi.includes('markEstimatedTrend'), 'spi trend must mark estimated fallback');
assert.ok(spi.includes('Estimated trend'), 'spi estimated label present');
assert.ok(nhrc.includes('markIllustrativeTrend'), 'nhrc trend must mark illustrative data');
assert.ok(nhrc.includes('Illustrative trend'), 'nhrc illustrative label present');
assert.ok(dashboard.includes('markDemoFallback'), 'safety dashboard must label demo fallback');
assert.ok(dashboard.includes('Demo data'), 'demo-only label present');
console.log('ok - outage/estimated/demo markers present (static)');

console.log('\nAll 3C.1B frontend checks passed.');
