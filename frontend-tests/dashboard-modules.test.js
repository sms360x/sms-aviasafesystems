'use strict';
// Real browser DOM/layout with isolated auth/API/Chart adapters. No live services.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const repo = path.resolve(__dirname, '..');
(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 800}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    let html = fs.readFileSync(path.join(repo, 'public/dashboard/safety-manager.html'), 'utf8')
      .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<link\b[^>]*>/gi, '');
    await page.setContent(html);
    await page.addStyleTag({content: fs.readFileSync(path.join(repo, 'public/css/executive-ui.css'), 'utf8')});
    if (process.env.DASHBOARD_CHART_SOURCE) {
      await page.addScriptTag({content: fs.readFileSync(process.env.DASHBOARD_CHART_SOURCE, 'utf8')});
      await page.evaluate(() => { window.RealChart = window.Chart; });
    }
    await page.evaluate(() => {
      const content = document.createElement('main'); content.id = 'execContent';
      document.getElementById('pageContent').replaceWith(content);
      // Move the original dashboard content into the same shell host used in production.
      window.Chart = class {
        constructor(canvas, config) {
          if (!canvas.getBoundingClientRect().width) throw new Error('Hidden canvas');
          if (window.chartOwners.has(canvas)) throw new Error('Canvas already in use');
          this.canvas = canvas; this.config = config;
          this.real = window.RealChart ? new window.RealChart(canvas, config) : null;
          window.chartOwners.set(canvas, this);
        }
        destroy() { if (this.real) this.real.destroy(); window.chartOwners.delete(this.canvas); }
        resize() { if (this.real) this.real.resize(); } update() { if (this.real) this.real.update(); }
      };
      window.chartOwners = new Map();
      window.calls = [];
      window.ApiClient = {get: async function(url) {
        calls.push(url);
        if (window.delay && url.includes('/trends')) await new Promise(r => window.releaseTrend = r);
        if (window.fail && url.includes(window.fail)) throw new Error('Test failure');
        if (url.includes('/overview')) return {kpis: {high_risk_reports: 4, total_reports: 30}};
        if (url.includes('/sms-health')) return {overall_score: 72, tier: 'watch'};
        if (url.includes('/needs-attention')) return window.emptyAttention ? [] : [{message:'Review hazard', link:'#hazards'}];
        if (url.includes('/trends')) return window.empty ? [] : [{month:'10',year:2026,voluntary:16,mandatory:14}];
        if (url.includes('/key-issues')) return {items: []};
        if (url.includes('/action-completion')) return {total:21,overdue:2,pending_review:3,closed:4,on_track:12,due_within_30_days:0,no_due_date:0};
        return {};
      }};
    });
    // Restore markup after establishing the shell host.
    const body = html.match(/<div id="pageContent">([\s\S]*?)<\/body>/)[1].replace(/<\/div>\s*<footer[\s\S]*/, '');
    await page.evaluate(body => { document.getElementById('execContent').innerHTML = body; document.body.classList.add('shell-ready'); }, body);
    let source = fs.readFileSync(path.join(repo, 'public/js/dashboard-safety-manager.js'), 'utf8');
    source = source.slice(0, source.indexOf("    if (document.readyState === 'loading')")) +
      "window.testRoute = function(hash, days) { history.replaceState(null, '', '#' + hash); currentDays = days; applyRoute(); }; window.testPeriod = changePeriod;})();";
    await page.evaluate(source);
    const route = async (hash,days=90) => {await page.evaluate(([h,d]) => testRoute(h,d),[hash,days]); await page.waitForTimeout(25);};
    await route('dashboard');
    assert.equal(await page.locator('#s1-safety-reports').textContent(),'30');
    assert.equal(await page.locator('#dashboardBento > *').count(),1);
    assert.equal(await page.evaluate(() => calls.length),3);
    await route('dashboard/trends',0);
    assert.equal(await page.evaluate(() => calls.at(-1)),'/api/v1/dashboard/trends?days=0');
    assert.equal(await page.evaluate(() => chartOwners.size),1);
    assert.equal(await page.evaluate(() => __dashboardCharts.reportsTrend.config.data.datasets[0].data[0]),16);
    await route('dashboard/tasks');
    assert.equal(await page.locator('#dashboardBento h2').textContent(),'CAP Summary (Tenant-Wide)');
    for (const label of ['Overdue','Due ≤30d','On Track','Pending Review','Closed','Missing due date']) {
      assert.ok((await page.locator('#cap-summary-body').textContent()).includes(label));
    }
    assert.equal(await page.evaluate(() => chartOwners.size),0);
    assert.match(await page.locator('#dashboardBento').textContent(),/Tenant-wide CAP status as of now/);
    assert.equal(await page.locator('#dashboardBento a').getAttribute('href'),'#actions');
    await route('actions');
    assert.equal(await page.evaluate(() => chartOwners.size),1);
    assert.equal(await page.locator('#s5-donut-center').textContent(),'21');
    await page.evaluate(() => { delay = true; });
    await route('dashboard/trends');
    await route('dashboard/tasks');
    await page.evaluate(() => { releaseTrend(); delay = false; });
    await page.waitForTimeout(25);
    assert.equal(await page.evaluate(() => chartOwners.size),0);
    assert.equal(await page.locator('#cap-summary-body').count(),1);
    await page.evaluate(() => { fail = '/trends'; });
    await route('dashboard/trends');
    assert.match(await page.locator('#dashboardBento').textContent(),/Failed to load/);
    await page.evaluate(() => { fail = ''; empty = true; });
    await page.evaluate(() => testPeriod(30));
    await page.waitForTimeout(25);
    assert.match(await page.locator('#dashboardBento').textContent(),/No data/);
    await page.evaluate(() => { empty = false; window.mountedSection = document.querySelector('#dashboardBento > *'); testPeriod(0); });
    await page.waitForTimeout(25);
    assert.equal(await page.evaluate(() => mountedSection === document.querySelector('#dashboardBento > *')),true);
    assert.equal(await page.evaluate(() => calls.at(-1)),'/api/v1/dashboard/trends?days=0');
    assert.equal(await page.evaluate(() => chartOwners.size),1);
    await page.setViewportSize({width:390,height:844});
    const width = await page.locator('#dashboardBento > *').evaluate(el => el.getBoundingClientRect().width);
    const hostWidth = await page.locator('#dashboardBento').evaluate(el => el.getBoundingClientRect().width);
    assert.ok(width > 0 && Math.abs(width-hostWidth) < 100);
    await route('hazards');
    assert.equal(await page.evaluate(() => chartOwners.size),0);
    assert.match(await page.locator('#hazardsView').textContent(),/Hazards/);
    await route('dashboard');
    assert.equal(await page.locator('#s1-safety-reports').textContent(),'30');
    await page.evaluate(() => { fail = '/needs-attention'; testPeriod(30); });
    await page.waitForTimeout(25);
    assert.equal(await page.locator('#attention-banner-container').isVisible(),false);
    assert.ok(!(await page.locator('#attention-banner-container').textContent()).includes('All clear'));
    await page.evaluate(() => { fail = ''; emptyAttention = true; testPeriod(0); });
    await page.waitForTimeout(25);
    assert.equal(await page.locator('#attention-banner-container').isVisible(),false);
    assert.deepEqual(errors,[]);
    console.log('dashboard modules: browser lifecycle, scoped fetches, All Time, CAP placement, stale response, retry, mobile and legacy route checks passed');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode=1;});
