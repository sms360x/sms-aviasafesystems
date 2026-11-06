const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.resolve(__dirname, '../public/js/admin-setup-core.js'), 'utf8');
const step3 = fs.readFileSync(path.resolve(__dirname, '../public/admin/setup/step3-manage.html'), 'utf8');

function assert(cond, msg) {
  if (!cond) { console.error('FAIL: ' + msg); process.exitCode = 1; }
  else { console.log('PASS: ' + msg); }
}

assert(src.includes("action.type === 'resetPassword'") && src.includes("action.type === 'deleteUser' || action.type === 'resetPassword'"),
  'openConfirm needsKey includes resetPassword');
assert(step3.includes('/js/admin-setup-core.js?brand=20261103'), 'step3 uses bumped cache-bust query');

console.log('\nDone.');
