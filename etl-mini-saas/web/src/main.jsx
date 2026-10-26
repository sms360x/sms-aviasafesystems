import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';

import './style.css';

function save(name, content) {
  const url = URL.createObjectURL(new Blob(['\ufeff', content], {type:'text/csv;charset=utf-8'}));
  const link = document.createElement('a'); link.href=url; link.download=name; link.click();
  setTimeout(()=>URL.revokeObjectURL(url), 1000);
}
async function responseJSON(response) {
  const body = await response.text();
  let data; try {data=JSON.parse(body);} catch {throw new Error(`Server returned an unreadable response (${response.status}).`);}
  if (!response.ok) throw new Error(typeof data.detail==='string'?data.detail:'Unable to process workbook.');
  return data;
}
function App() {
  const [file,setFile]=useState(null), [book,setBook]=useState(null), [sheets,setSheets]=useState([]);
  const [active,setActive]=useState(0), [mode,setMode]=useState('split'), [files,setFiles]=useState([]);
  const [busy,setBusy]=useState(false), [error,setError]=useState(''), [localCount,setLocalCount]=useState(0);
  const current=sheets[active];
  function update(patch){setSheets(old=>old.map((s,i)=>i===active?{...s,...patch}:s));setFiles([]);}
  async function upload(selected){
    if(!selected)return; setBusy(true);setError('');setFiles([]);setBook(null);setSheets([]);setFile(null);
    try{
      if(!selected.name.toLowerCase().endsWith('.xlsx'))throw new Error('Choose an .xlsx workbook.');
      if(selected.size>20*1024*1024)throw new Error('Workbook exceeds 20 MB.');
      const XLSX=await import('xlsx');
      const local=XLSX.read(await selected.arrayBuffer(),{type:'array',sheetRows:110});
      setLocalCount(local.SheetNames.length);
      const form=new FormData();form.append('file',selected);
      const data=await responseJSON(await fetch('/api/inspect',{method:'POST',body:form}));
      setBook(data);setSheets(data.sheets);setActive(0);setFile(selected);
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function convert(){
    setBusy(true);setError('');setFiles([]);
    try{const form=new FormData();form.append('file',file);form.append('configuration',JSON.stringify(sheets));form.append('mode',mode);
      const result=await responseJSON(await fetch('/api/convert',{method:'POST',body:form}));setFiles(result.files);
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  function columnsFor(sheet){
    const a=sheet.grid[sheet.header_row]||[], b=sheet.header_depth===2?(sheet.grid[sheet.header_row+1]||[]):[];
    let parent='';const seen={};
    return a.map((v,i)=>{if(v)parent=v;const label=[...new Set([v||(b[i]?parent:''),b[i]].filter(Boolean))].join(' / ')||`Column ${i+1}`;seen[label]=(seen[label]||0)+1;return seen[label]>1?`${label} [${seen[label]}]`:label;});
  }
  const columns=current?columnsFor(current):[];
  return <><header><a className="brand" href="/">↗ <span>LOGSHEET STUDIO</span></a><span className="badge">AIRLINE DATA TOOLS</span></header>
    <main><div className="eyebrow">EXCEL → CSV / WORKBOOK REVIEW</div><h1>A cleaner start<br/><span>for your safety data.</span></h1>
    <p className="intro">Break a multi-tab workbook into individual CSVs. Review the first ten rows, then decide how each register should map.</p>
    <div className="steps"><span className="selected">01 Upload workbook</span><span>02 Review & map</span><span>03 Download CSVs</span></div>
    <section className="upload"><div><h2>Start with your logsheet</h2><p>.xlsx only · up to 20 MB · first 10 data rows per tab</p></div><label className="button">{busy?'Processing…':'Choose workbook'}<input type="file" accept=".xlsx" disabled={busy} onChange={e=>upload(e.target.files[0])}/></label></section>
    {error&&<div className="error" role="alert">{error}</div>}
    {book&&<><div className="summary"><strong>{file.name}</strong><span>{localCount} tabs detected · sample mode · files stay in memory</span></div>
      <div className="workspace"><nav aria-label="Workbook tabs"><h3>WORKBOOK TABS</h3>{sheets.map((s,i)=><button key={s.name} className={i===active?'tab active':'tab'} onClick={()=>setActive(i)}>{s.name}<small>{s.entity}</small></button>)}</nav>
      <section className="panel"><div className="paneltop"><h2>{current.name}</h2><span className="badge">10 ROW SAMPLE</span></div>
      <div className="controls"><label>Header starts at Excel row<input type="number" min="1" max={Math.min(61,current.grid.length)||1} value={current.header_row+1} onChange={e=>update({header_row:Math.max(0,Number(e.target.value)-1),mapping:{}})}/></label>
      <label>Header rows<select value={current.header_depth} onChange={e=>update({header_depth:Number(e.target.value),mapping:{}})}><option value="1">Single row</option><option value="2">Two rows → flattened</option></select></label>
      <label>Conversion mode<select value={mode} onChange={e=>{setMode(e.target.value);setFiles([]);}}><option value="split">Split only · original columns</option><option value="mapped">Map to standard headers</option></select></label></div>
      <p className="note">Split mode preserves all source columns, including unnamed columns. The ten-row limit applies before validation. Header detection is a suggestion—check the preview.</p>
      {mode==='mapped'&&<><label>Output entity<select value={current.entity} onChange={e=>update({entity:e.target.value,mapping:{}})}><option>Original</option>{Object.keys(book.contracts).map(e=><option key={e}>{e}</option>)}</select></label>
      {current.entity!=='Original'&&<div className="mapping">{book.contracts[current.entity].map(target=><div className="maprow" key={target}><strong>{target}</strong><span>←</span><select aria-label={`Source for ${target}`} value={current.mapping[target]??''} onChange={e=>{const mapping={...current.mapping};if(e.target.value==='')delete mapping[target];else mapping[target]=Number(e.target.value);update({mapping});}}><option value="">Unmapped / use constant</option>{columns.map((c,i)=><option value={i} key={i}>{c}</option>)}</select><input placeholder="Constant (optional)" aria-label={`Constant for ${target}`} disabled={current.mapping[target]!==undefined} value={current.constants?.[target]||''} onChange={e=>update({constants:{...current.constants,[target]:e.target.value}})}/></div>)}</div>}</>}
      <h3>SOURCE PREVIEW</h3><div className="tablewrap"><table><thead><tr>{columns.map((c,i)=><th key={i}>{c}</th>)}</tr></thead><tbody>{current.grid.slice(current.header_row+current.header_depth,current.header_row+current.header_depth+10).map((row,i)=><tr key={i}>{columns.map((_,j)=><td key={j}>{row[j]}</td>)}</tr>)}</tbody></table>{current.grid.length<=current.header_row+current.header_depth&&<p>This tab has headers only. Its CSV will contain the header.</p>}</div>
      </section></div><div className="actionbar"><p>No ZIP. One CSV for each tab, named after the tab.</p><button disabled={busy} onClick={convert}>{busy?'Converting…':'Generate separate CSVs →'}</button></div>
      {files.length>0&&<section className="downloads"><h2>Your CSV files</h2><p>Mapped output excludes rejected rows. Download the validation report for details.</p>{files.map(f=><div className="download" key={f.name}><div><strong>{f.name}</strong><small>{f.rows} rows · {f.rejected} rejected</small></div><button onClick={()=>save(f.name,f.csv)}>Download CSV ↓</button></div>)}</section>}</>}
      <footer>LOGSHEET STUDIO <span>Standalone conversion · no database writes</span></footer></main></>;
}
createRoot(document.getElementById('root')).render(<App/>);

