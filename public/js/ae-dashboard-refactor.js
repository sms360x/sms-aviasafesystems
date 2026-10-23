const SUBDOMAIN_ROUTING_ENABLED = (typeof window !== 'undefined' && window.location.hostname !== 'localhost') ? false : true;
function isAE(u){const r=(u&&(u.role||u.custom_claims?.role))||'';return r==='ACCOUNTABLE_EXECUTIVE'||r==='SUPER_ADMIN';}
async function fetchJson(p){const r=await fetch(p,{credentials:'same-origin'});if(!r.ok)throw new Error(r.status);return r.json();}
async function load(){
  const c=document.getElementById('caps');const t=document.getElementById('trends');
  try{const d=await fetchJson('/api/v1/caps?escalated=true');const items=Array.isArray(d)?d:(d.items||[]);c.innerHTML=items.map(x=>`<tr><td>${x.id||''}</td><td>${x.status||''}</td></tr>`).join('')||'<tr><td colspan="2" class="empty">No escalated CAPs.</td></tr>';}catch(e){c.innerHTML='<tr><td colspan="2" class="empty">Failed to load CAPs.</td></tr>';}
  try{const d=await fetchJson('/api/v1/risk/trends');t.textContent=JSON.stringify(d);}catch(e){t.textContent='Failed to load trends.';}
}
if(typeof document!=='undefined'){document.addEventListener('DOMContentLoaded',()=>{const f=document.getElementById('subdomainFlag');if(f)f.dataset.flag=String(SUBDOMAIN_ROUTING_ENABLED);load();});}
if(typeof module!=='undefined'){module.exports={isAE,SUBDOMAIN_ROUTING_ENABLED};}