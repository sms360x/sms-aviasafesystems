'use strict';
const RESERVED_KEYWORDS = ['www','api','admin','app','mail','sms','login','auth'];

const APEX_DOMAINS = ['sms360x.com','aviasafesystems.com'];

function getActiveApex() {
  // Primary apex when subdomain routing enabled; fallback to legacy.
  const flag = (typeof window !== 'undefined' && window.__SUBDOMAIN_ROUTING_ENABLED) ? true : false;
  return flag ? 'sms360x.com' : 'aviasafesystems.com';
}

function getTenantFromSubdomain(hostname) {
  const host = (hostname || '').toLowerCase().trim();
  const apex = APEX_DOMAINS.find(d => host === d || host.endsWith('.' + d));
  if (!apex) return null;
  const prefix = host.slice(0, host.length - apex.length).replace(/\.$/, '');
  if (!prefix) return null; // apex, no tenant
  const label = prefix.split('.')[0];
  if (RESERVED_KEYWORDS.includes(label)) return null;
  return label;
}

function buildTenantUrl(tenantSlug, path) {
  const apex = getActiveApex();
  const p = path && path.startsWith('/') ? path : '/' + (path || '');
  return `https://${tenantSlug}.${apex}${p}`;
}

if (typeof module !== 'undefined') {
  module.exports = { RESERVED_KEYWORDS, APEX_DOMAINS, getTenantFromSubdomain, buildTenantUrl, getActiveApex };
}
if (typeof window !== 'undefined') {
  window.DomainResolver = { RESERVED_KEYWORDS, APEX_DOMAINS, getTenantFromSubdomain, buildTenantUrl, getActiveApex };
}