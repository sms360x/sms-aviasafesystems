// Phase 3B Workstream 1 — Safety Officer (Sorting Center / CAP Queue) scaffold.
// Subdomain routing feature flag: default OFF in production, ON in dev/staging.
const SUBDOMAIN_ROUTING_ENABLED = (typeof window !== 'undefined' && window.location.hostname !== 'localhost') ? false : true;

function isSafetyOfficer(user) {
  // Fail-closed: only OFFICER of the Safety department (or legacy SAFETY_OFFICER) qualifies.
  const role = (user && (user.role || user.custom_claims?.role)) || '';
  const dept = (user && (user.department || user.custom_claims?.department)) || '';
  if (role === 'SAFETY_OFFICER') return true;
  return role === 'OFFICER' && (dept === 'safety' || dept === 'corporate_safety');
}

async function fetchJson(path) {
  const res = await fetch(path, { credentials: 'same-origin' });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function loadSortingCenter() {
  const el = document.getElementById('sortingCenter');
  try {
    const data = await fetchJson('/api/v1/hazards?scope=safety');
    const items = Array.isArray(data) ? data : (data.items || []);
    if (!items.length) { el.textContent = 'No items in sorting center.'; return; }
    el.innerHTML = items.map(h => `
      <div class="item">
        <strong>${h.taxonomy || 'Hazard'}</strong>
        <div>${h.title || ''}</div>
        ${isSafetyOfficer(window.__user) && h.reporter_contact ? `<div class="contact">Reporter: ${h.reporter_contact}</div>` : ''}
      </div>
    `).join('');
  } catch (e) {
    el.textContent = 'Failed to load sorting center.';
  }
}

async function loadCapQueue() {
  const el = document.getElementById('capQueue');
  try {
    const data = await fetchJson('/api/v1/caps?status=open');
    const items = Array.isArray(data) ? data : (data.items || []);
    if (!items.length) { el.textContent = 'No open CAPs.'; return; }
    el.innerHTML = items.map(c => `<div class="item"><strong>${c.id || ''}</strong> — ${c.status || ''}</div>`).join('');
  } catch (e) {
    el.textContent = 'Failed to load CAP queue.';
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
  const flagEl = document.getElementById('subdomainFlag');
  if (flagEl) flagEl.dataset.flag = String(SUBDOMAIN_ROUTING_ENABLED);
  loadSortingCenter();
  loadCapQueue();
  });
}

if (typeof module !== 'undefined') {
  module.exports = { isSafetyOfficer, SUBDOMAIN_ROUTING_ENABLED };
}
