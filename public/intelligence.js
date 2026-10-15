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
 function render(){document.getElementById('intelligenceReports').innerHTML=renderReports(reports);document.getElementById('intelligenceSelected').innerHTML=renderSelected(selected,filterFindings(findings,filters()),admin);document.getElementById('intelligenceLogin').hidden=admin;document.getElementById('intelligenceUpload').hidden=!admin;document.getElementById('synthesisRefresh').hidden=!admin;}
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

 let pulse=null,pulseBusy=false,pulseSequence=0;
 const sections=[['what_changed','WHAT CHANGED','No meaningful change established from comparable dated reports.'],['cross_source','CROSS-SOURCE SIGNALS','No cross-source signal established.'],['divergence','DIVERGENCE','No meaningful divergence detected.'],['watch_next','WATCH NEXT','No source-supported watch items established.']];
 function renderSynthesis(envelope) {
  const run=envelope?.data,items=run?.items||[],metrics=run?.metrics||{};
  const attempt=envelope?.last_attempt,failed=attempt?.status==='failed';
  const disclosure=run?`Generated ${esc(new Date(run.generated_at).toLocaleString("en-GB",{timeZone:"Africa/Lagos",dateStyle:"medium",timeStyle:"short"}))} WAT · ${metrics.document_count} source reports · ${metrics.source_organisation_count} source organisations · ${metrics.finding_count} findings considered · ${metrics.finding_count_used||0} findings used · Model ${text(run.model_version)}`:'Insufficient recent evidence. Refresh Intelligence Pulse to assess completed reports in this window.';
  return `<p class="intelligence-note">${disclosure}</p>${failed?'<p class="intelligence-warning">Refresh failed. Previous supported synthesis is retained. Retry refresh.</p>':''}${run?.stale?'<p class="intelligence-warning">Evidence changed since generation. Unsupported items are hidden. Refresh Intelligence Pulse.</p>':''}${metrics.single_source?'<p>Only one source available; cross-source agreement cannot be established.</p>':''}${metrics.unknown_date_findings?`<p>${metrics.unknown_date_findings} findings use upload dates; report dates are unavailable.</p>`:''}${metrics.truncated_findings?'<p class="intelligence-warning">Evidence exceeds the processing bound; this synthesis covers a disclosed subset.</p>':''}
  <div class="intelligence-synthesis-grid">${sections.map(([kind,label,empty])=>{
   const cards=items.filter(item=>item.synthesis_type===kind);
   return `<section class="intelligence-synthesis-section"><h3>${label}</h3>${cards.length?cards.map(item=>`<article class="intelligence-synthesis-card"><h4>${esc(item.title)}</h4><p>${esc(item.summary)}</p>${item.evidence.filter(row=>item.summary.endsWith(row.key_fact)).slice(0,1).map(row=>`<p class="intelligence-note">Quoted assessment: ${esc(row.source_organisation)} · ${text(row.report_date)}</p>`).join('')}<p><strong>${esc(item.direction)}</strong> · Confidence: ${esc(item.confidence)} · ${item.source_organisations.length} source organisations · ${item.document_ids.length} reports</p><p class="intelligence-note">${esc(item.commodity)} · ${esc(item.geography)} · ${esc(item.time_horizon)}</p><details class="intelligence-synthesis-evidence"><summary>Evidence · contributing reports</summary><p>Confidence basis: ${esc(item.confidence_basis.independent_claim_count)} independent claim groups; oldest evidence ${esc(item.confidence_basis.oldest_evidence_age_days)} days old as of ${text(item.confidence_basis.recency_as_of)}. Publisher counts do not independently verify source independence.</p>${item.evidence.map(row=>`<div><p><strong>${esc(row.source_organisation)} · ${esc(row.document_title)}</strong><br>Report date: ${text(row.report_date)}${row.date_basis==='upload_date'?' · upload date used for scope':''}<br>Finding ${row.finding_id} · Document ${row.document_id} · ${esc(row.source_locator)} · Phase-1 confidence: ${esc(row.confidence)}</p><blockquote>${esc(row.key_fact)}</blockquote></div>`).join('')}</details></article>`).join(''):`<p class="empty-state">${empty}${kind==='divergence'&&metrics.omitted_candidates?.insufficient_comparability?' Insufficient comparability for some findings.':''}</p>`}</section>`;
  }).join('')}</div><p class="intelligence-note">Extractive source assessments and deterministic comparisons; analyst review required. Agreement describes reported direction, not a trading recommendation.</p>`;
 }
 function synthesisScope(){
  const start=document.getElementById('synthesisStart').value,end=document.getElementById('synthesisEnd').value;
  if(!start||!end||start>end||(Date.parse(end)-Date.parse(start))/86400000>365)throw Error('Select an ordered date window of at most 366 days.');
  return {window_start:start,window_end:end};
 }
 function setSynthesisWindow(){
  const value=document.getElementById('synthesisWindow').value,custom=value==='custom';
  for(const id of ['synthesisStart','synthesisEnd'])document.getElementById(id).disabled=!custom;
  if(!custom){
   const end=new Date(),start=new Date();start.setUTCDate(end.getUTCDate()-Number(value)+1);
   document.getElementById('synthesisStart').value=start.toISOString().slice(0,10);document.getElementById('synthesisEnd').value=end.toISOString().slice(0,10);
  }
 }
 async function loadSynthesis(){
  const sequence=++pulseSequence,status=document.getElementById('synthesisStatus');
  try{
   const scope=synthesisScope();status.textContent='Loading saved intelligence…';
   const result=await request('/api/intelligence/synthesis?'+new URLSearchParams(scope));
   if(sequence!==pulseSequence)return;
   pulse=result;document.getElementById('synthesisContent').innerHTML=renderSynthesis(pulse);
   status.textContent=result.data?'Saved intelligence loaded.':'No synthesis saved for this window.';
   return true;
  }catch(error){if(sequence!==pulseSequence)return;pulse=null;document.getElementById('synthesisContent').innerHTML=renderSynthesis(null);status.textContent=error.message;}
 }
 async function refreshSynthesis(){
  if(pulseBusy)return;
  const button=document.getElementById('synthesisRefresh'),status=document.getElementById('synthesisStatus');
  let scope;try{scope=synthesisScope();}catch(error){status.textContent=error.message;return;}
  pulseBusy=true;button.disabled=true;
  for(const id of ['synthesisWindow','synthesisStart','synthesisEnd'])document.getElementById(id).disabled=true;
  status.textContent='Refreshing Intelligence Pulse…';
  try{
   await request('/api/intelligence/synthesis/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(scope)});
   if(!await loadSynthesis())throw Error('Unable to load refreshed intelligence.');status.textContent='Intelligence Pulse updated.';
  }catch(error){await loadSynthesis();status.textContent='Refresh failed. '+error.message;}
  finally{pulseBusy=false;button.disabled=false;document.getElementById('synthesisWindow').disabled=false;setSynthesisWindow();}
 }
 async function openSavedSynthesis(id){
  if(!Number.isInteger(id)||id<1)return;
  const status=document.getElementById('synthesisStatus');
  status.textContent='Loading supporting synthesis…';
  try{
   const run=await request('/api/intelligence/synthesis/'+id);
   document.getElementById('synthesisWindow').value='custom';setSynthesisWindow();
   document.getElementById('synthesisStart').value=run.window_start;document.getElementById('synthesisEnd').value=run.window_end;
   ++pulseSequence;pulse={available:true,data:run,last_attempt:run};
   document.getElementById('synthesisContent').innerHTML=renderSynthesis(pulse);
   status.textContent='Saved synthesis '+id+' loaded from Risk Advisor provenance.';
  }catch(error){status.textContent='Supporting synthesis unavailable. '+error.message;}
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
  document.getElementById('synthesisWindow').addEventListener('change',()=>{setSynthesisWindow();loadSynthesis();});
  for(const id of ['synthesisStart','synthesisEnd'])document.getElementById(id).addEventListener('change',loadSynthesis);
  document.getElementById('synthesisRefresh').addEventListener('click',refreshSynthesis);
  document.addEventListener('click',event=>{const link=event.target.closest('[data-pulse-run]');if(link)openSavedSynthesis(Number(link.dataset.pulseRun));});
  setSynthesisWindow();loadSynthesis();
  global.addEventListener('administrator-session-changed',load);
  load();setInterval(()=>{if(polling||reports.some(d=>['extracting','analysing'].includes(d.processing_status)))load();},4000);
 }
 global.OilRiskIntelligence={filterFindings,renderReports,renderSelected,renderSynthesis,openSavedSynthesis,loadSynthesis,refreshSynthesis,setSynthesisWindow,synthesisScope,load};
 if(typeof document!=='undefined'){if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialise);else initialise();}
})(typeof window!=='undefined'?window:globalThis);
