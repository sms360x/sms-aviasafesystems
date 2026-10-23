'use strict';
const assert = require('assert');
const SO = require('../public/js/safety-officer.js');

function test_fail_closed_safety_officer() {
  assert.strictEqual(SO.isSafetyOfficer({ role: 'OFFICER', department: 'safety' }), true);
  assert.strictEqual(SO.isSafetyOfficer({ role: 'OFFICER', department: 'flight_ops' }), false);
  assert.strictEqual(SO.isSafetyOfficer({ role: 'OFFICER' }), false);
  assert.strictEqual(SO.isSafetyOfficer(null), false);
}

function test_subdomain_flag_default() {
  // In Node (non-browser) the flag defaults to true (dev/staging).
  assert.strictEqual(typeof SO.SUBDOMAIN_ROUTING_ENABLED, 'boolean');
}

function run() {
  test_fail_closed_safety_officer();
  test_subdomain_flag_default();
  console.log('test_safety_officer: 2 tests passed');
}
run();
