// ============================================================
// VERIFIED NEWS SERVICE
// The browser reads only normalized backend news records.
// ============================================================

(function registerNewsService(global) {
  "use strict";

  async function getLatestNews(options) {
    const settings = options || {};
    const endpoint = (global.OilRiskConfig && global.OilRiskConfig.NEWS_API_ENDPOINTS && global.OilRiskConfig.NEWS_API_ENDPOINTS.latest)
      || "/api/news/latest";
    const params = new URLSearchParams();
    if (settings.region) params.set("region", settings.region);
    if (settings.topic) params.set("topic", settings.topic);
    if (settings.limit) params.set("limit", String(settings.limit));
    const response = await global.fetch(`${endpoint}${params.toString() ? `?${params}` : ""}`, {
      method: "GET",
      credentials: "same-origin",
      headers: { Accept: "application/json" }
    });
    if (!response.ok) {
      throw new Error(`News service returned HTTP ${response.status}.`);
    }
    return response.json();
  }

  async function refreshNews() {
    const endpoint = (global.OilRiskConfig && global.OilRiskConfig.NEWS_API_ENDPOINTS && global.OilRiskConfig.NEWS_API_ENDPOINTS.refresh)
      || "/api/news/refresh";
    const response = await global.fetch(endpoint, {
      method: "POST",
      credentials: "same-origin",
      headers: { Accept: "application/json" }
    });
    if (!response.ok) {
      throw new Error(`News refresh returned HTTP ${response.status}.`);
    }
    return response.json();
  }

  global.OilRiskNewsService = { getLatestNews, refreshNews };
})(typeof window !== "undefined" ? window : globalThis);
