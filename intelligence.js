(function registerIntelligence(global) {
 "use strict";
 let reports=[],selected=null,findings=[],admin=false,busy=false,polling=false;
 const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
 const text=value=>esc(value===null||value===undefined||value===""?"—":value);
 function filterFindings(rows,filters) { return rows.filter(row=>["commodity","geography","signal_type","direction"].every(key=>!filters[key]||row[key]===filters[key])); }
 function renderReports(rows) {
  return '<h3>Recent Reports</h3>'+(!rows.length?'<p>No reports uploaded for this selection.</p>':`<div class="intelligence-table-wrap"><table><thead><tr><th>Source</th><th>Report</th><th>Date</th><th>Status</th><th>Findings</th></tr></thead><tbody>${rows.map(d=>`<tr><td>${esc(d.source_organisation)}</td><td><button type="button" data-report-select="${d.id}">${esc(d.title)}</button></td><td>${text(d.report_date)}</td><td><span class="intelligence-status">${esc(d.processing_status)}</span></td><td>${d.finding_count}</td></tr>`).join("")}</tbody></table></div>`);
 }
 function renderSelected(document,rows,isAdmin=false) {
  if(!document) return '<h3>Selected Report</h3><p>Select a report to review its findings and source evidence.</p>';
  const processing=["extracting","analysing"].includes(document.processing_status);
  return `<h3>Selected Report: ${esc(document.title)}</h3><p>${esc(document.source_organisation)} · Report date: ${text(document.report_date)} · ${esc(document.file_type)} · Status: <strong>${esc(document.processing_status)}</strong></p>
   <p>Original: ${esc(document.filename)} · ${document.chunk_count} source chunks · ${document.finding_count} accepted findings · ${document.findings_rejected||0} rejected findings</p>
   ${isAdmin?`<div class="intelligence-actions"><button data-report-process="${document.id}" class="admin-action-button" type="button" ${processing?'disabled':''}>${document.processing_status==='completed'?'Reprocess report':document.processing_status==='failed'?'Retry processing':'Process report'}</button><a class="admin-action-button secondary" href="${esc(document.original_url)}" download>Download original</a><button data-report-delete="${document.id}" class="admin-action-button secondary" type="button" ${processing?'disabled':''}>Delete report and findings</button></div>`:''}
   ${processing?'<p>Processing report. Extraction and AI analysis status update here.</p>':''}
   ${document.error_message?`<p class="intelligence-warning">${esc(document.error_message)} Original and extracted material remain available.</p>`:''}
   <h4>Report summary</h4><p>${esc(document.summary||'No completed analysis yet. Upload alone does not create intelligence findings.')}</p>
   ${document.extraction_limitations?.length?`<details><summary>Extraction limitations</summary><ul>${document.extraction_limitations.map(note=>`<li>${esc(note)}</li>`).join("")}</ul></details>`:''}
   <h4>Structured findings</h4><p class="intelligence-note">AI-derived classifications and interpretations require analyst review. Source excerpts are matched to extracted material; this is not independent verification.</p>
   ${!rows.length?'<p>No supported findings for this selection.</p>':`<div class="intelligence-findings">${rows.map(f=>`<details class="intelligence-finding"><summary><strong>${esc(f.signal_type)} · ${esc(f.direction)}</strong> · ${esc(f.commodity)} · ${esc(f.geography)}<br>${esc(f.key_fact)}<br><small>Confidence: ${esc(f.confidence)} · Source: ${esc(f.source_locator)}</small></summary><p><strong>Risk implication:</strong> ${esc(f.risk_implication||'—')}</p><p>Driver: ${text(f.driver)} · Horizon: ${text(f.time_horizon)}</p><p>Relevant numbers: ${esc((f.relevant_numbers||[]).join('; ')||'—')}</p><h5>Source evidence</h5><p>${esc(f.source_locator)}</p><blockquote>${esc(f.evidence_excerpt)}</blockquote><small>Evidence excerpt from deterministic extraction · ${esc(f.document_title)}</small></details>`).join("")}</div>`}
   <h4>Source evidence</h4><p>Original file hash: <code>${esc(document.file_hash)}</code>. Source locations are supplied by deterministic extraction, not invented by AI.</p>
   <div class="intelligence-chunks">${(document.chunks||[]).map(c=>`<details><summary>${esc(c.source_locator)}</summary><pre>${esc(c.text_content)}</pre></details>`).join("")}</div>`;
 }
 async function request(url,options={}) {
  const response=await fetch(url,{credentials:"same-origin",...options});
  if(!response.ok) throw new Error(response.status===401||response.status===403?(url==='/api/auth/login'?'Invalid username or password.':'Administrator sign-in is required.'):response.status===409?'This report is already processing. Retry later.':response.status===413?'Report exceeds the upload size limit.':response.status===400||response.status===422?'Report or metadata rejected. Check format, source, title and date.':'Intelligence service unavailable. Please retry.');
  return response.json();
 }
 function notify(message) {document.getElementById('intelligenceMessage').textContent=message;}
 function filters(){return {commodity:document.getElementById('intelligenceCommodity').value,geography:document.getElementById('intelligenceGeography').value,signal_type:document.getElementById('intelligenceSignal').value,direction:document.getElementById('intelligenceDirection').value};}
 function render(){document.getElementById('intelligenceReports').innerHTML=renderReports(reports);document.getElementById('intelligenceSelected').innerHTML=renderSelected(selected,filterFindings(findings,filters()),admin);document.getElementById('intelligenceLogin').hidden=admin;document.getElementById('intelligenceUpload').hidden=!admin;}
 function setOptions(id,key,label) {
  const control=document.getElementById(id),old=control.value;const values=[...new Set(findings.map(f=>f[key]))].sort();
  control.innerHTML=`<option value="">${label}</option>`+values.map(value=>`<option value="${esc(value)}">${esc(value)}</option>`).join('');
  if(values.includes(old))control.value=old;
 }
 async function select(id) {
  const [document,rows]=await Promise.all([request('/api/intelligence/documents/'+id),request('/api/intelligence/documents/'+id+'/findings')]);
  selected=document;findings=rows;setOptions('intelligenceCommodity','commodity','All commodities');setOptions('intelligenceGeography','geography','All geographies');render();
 }
 async function load() {
  const params=new URLSearchParams();for(const [id,key] of [['intelligenceSource','source'],['intelligenceDateFrom','start_date'],['intelligenceDateTo','end_date']]){const value=document.getElementById(id).value;if(value)params.set(key,value);}
  try {
   reports=await request('/api/intelligence/documents?'+params);
   const auth=await request('/api/auth/status').catch(()=>({authenticated:false}));admin=auth.authenticated&&auth.role==='admin';
   if(selected&&reports.some(d=>d.id===selected.id))await select(selected.id);
   else if(reports.length)await select(reports[0].id);
   else{selected=null;findings=[];render();}
  }catch(error){notify(error.message);if(!reports.length){document.getElementById('intelligenceReports').innerHTML='<h3>Recent Reports</h3><p>Report service unavailable.</p>';document.getElementById('intelligenceSelected').innerHTML=renderSelected(null,[]);}}
 }
 function initialise() {
  if(!document.getElementById('intelligence'))return;
  for(const id of ['intelligenceSource','intelligenceDateFrom','intelligenceDateTo'])document.getElementById(id).addEventListener('change',load);
  for(const id of ['intelligenceCommodity','intelligenceGeography','intelligenceSignal','intelligenceDirection'])document.getElementById(id).addEventListener('change',render);
  document.getElementById('intelligenceLogin').addEventListener('submit',async event=>{
   event.preventDefault();const form=event.currentTarget;
   try{await request('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:form.elements.username.value,password:form.elements.password.value})});form.elements.password.value='';notify('Administrator signed in.');global.dispatchEvent(new Event('administrator-session-changed'));await load();}catch(error){form.elements.password.value='';notify(error.message);}
  });
  document.getElementById('intelligenceUpload').addEventListener('submit',async event=>{
   event.preventDefault();if(busy)return;const form=event.currentTarget,file=form.elements.report.files[0];
   if(!file||file.size>20*1024*1024){notify('Select a supported report up to 20 MB.');return;}
   busy=true;const button=form.querySelector('button');button.disabled=true;
   try{const body=new FormData(form);if(!form.elements.report_date.value)body.delete('report_date');notify('Uploading original report…');const result=await request('/api/intelligence/documents',{method:'POST',body});selected=result.document;notify(result.duplicate?'Exact duplicate found. Existing report returned; findings were not duplicated.':'Original report preserved. Select Process report to extract and analyse.');await load();}
   catch(error){notify(error.message);}finally{busy=false;button.disabled=false;}
  });
  document.getElementById('intelligenceReports').addEventListener('click',event=>{const button=event.target.closest('[data-report-select]');if(button)select(Number(button.dataset.reportSelect)).catch(error=>notify(error.message));});
  document.getElementById('intelligenceSelected').addEventListener('click',async event=>{
   const process=event.target.closest('[data-report-process]'),remove=event.target.closest('[data-report-delete]');
   if(process&&!busy){busy=true;process.disabled=true;polling=true;notify('Processing selected report…');try{await request('/api/intelligence/documents/'+process.dataset.reportProcess+'/process'+(selected.processing_status==='completed'?'?reprocess=true':''),{method:'POST'});await load();notify(selected?.processing_status==='failed'?'Processing failed. Original and extracted text retained.':'Report processing finished. Review source-linked findings.');}catch(error){notify(error.message);}finally{busy=false;polling=false;}}
   if(remove&&!busy){if(!global.confirm('Delete this report, original file, extracted text and findings?'))return;try{await request('/api/intelligence/documents/'+remove.dataset.reportDelete,{method:'DELETE'});selected=null;findings=[];notify('Report and its findings deleted.');await load();}catch(error){notify(error.message);}}
  });
  global.addEventListener('administrator-session-changed',load);
  load();setInterval(()=>{if(polling||reports.some(d=>['extracting','analysing'].includes(d.processing_status)))load();},4000);
 }
 global.OilRiskIntelligence={filterFindings,renderReports,renderSelected,load};
 if(typeof document!=='undefined'){if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialise);else initialise();}
})(typeof window!=='undefined'?window:globalThis);
