'use strict';
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'public/login.html'), 'utf8');

const start = html.indexOf('function tenantMembershipError(user) {');
const end = html.indexOf('\n// ====', start);
const fnSrc = html.slice(start, end);

const storage = {};
global.window = {
    location: { hostname: 'sita.sms360x.com', search: '', pathname: '/login.html' },
    localStorage: { getItem: k => (k in storage ? storage[k] : null), setItem: (k,v)=>{storage[k]=String(v);}, removeItem: k=>{delete storage[k];} },
    sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
};
global.document = { readyState:'complete', addEventListener:()=>{}, createElement:()=>({style:{},appendChild:()=>{},addEventListener:()=>{}}), body:{appendChild:()=>{}} };
global.TenantResolver = { normalizeTenantId: x => x, getCurrentTenant: () => null, getDemoTenant: () => null };

const helpers = `
function isProductionHost() { return true; }
function getActiveTenant() { return global.__ACTIVE_TENANT || null; }
`;
const wrapped = helpers + '\n' + fnSrc + '\n; global.tenantMembershipError = tenantMembershipError;';
new Function('global', wrapped)(global);

function setHost(t){ global.window.location.hostname = t; global.__ACTIVE_TENANT = (t.indexOf('.')>=0) ? t.split('.')[0] : null; }
function setTenantResolver(map){ global.TenantResolver = { normalizeTenantId: x => (map && map[x]) || x }; }

let fails = 0;
function assert(cond, msg){ if(!cond){ console.log('FAIL: '+msg); fails++; } else { console.log('PASS: '+msg); } }

// Sita on Sita
setHost('sita.sms360x.com'); setTenantResolver({'sita':'sita-air'});
assert(global.tenantMembershipError({role:'TENANT_ADMIN', tenantId:'sita-air'}) === null, 'Sita on Sita allowed');
// Tara on Tara
setHost('tara.sms360x.com'); setTenantResolver({'tara':'tara-air'});
assert(global.tenantMembershipError({role:'TENANT_ADMIN', tenantId:'tara-air'}) === null, 'Tara on Tara allowed');
// Saurya on Saurya
setHost('saurya.sms360x.com'); setTenantResolver({'saurya':'saurya-airlines'});
assert(global.tenantMembershipError({role:'TENANT_ADMIN', tenantId:'saurya-airlines'}) === null, 'Saurya on Saurya allowed');
// Sita on Tara
setHost('tara.sms360x.com'); setTenantResolver({'tara':'tara-air'});
assert(global.tenantMembershipError({role:'TENANT_ADMIN', tenantId:'sita-air'}) !== null, 'Sita on Tara rejected');
// Tara on Saurya
setHost('saurya.sms360x.com'); setTenantResolver({'saurya':'saurya-airlines'});
assert(global.tenantMembershipError({role:'TENANT_ADMIN', tenantId:'tara-air'}) !== null, 'Tara on Saurya rejected');
// Prefix collision
setHost('sita.sms360x.com'); setTenantResolver({'sita':'sita-air'});
assert(global.tenantMembershipError({role:'TENANT_ADMIN', tenantId:'sita-airlines'}) !== null, 'prefix collision rejected');
// Unknown host
setHost('unknown.sms360x.com'); setTenantResolver({});
global.__ACTIVE_TENANT = null;
assert(global.tenantMembershipError({role:'TENANT_ADMIN', tenantId:'sita-air'}) === null, 'unknown host returns null (no scope)');
// Missing tenant identity
setHost('sita.sms360x.com'); setTenantResolver({'sita':'sita-air'});
assert(global.tenantMembershipError({role:'TENANT_ADMIN', tenantId:null}) !== null, 'missing tenant rejected');
// Message non-disclosing
setHost('tara.sms360x.com'); setTenantResolver({'tara':'tara-air'});
const msg = global.tenantMembershipError({role:'TENANT_ADMIN', tenantId:'sita-air'});
assert(msg && msg.indexOf('sita-air') === -1 && msg.indexOf('tara-air') === -1, 'message non-disclosing');

console.log(fails ? `\nRESULT: ${fails} FAILURES` : '\nRESULT: ALL ROUTE-02F-B CHECKS PASSED');
process.exit(fails ? 1 : 0);