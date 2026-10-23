'use strict';
const assert=require('assert');
const DR=require('../public/js/domain-resolver.js');
function run(){
  assert.strictEqual(DR.getTenantFromSubdomain('sita.sms360x.com'),'sita');
  assert.strictEqual(DR.getTenantFromSubdomain('www.sms360x.com'),null);
  assert.strictEqual(DR.getTenantFromSubdomain('api.aviasafesystems.com'),null);
  assert.strictEqual(DR.getTenantFromSubdomain('sms360x.com'),null);
  console.log('test_domain_resolver: 4 tests passed');
}
run();