(function registerHistoricalAnalytics(global) {
  "use strict";
  let payload = null;
  const finite = value => typeof value === "number" && Number.isFinite(value);
  const escape = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  const number = value => finite(value) ? value.toLocaleString("en-US", {maximumFractionDigits: 2}) : "—";

  function selectSeries(data, instrument) {
    return data && Array.isArray(data.instruments) ? data.instruments.find(item => item.instrument === instrument && item.provider === "platts_excel") : null;
  }

  function chart(points, unit) {
    const valid = (points || []).filter(p => p && finite(p.value) && Number.isFinite(Date.parse(p.date)));
    if (valid.length < 2) return '<p class="historical-empty">Insufficient observations for a historical chart.</p>';
    const first = Date.parse(valid[0].date), last = Date.parse(valid.at(-1).date);
    const low = Math.min(...valid.map(p => p.value)), high = Math.max(...valid.map(p => p.value));
    const x = date => 60 + (Date.parse(date) - first) / (last - first || 1) * 700;
    const y = value => 220 - (value - low) / (high - low || 1) * 170;
    const line = valid.map(p => `${x(p.date).toFixed(2)},${y(p.value).toFixed(2)}`).join(" ");
    return `<svg class="historical-chart" viewBox="0 0 800 265" role="img" aria-label="90 calendar-day historical price chart in ${escape(unit)}">
      <line x1="60" y1="220" x2="760" y2="220" stroke="#ced8e7"/>
      <text x="5" y="55">${number(high)}</text><text x="5" y="220">${number(low)}</text>
      <polyline points="${line}" fill="none" stroke="#203973" stroke-width="2.5"/>
      ${valid.map(p => `<circle cx="${x(p.date)}" cy="${y(p.value)}" r="2.5" fill="#203973"><title>${escape(p.date)}: ${number(p.value)} ${escape(unit)}</title></circle>`).join("")}
      <text x="60" y="250">${escape(valid[0].date)}</text><text x="760" y="250" text-anchor="end">${escape(valid.at(-1).date)}</text>
    </svg>`;
  }

  function markup(series) {
    if (!series || !finite(series.latest)) return '<p class="historical-empty">Historical data unavailable. Import the approved Platts workbook to populate this section.</p>';
    const metrics = [["Latest", series.latest], ["1D change", series.change_1d], ["30D change", series.change_30d], ["90D change", series.change_90d]];
    const spread = finite(series.spread) && finite(series.factor)
      ? `<p class="historical-spread">Spread vs same-date Platts Dated Brent: <strong>${number(series.spread)} USD/bbl</strong><br>Native product ÷ ${escape(series.factor)} bbl/mt − Dated Brent. Recomputed from raw prices.</p>` : "";
    return `<h4>${escape(series.label)}</h4>
      <p class="historical-disclosure"><strong>${escape(series.freshness.toUpperCase())}</strong> · As of ${escape(series.latest_date)} · ${escape(series.unit)} · ${escape(series.symbol)}<br>
      Source: Platts Excel · ${series.observation_count} valid observations · 30D: ${series.count_30d} · 90D: ${series.count_90d}</p>
      <div class="historical-kpis">${metrics.map(([label,value]) => `<div><span>${label}</span><strong>${number(value)}</strong><small>${escape(series.unit)}</small></div>`).join("")}</div>
      ${chart(series.points, series.unit)}${spread}
      <p class="historical-footnote">Windows end at the latest observation, not today. Changes are absolute native-unit differences; 1D uses the previous available assessment, and 30D/90D use the first valid assessment inside each calendar window. Stale history remains available.</p>
      <details><summary>Historical provenance</summary><p>Workbook: ${escape(series.workbook)}<br>Worksheet: ${escape(series.worksheet)}<br>Imported: ${escape(series.imported_at)}<br>These histories are never concatenated with API/proxy observations.</p></details>`;
  }

  function render() {
    const target = document.getElementById("historicalAnalyticsContent");
    const select = document.getElementById("historicalInstrument");
    if (target && select) target.innerHTML = markup(selectSeries(payload, select.value));
  }

  async function load() {
    const target = document.getElementById("historicalAnalyticsContent");
    const button = document.getElementById("historicalReload");
    if (!target) return;
    if (button) button.disabled = true;
    try {
      const response = await fetch("/api/market/historical", {credentials: "same-origin"});
      if (!response.ok) throw new Error("Historical service unavailable");
      payload = await response.json();
      render();
    } catch (_) {
      target.innerHTML = '<p class="historical-empty">Historical service unavailable. Reload history after the backend migration and workbook import are complete.</p>';
    } finally { if (button) button.disabled = false; }
  }

  function initialise() {
    document.getElementById("historicalInstrument")?.addEventListener("change", render);
    document.getElementById("historicalReload")?.addEventListener("click", load);
    load();
  }
  global.OilRiskHistoricalAnalytics = {selectSeries, markup, chart, load};
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialise);
    else initialise();
  }
})(typeof window !== "undefined" ? window : globalThis);
