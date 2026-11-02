'use strict';
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const storage = {};
global.window = {
    location: { hostname: 'sita.sms360x.com', search: '', pathname: '/login.html' },
    localStorage: { getItem: k => (k in storage ? storage[k] : null), setItem: (k,v)=>{storage[k]=String(v);}, removeItem: k=>{delete storage[k];} },
};
global.document = { readyState:'complete', addEventListener:()=>{}, createElement:()=>({style:{},appendChild:()=>{},addEventListener:()=>{}}), body:{appendChild:()=>{}} };

// tenant_context
let tcSrc = fs.readFileSync(path.join(root,'public/js/tenant_context.js'),'utf8');
new Function('window', tcSrc).call(global.window, global.window);
const TC = global.window.TenantResolver || global.window;
// firebase getRoleDestination
let fbSrc = fs.readFileSync(path.join(root,'public/js/firebase.js'),'utf8')
    .replace("console.log('?? firebase.js loaded');",'')
    + '\n;window.__fb = { getRoleDestination };';
new Function('window', fbSrc).call(global.window, global.window);
const fb = global.window.__fb;

function getTenant(sub){ global.window.location.hostname = sub; return (TC.getTenantFromSubdomain ? TC.getTenantFromSubdomain() : null); }

// tenant mapping
console.assert(getTenant('sita.sms360x.com') === 'sita', 'sita mapping');
console.assert(getTenant('tara.sms360x.com') === 'tara', 'tara mapping');
console.assert(getTenant('saurya.sms360x.com') === 'saurya', 'saurya mapping');
console.assert(getTenant('unknown.sms360x.com') === null, 'unknown rejected');

// role routing
function dest(u){ return fb.getRoleDestination(u); }
console.assert(dest({role:'TENANT_ADMIN',email:'safety@sitaair.com.np'}) === '/dashboard/safety-manager.html', 'tenant admin');
console.assert(dest({role:'OFFICER',email:'x@y.com',claims:{department:'safety'}}) === '/dashboard/safety-manager.html', 'officer safety');
console.assert(dest({role:'OFFICER',email:'x@y.com',claims:{department:'corporate_safety'}}) === '/dashboard/safety-manager.html', 'officer corporate_safety');
console.assert(dest({role:'OFFICER',email:'safety@x.com',claims:{department:'maintenance'}}) === '/dashboard/my-tasks.html', 'officer safety email but non-safety dept');
console.assert(dest({role:'OFFICER',email:'ops@x.com',claims:{department:'maintenance'}}) === '/dashboard/my-tasks.html', 'officer non-safety');
console.assert(dest({role:'DEPT_ADMIN',email:'x@y.com',department:'maintenance'}) === '/dashboard/my-tasks.html', 'dept admin maintenance');

console.log('route_02c_verify: all assertions passed');
