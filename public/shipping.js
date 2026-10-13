(function registerShipping(global) {
  "use strict";
  let data = null, watchlist = [], admin = false, loading = false;
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const present = value => value !== null && value !== undefined && value !== "";
  const numeric = (value, suffix = "", digits = 1) => typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) + suffix : "—";
  const nav = value => ({0:"Under way (engine)",1:"Reported at anchor",2:"Reported not under command",3:"Restricted manoeuvrability",4:"Constrained draught",5:"Reported moored",6:"Reported aground",7:"Reported fishing",8:"Under way (sailing)"}[value] || (present(value) ? `AIS code ${value}` : "—"));
  const region = value => ({lagos:"Lagos",niger_delta:"Niger Delta",gulf_of_guinea:"Gulf of Guinea"}[value] || "—");
  function elapsed(timestamp, at = Date.now()) {
    const time = Date.parse(timestamp || "");
    return Number.isFinite(time) ? Math.max(0, (at - time) / 1000) : null;
  }
  function since(timestamp) {
    const seconds = elapsed(timestamp);
    return seconds === null ? "—" : seconds < 60 ? `${Math.floor(seconds)} sec ago` : seconds < 3600 ? `${Math.floor(seconds / 60)} min ago` : `${Math.floor(seconds / 3600)} hr ago`;
  }
  function eta(raw) {
    if (!raw || !["Month", "Day", "Hour", "Minute"].every(k => Number.isInteger(raw[k]))) return "—";
    return `${String(raw.Month).padStart(2,"0")}-${String(raw.Day).padStart(2,"0")} ${String(raw.Hour).padStart(2,"0")}:${String(raw.Minute).padStart(2,"0")} · year unspecified`;
  }
  function table(headers, rows, empty) {
    return rows.length ? `<div class="shipping-table-wrap" tabindex="0" aria-label="Scrollable shipping data table"><table class="shipping-table"><thead><tr>${headers.map(h=>`<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(cell=>`<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : `<p class="shipping-empty">${esc(empty)}</p>`;
  }
  function renderCurrent(vessels) {
    return `<h3>Current Watch</h3><p>Last seen uses collector receipt time. Destination and ETA are AIS-reported and may be outdated.</p>` + table(["Vessel / MMSI", "Region", "Navigation", "Speed", "Course", "Last seen", "Destination", "AIS ETA", "Watchlist"], vessels.map(v=>[
      `<strong>${esc(v.vessel_name || "Unnamed vessel")}</strong><br>${esc(v.mmsi)}<br><small>${present(v.vessel_type_code) ? `AIS type ${esc(v.vessel_type_code)} · cargo unverified` : "Type unavailable"}</small>`,
      esc(region(v.region)), esc(nav(v.navigation_status)), numeric(v.sog," kn"), numeric(v.cog,"°"),
      `${esc(since(v.last_seen))}${v.stale ? '<br><strong>No recent position observation</strong>' : ""}<br><small>Position receipt: ${esc(since(v.position_last_seen))}</small>`,
      esc(v.destination || "—"), `${esc(eta(v.eta_raw))}${v.eta_raw ? '<br><small>Possibly stale · vessel-reported</small>' : ""}`, v.watchlisted ? "Watched" : "—"
    ]), "No recent vessel observations in this selection. This does not mean zero vessel traffic.");
  }
  function renderEvents(events) {
    return `<h3>Shipping Exceptions</h3><p>Informational observations; operational conditions are not independently verified.</p>` + table(["Vessel MMSI", "Observation", "Region", "Observed"], events.map(e=>[esc(e.mmsi), `${esc(e.label)}<br><small>${e.event_type === "no_recent_observation" ? "Feed or coverage gaps may explain this." : "AIS-reported"}</small>`, esc(region(e.region)), esc(since(e.observed_at))]), "No active shipping exceptions observed.");
  }
  function renderRegions(rows) {
    return `<h3>Regional Activity</h3><p>Distinct MMSIs in the selected window. The wider Gulf includes its subregions; totals are not additive.</p>` + table(["Region", "Seen", "Moving", "Stationary", "Reported anchor", "Reported moored", "Stale watched", "Coverage"], rows.map(r=>[esc(r.label),r.vessels_observed,r.moving,r.stationary,r.reported_anchored,r.reported_moored,r.stale_watchlist,esc(r.coverage)]), "No recent feed activity observed.");
  }
  function renderQuality(status, regions) {
    const coverage = regions.filter(r=>!r.vessels_observed).map(r=>`${r.label}: No recent feed activity observed.`).join(" ");
    return `<h3>Data Coverage &amp; Quality</h3><p>Provider: AISStream · Collection: <strong>${esc(status.collection_status)}</strong> · Latest message received: ${esc(since(status.latest_message_received))}</p>
      <p>Monitored: Gulf of Guinea pilot, including Niger Delta and Lagos. Over the last 60 minutes: ${status.vessels_observed_recently ?? 0} observed vessels; ${status.static_voyage_vessels ?? 0} with static/voyage context; ${status.destination_vessels ?? 0} with destination; ${status.eta_vessels ?? 0} with ETA; ${status.type_vessels ?? 0} with reported type.</p>
      ${!status.collecting ? '<p class="shipping-warning">Live shipping feed is not currently collecting. Stored observations remain visible with their last-seen times.</p>' : ""}
      ${coverage ? `<p class="shipping-warning">${esc(coverage)}</p>` : ""}
      <p>AIS observations are event-driven and coverage varies by geography. Absence of a recent observation does not prove absence of a vessel. Destination and ETA are vessel-reported and may be outdated. Type categories do not verify cargo.</p>
      <p class="shipping-scope-note">Receipt time records when our collector received a message. Provider time and the AIS UTC-second field do not establish a complete dated vessel transmission time. Static messages do not refresh position time.</p>`;
  }
  function renderWatchlist() {
    const el = document.getElementById("shippingWatchlist");
    if (el) el.innerHTML = table(["MMSI", "Vessel", "Priority", "Reason", "State", ...(admin ? ["Manage"] : [])], watchlist.map(w=>[esc(w.mmsi),esc(w.vessel_name || "—"),esc(w.priority),esc(w.reason || "—"),w.active?"Active":"Inactive",...(admin?[`<button type="button" data-shipping-edit="${w.id}">Edit</button> <button type="button" data-shipping-delete="${w.id}">Remove</button>`]:[])]), "No vessels have been added to the watchlist.");
    document.getElementById("shippingLogin").hidden = admin;
    document.getElementById("shippingWatchForm").hidden = !admin;
  }
  async function request(path, options = {}) {
    const response = await fetch(path, {credentials:"same-origin",...options});
    if (!response.ok) throw new Error(response.status === 403 || response.status === 401 ? "Administrator sign-in is required for watchlist changes." : response.status === 409 ? "This MMSI is already on the watchlist." : "Shipping service unavailable. Try again shortly.");
    return response.json();
  }
  async function load() {
    if (loading || !document.getElementById("shippingSummary")) return;
    loading = true;
    const minutes=document.getElementById("shippingWindow").value;
    const selected=document.getElementById("shippingRegion").value;
    const type=document.getElementById("shippingType").value;
    try {
      const params = new URLSearchParams({minutes}); if(selected) params.set("region",selected); if(type) params.set("type_code",type);
      const results=await Promise.all([request("/api/shipping/status"),request(`/api/shipping/vessels?${params}`),request("/api/shipping/events"),request(`/api/shipping/regions?minutes=${minutes}`),request("/api/shipping/watchlist")]);
      data={status:results[0],vessels:results[1],events:results[2],regions:results[3]}; watchlist=results[4];
      const auth=await request("/api/auth/status").catch(()=>({authenticated:false})); admin=auth.authenticated && auth.role==="admin";
      document.getElementById("shippingSummary").innerHTML = [["Collection status",data.status.collection_status],["Vessels seen",data.vessels.length],["Watchlist alerts",data.status.watchlist_alerts],["Coverage",data.regions.find(r=>r.region===(selected||"gulf_of_guinea"))?.coverage || "Unknown"]].map(([label,value])=>`<div><span>${label}</span><strong>${esc(value)}</strong></div>`).join("");
      document.getElementById("shippingCurrentWatch").innerHTML=renderCurrent(data.vessels);
      document.getElementById("shippingExceptions").innerHTML=renderEvents(data.events.filter(e=>!selected || selected==="gulf_of_guinea" || e.region===selected));
      document.getElementById("shippingRegionalActivity").innerHTML=renderRegions(data.regions);
      document.getElementById("shippingQuality").innerHTML=renderQuality(data.status,data.regions);
      if (!type) {
        const codes=[...new Set(data.vessels.filter(v=>present(v.vessel_type_code)).map(v=>v.vessel_type_code))].sort((a,b)=>a-b);
        document.getElementById("shippingType").innerHTML='<option value="">All / unknown types included</option>'+codes.map(code=>`<option value="${code}">AIS type ${code} · cargo unverified</option>`).join("");
      }
      renderWatchlist();
    } catch (_) {
      document.getElementById("shippingSummary").innerHTML='<p class="shipping-warning">Shipping service unavailable. Collection status cannot be confirmed.</p>';
      if (data) document.getElementById("shippingQuality").innerHTML=renderQuality({...data.status,collecting:false,collection_status:"unconfirmed"},data.regions);
      else {
        document.getElementById("shippingCurrentWatch").innerHTML=renderCurrent([]);
        document.getElementById("shippingExceptions").innerHTML=renderEvents([]);
        document.getElementById("shippingRegionalActivity").innerHTML=renderRegions([]);
        document.getElementById("shippingQuality").innerHTML='<h3>Data Coverage &amp; Quality</h3><p>Live shipping feed is not currently available. No vessel or traffic conclusions can be drawn.</p>';
      }
    } finally { loading=false; }
  }
  function message(text) {document.getElementById("shippingAdminMessage").textContent=text;}
  function initialise() {
    if (!document.getElementById("shipping")) return;
    for (const id of ["shippingRegion","shippingWindow","shippingType"]) document.getElementById(id).addEventListener("change",load);
    document.getElementById("shippingReload").addEventListener("click",load);
    document.getElementById("shippingLogin").addEventListener("submit",async event=>{
      event.preventDefault();const form=event.currentTarget;
      try { await request("/api/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:form.elements.username.value,password:form.elements.password.value})});form.elements.password.value="";message("Administrator signed in.");await load(); }
      catch (_) {form.elements.password.value="";message("Administrator sign-in failed.");}
    });
    document.getElementById("shippingWatchForm").addEventListener("submit",async event=>{
      event.preventDefault(); const form=event.currentTarget, f=form.elements;
      const payload={mmsi:f.mmsi.value,vessel_name:f.vessel_name.value||null,reason:f.reason.value||null,priority:f.priority.value,active:f.active.checked};
      try { await request('/api/shipping/watchlist'+(f.entryId.value?'/'+f.entryId.value:''),{method:f.entryId.value?'PUT':'POST',headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});form.reset();f.entryId.value="";message("Watchlist saved.");await load(); }
      catch(error){message(error.message);}
    });
    document.getElementById("shippingWatchCancel").addEventListener("click",()=>{const f=document.getElementById("shippingWatchForm");f.reset();f.elements.entryId.value="";});
    document.getElementById("shippingLogout").addEventListener("click",async()=>{await request("/api/auth/logout",{method:"POST"});message("Signed out.");await load();});
    document.getElementById("shippingWatchlist").addEventListener("click",async event=>{
      const edit=event.target.closest("[data-shipping-edit]"),remove=event.target.closest("[data-shipping-delete]");
      if(edit){const row=watchlist.find(w=>w.id===Number(edit.dataset.shippingEdit)), f=document.getElementById("shippingWatchForm").elements; if(row){f.entryId.value=row.id;for(const key of ["mmsi","vessel_name","reason","priority"])f[key].value=row[key]||"";f.active.checked=row.active;}}
      if(remove){try{await request('/api/shipping/watchlist/'+remove.dataset.shippingDelete,{method:"DELETE"});message("Watchlist entry removed.");await load();}catch(error){message(error.message);}}
    });
    load();setInterval(load,30000);
  }
  global.OilRiskShipping={elapsed,eta,renderCurrent,renderEvents,renderRegions,renderQuality,load};
  if(typeof document!=="undefined") {if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",initialise);else initialise();}
})(typeof window!=="undefined"?window:globalThis);
