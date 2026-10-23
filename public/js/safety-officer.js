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
      <tr>
        <td>${h.id || ''}</td>
        <td>${h.taxonomy || ''}</td>
        <td>${h.title || ''}</td>
        <td>
          ${isSafetyOfficer(window.__user)
            ? `<button class="btn btn-outline" onclick="viewContact('${h.id}')">View Contact</button><span class="contact" style="display:none;"></span>`
            : '<span class="empty">—</span>'}
        </td>
      </tr>
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
    el.innerHTML = items.map(c => `
      <tr>
        <td>${c.id || ''}</td>
        <td>${c.hazard_taxonomy || c.taxonomy || ''}</td>
        <td>${c.status || ''}</td>
        <td>
          ${isSafetyOfficer(window.__user)
            ? `<button class="btn btn-outline" onclick="viewContact('${c.id}', this)">View Contact</button><span class="contact" style="display:none;"></span>`
            : '<span class="empty">—</span>'}
        </td>
      </tr>
    `).join('');
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

async function viewContact(id, btn) {
  const span = btn ? btn.nextElementSibling : null;
  if (span && span.style.display !== 'none') {
    span.style.display = 'none';
    if (btn) btn.textContent = 'View Contact';
    return;
  }
  try {
    const data = await fetchJson(`/api/v1/reports/${encodeURIComponent(id)}/contact`);
    const contact = data && (data.contact || data.reporter_contact || JSON.stringify(data));
    if (span) { span.textContent = contact; span.style.display = 'block'; }
    if (btn) btn.textContent = 'Hide Contact';
  } catch (e) {
    if (span) { span.textContent = 'Unable to load contact'; span.style.display = 'block'; }
  }
}

if (typeof module !== 'undefined') {
  module.exports = { isSafetyOfficer, SUBDOMAIN_ROUTING_ENABLED };
}
