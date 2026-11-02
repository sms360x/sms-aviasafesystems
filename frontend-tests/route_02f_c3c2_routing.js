'use strict';
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');

global.window = { location: { search: '', pathname: '/login.html' }, localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} }, sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} } };
global.document = { readyState: 'complete', addEventListener: () => {}, createElement: () => ({ style: {}, appendChild: () => {}, addEventListener: () => {} }), body: { appendChild: () => {} } };

let fbSrc = fs.readFileSync(path.join(root, 'public/js/firebase.js'), 'utf8').replace("console.log('?? firebase.js loaded');", '')
    + '\n;window.__fb = { getRoleDestination };';
new Function('window', fbSrc).call(global.window, global.window);
const fb = global.window.__fb;

let fails = 0;
function assert(cond, msg){ if(!cond){ console.log('FAIL: '+msg); fails++; } else { console.log('PASS: '+msg); } }

// 1. OFFICER + safety
assert(fb.getRoleDestination({role:'OFFICER', claims:{department:'safety'}}) === '/dashboard/safety-manager.html', 'OFFICER safety -> safety-manager');
// 2. OFFICER + corporate_safety
assert(fb.getRoleDestination({role:'OFFICER', claims:{department:'corporate_safety'}}) === '/dashboard/safety-manager.html', 'OFFICER corporate_safety -> safety-manager');
// 3. OFFICER + other dept
assert(fb.getRoleDestination({role:'OFFICER', claims:{department:'maintenance'}}) === '/dashboard/my-tasks.html', 'OFFICER maintenance -> my-tasks');
// 4. DEPT_ADMIN
assert(fb.getRoleDestination({role:'DEPT_ADMIN'}) === '/dashboard/my-tasks.html', 'DEPT_ADMIN -> my-tasks');
// 5. USER with/without dept
assert(fb.getRoleDestination({role:'USER', claims:{department:'safety'}}) === '/login.html', 'USER with dept -> login');
assert(fb.getRoleDestination({role:'USER'}) === '/login.html', 'USER without dept -> login');
// 6. SAFETY_OFFICER legacy
assert(fb.getRoleDestination({role:'SAFETY_OFFICER'}) === '/login.html', 'SAFETY_OFFICER -> login');
// 7. Unknown role
assert(fb.getRoleDestination({role:'UNKNOWN_ROLE'}) === '/login.html', 'unknown role -> login');
// 8. STATE_SMD
assert(fb.getRoleDestination({role:'STATE_SMD'}) === '/dashboard/state-oversight.html', 'STATE_SMD -> state-oversight');
// 9. TENANT_ADMIN + AE exception
assert(fb.getRoleDestination({role:'TENANT_ADMIN', email:'ae@x.com'}) === '/dashboard/ae-dashboard.html', 'TENANT_ADMIN AE -> ae-dashboard');
assert(fb.getRoleDestination({role:'TENANT_ADMIN', email:'safety@x.com'}) === '/dashboard/safety-manager.html', 'TENANT_ADMIN safety -> safety-manager');
// 10. ACCOUNTABLE_EXECUTIVE, SUPER_ADMIN
assert(fb.getRoleDestination({role:'ACCOUNTABLE_EXECUTIVE'}) === '/dashboard/ae-dashboard.html', 'AE -> ae-dashboard');
assert(fb.getRoleDestination({role:'SUPER_ADMIN'}) === '/admin/production-setup.html', 'SUPER_ADMIN -> production-setup');

console.log(fails ? `\nRESULT: ${fails} FAILURES` : '\nRESULT: ALL ROUTE-02F-C3-C2 ROUTING CHECKS PASSED');
process.exit(fails ? 1 : 0);