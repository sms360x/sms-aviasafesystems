const SUBDOMAIN_ROUTING_ENABLED = (typeof window !== 'undefined' && window.location.hostname !== 'localhost') ? false : true;
function isStateSmd(u){const r=(u&&(u.role||u.custom_claims?.role))||'';return r==='STATE_SMD'||r==='SUPER_ADMIN';}
async function fetchJson(p){const r=await fetch(p,{credentials:'same-origin'});if(!r.ok)throw new Error(r.status);return r.json();}
async function load(){
  const k=document.getElementById('kpis');const t=document.getElementById('trends');
  try{const d=await fetchJson('/api/v1/state/kpis');k.textContent=JSON.stringify(d);}catch(e){k.textContent='Failed to load aggregates.';}
  try{const d=await fetchJson('/api/v1/state/trends');t.textContent=JSON.stringify(d);}catch(e){t.textContent='Failed to load trends.';}
}
if(typeof document!=='undefined'){document.addEventListener('DOMContentLoaded',()=>{const f=document.getElementById('subdomainFlag');if(f)f.dataset.flag=String(SUBDOMAIN_ROUTING_ENABLED);load();});}
if(typeof module!=='undefined'){module.exports={isStateSmd,SUBDOMAIN_ROUTING_ENABLED};}