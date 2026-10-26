const form=document.querySelector('#filters'), register=document.querySelector('#register'), days=document.querySelector('#days');
const preview=document.querySelector('#preview'), status=document.querySelector('#status'), error=document.querySelector('#error'), download=document.querySelector('#download');
let selected=null, busy=false;
function showError(message){error.textContent=message;error.hidden=false;}
async function check(response){if(response.ok)return response;let message='Unable to read the register.';try{const data=await response.json();if(typeof data.detail==='string')message=data.detail;}catch{}throw new Error(message);}
function cell(tag,value){const c=document.createElement(tag);c.textContent=value==null?'':typeof value==='boolean'?(value?'Yes':'No'):String(value);return c;}
function invalidate(){selected=null;download.disabled=true;status.textContent='Filters changed. Preview again to enable export.';}
register.addEventListener('change',invalidate);days.addEventListener('change',invalidate);
function controls(disabled){form.querySelectorAll('button,select').forEach(e=>e.disabled=disabled);}
form.addEventListener('submit',async event=>{event.preventDefault();if(busy)return;busy=true;controls(true);download.disabled=true;error.hidden=true;selected=null;status.textContent='Reading register…';
 try{const query=new URLSearchParams({register:register.value,days:days.value});const data=await (await check(await fetch('/api/preview?'+query,{cache:'no-store'}))).json();
 const table=document.createElement('table'),head=document.createElement('thead'),tr=document.createElement('tr');data.headers.forEach(h=>tr.append(cell('th',h)));head.append(tr);table.append(head);const body=document.createElement('tbody');data.rows.forEach(row=>{const r=document.createElement('tr');row.forEach(v=>r.append(cell('td',v)));body.append(r);});table.append(body);preview.replaceChildren(table);
 if(!data.rows.length){const p=document.createElement('p');p.textContent='No rows match these filters. Export will contain headers only.';preview.append(p);}
 status.textContent=`${data.rows.length} preview rows · filtered by ${data.date_field} · export includes all matching rows`;selected=query;download.disabled=false;
 }catch(e){showError(e.message);status.textContent='Preview could not be loaded.';preview.replaceChildren();}finally{busy=false;controls(false);}});
download.addEventListener('click',async()=>{if(!selected||busy)return;busy=true;controls(true);download.disabled=true;error.hidden=true;const query=selected;try{const response=await check(await fetch('/api/export?'+query,{cache:'no-store'}));const blob=await response.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=(response.headers.get('content-disposition')||'').match(/filename="([^"]+)"/)?.[1]||'register.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){showError(e.message);}finally{busy=false;controls(false);download.disabled=!selected;}});
