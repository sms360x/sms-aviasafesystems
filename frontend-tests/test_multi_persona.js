'use strict';
const assert=require('assert');
const TA=require('../public/js/tenant-admin.js');
const SS=require('../public/js/state-smd.js');
const AE=require('../public/js/ae-dashboard-refactor.js');

function run(){
  // fail-closed checks
  assert.strictEqual(TA.isTenantAdmin({role:'OFFICER'}),false);
  assert.strictEqual(TA.isTenantAdmin({role:'TENANT_ADMIN'}),true);
  assert.strictEqual(SS.isStateSmd({role:'TENANT_ADMIN'}),false);
  assert.strictEqual(SS.isStateSmd({role:'STATE_SMD'}),true);
  assert.strictEqual(AE.isAE({role:'OFFICER'}),false);
  assert.strictEqual(AE.isAE({role:'ACCOUNTABLE_EXECUTIVE'}),true);
  console.log('test_multi_persona: 6 tests passed');
}
run();