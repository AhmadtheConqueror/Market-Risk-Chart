// ============================================================
// MARKET DATA SERVICE
// The browser talks only to our backend. External provider details stay server-side.
// ============================================================

(function registerMarketDataService(global) {
  "use strict";

  const memoryCache = new Map();
  let lastSuccessfulSnapshot = null;
  let lastSuccessfulObservations = null;
  let lastSuccessfulHistoryByInstrument = {};

  const MACRO_INDICATOR_DEFAULTS = Object.freeze([
    Object.freeze({
      indicator_key: "headline_inflation",
      display_name: "Headline Inflation",
      unit: "%",
      source: "National Bureau of Statistics Nigeria"
    }),
    Object.freeze({
      indicator_key: "food_inflation",
      display_name: "Food Inflation",
      unit: "%",
      source: "National Bureau of Statistics Nigeria"
    }),
    Object.freeze({
      indicator_key: "core_inflation",
      display_name: "Core Inflation",
      unit: "%",
      source: "National Bureau of Statistics Nigeria"
    }),
    Object.freeze({
      indicator_key: "real_gdp_growth",
      display_name: "Real GDP Growth",
      unit: "%",
      source: "National Bureau of Statistics Nigeria"
    }),
    Object.freeze({
      indicator_key: "nigeria_pmi",
      display_name: "PMI",
      unit: "index",
      source: "Stanbic IBTC Bank / S&P Global"
    }),
    Object.freeze({
      indicator_key: "crude_oil_production",
      display_name: "Crude Oil Production",
      unit: "mbpd",
      source: "Nigerian Upstream Petroleum Regulatory Commission"
    })
  ]);

  async function getDashboardSnapshot() {
    const endpoint = (global.OilRiskConfig && global.OilRiskConfig.MARKET_API_ENDPOINTS && global.OilRiskConfig.MARKET_API_ENDPOINTS.snapshot)
      || "/api/dashboard/snapshot";
    return await requestJson(endpoint);
  }

  async function getLatestMarketData(options) {
    const settings = options || {};

    if (isLegacyMode()) {
      return latestByInstrument(legacyObservations(settings.legacyData));
    }

    const endpoint = (global.OilRiskConfig && global.OilRiskConfig.MARKET_API_ENDPOINTS && global.OilRiskConfig.MARKET_API_ENDPOINTS.latest)
      || "/api/market/latest";
    const payload = await requestJson(endpoint);
    const observations = normalizeApiPayload(payload);
    remember(observations);
    return latestByInstrument(observations);
  }

  async function getMarketHistory(instrumentId, days, options) {
    const settings = options || {};
    const instrument = getInstrument(instrumentId);
    const requestedDays = positiveInteger(days, global.OilRiskConfig.marketHistoryDays || 90);

    if (isLegacyMode()) {
      const observations = global.OilRiskMarketCalculations.observationsForInstrument(
        legacyObservations(settings.legacyData),
        instrument.id
      );
      return global.OilRiskMarketCalculations.calendarWindow(observations, requestedDays);
    }

    const query = new URLSearchParams({
      instrument: instrument.id,
      days: String(requestedDays)
    });
    const endpoint = (global.OilRiskConfig && global.OilRiskConfig.MARKET_API_ENDPOINTS && global.OilRiskConfig.MARKET_API_ENDPOINTS.history)
      || "/api/market/history";
    const payload = await requestJson(`${endpoint}?${query}`);
    const observations = normalizeApiPayload(payload)
      .filter((observation) => observation.instrumentId === instrument.id);
    remember(observations);
    return observations;
  }

  async function refreshMarketData() {
    if (isLegacyMode()) {
      return {
        configured: false,
        message: "Automated market refresh is not configured while legacy mode is active."
      };
    }

    const endpoint = (global.OilRiskConfig && global.OilRiskConfig.MARKET_API_ENDPOINTS && global.OilRiskConfig.MARKET_API_ENDPOINTS.refresh)
      || "/api/market/refresh";
    const refreshResult = await requestJson(endpoint, {
      method: "POST"
    });

    // Re-fetch snapshot immediately following refresh
    let snapshot = null;
    try {
      snapshot = await getDashboardSnapshot();
    } catch (_) {
      // Snapshot reload optional if refreshResult contains status
    }

    return {
      configured: true,
      data: refreshResult,
      snapshot
    };
  }

  async function importExcelWorkbook(file) {
    if (!file) {
      throw new Error("No workbook selected.");
    }
    const endpoint = (global.OilRiskConfig && global.OilRiskConfig.MARKET_API_ENDPOINTS && global.OilRiskConfig.MARKET_API_ENDPOINTS.importExcel)
      || "/api/market/import-excel";
    const formData = new FormData();
    formData.append("workbook", file);
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    const timeoutId = global.setTimeout(() => controller && controller.abort(), 180000);
    let response;

    try {
      response = await global.fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        body: formData,
        ...(controller ? { signal: controller.signal } : {})
      });
    } catch (error) {
      const timeoutError = error && error.name === "AbortError";
      const requestError = new Error(timeoutError
        ? "The workbook upload timed out."
        : "The dashboard could not reach the import service.");
      requestError.code = timeoutError ? "TIMEOUT" : "NETWORK_ERROR";
      throw requestError;
    } finally {
      global.clearTimeout(timeoutId);
    }

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = Array.isArray(payload.detail)
        ? payload.detail.map((item) => item && (item.msg || item.detail)).filter(Boolean).join("; ")
        : payload.detail || payload.message;
      const error = new Error(detail || `Excel import failed with HTTP ${response.status}.`);
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  async function prepareDashboardData(dashboardData) {
    const data = global.OilRiskData.cloneDashboardData(dashboardData);

    if (isLegacyMode()) {
      return prepareLegacyDashboardData(data);
    }

    try {
      // 1. Primary initial-load endpoint: GET /api/dashboard/snapshot
      const snapshot = await getDashboardSnapshot();

      // 2. Fetch latest observations from backend (or construct from snapshot)
      let observations = [];
      try {
        const latestList = await getLatestMarketData();
        observations = global.OilRiskMarketDataModel.normalizeCollection(latestList);
      } catch (_) {
        observations = observationsFromSnapshot(snapshot);
      }

      if (!observations.length && snapshot && Array.isArray(snapshot.market_stats)) {
        observations = observationsFromSnapshot(snapshot);
      }

      const historyByInstrument = await loadMarketHistoryByInstrument(90);
      const historyObservations = Object.values(historyByInstrument).flat();
      if (historyObservations.length) {
        observations = mergeObservations(historyObservations.concat(observations));
      }

      const hasExcelSource = (snapshot && Array.isArray(snapshot.market_stats)) && snapshot.market_stats.some((stat) => stat.provider === "internal_excel");
      const sourceLabel = hasExcelSource ? "Hybrid market sources" : "OilPriceAPI";
      const status = global.OilRiskMarketDataModel.buildStatus(observations, {
        stale: false,
        source: sourceLabel,
        lastRefreshed: snapshot ? snapshot.generated_at : new Date().toISOString()
      });

      const prepared = applyObservationsToDashboard(data, observations, status);
      prepared.backendSnapshot = snapshot;
      prepared.backendMarketStats = indexMarketStats(snapshot ? snapshot.market_stats : []);
      attachMarketHistories(prepared.backendMarketStats, historyByInstrument);
      prepared.macroIndicators = normalizeMacroIndicators(snapshot ? snapshot.macro_indicators : []);
      prepared.source = {
        type: "api",
        label: sourceLabel,
        lastRefreshed: snapshot ? (snapshot.generated_at || snapshot.snapshot_date) : new Date().toISOString(),
        refreshedAtFormatted: formatIsoToUtc(snapshot ? snapshot.generated_at : null)
      };
      prepared.apiUnavailable = false;

      // Remember session-level successful data
      lastSuccessfulSnapshot = snapshot;
      lastSuccessfulObservations = observations;
      lastSuccessfulHistoryByInstrument = historyByInstrument;

      return prepared;
    } catch (error) {
      // If we have previous successful API data in-memory, retain it marked as stale
      if (lastSuccessfulSnapshot && lastSuccessfulObservations) {
        const status = global.OilRiskMarketDataModel.buildStatus(lastSuccessfulObservations, {
          stale: true,
          error: serviceError(error)
        });
        const prepared = applyObservationsToDashboard(data, lastSuccessfulObservations, status);
        prepared.backendSnapshot = lastSuccessfulSnapshot;
        prepared.backendMarketStats = indexMarketStats(lastSuccessfulSnapshot.market_stats || []);
        attachMarketHistories(prepared.backendMarketStats, lastSuccessfulHistoryByInstrument);
        prepared.macroIndicators = normalizeMacroIndicators(lastSuccessfulSnapshot.macro_indicators || [], { forceStale: true });
        prepared.source = {
          type: "api",
          label: "OilPriceAPI (Stale)",
          lastRefreshed: lastSuccessfulSnapshot.generated_at,
          refreshedAtFormatted: formatIsoToUtc(lastSuccessfulSnapshot.generated_at),
          stale: true,
          errorMessage: "Live market data temporarily unavailable."
        };
        prepared.apiUnavailable = true;
        prepared.apiErrorMessage = "Live market data temporarily unavailable.";
        return prepared;
      }

      // DO NOT silently fall back to legacy market data!
      // Return honest API-unavailable state with empty observations
      data.marketObservations = [];
      data.backendSnapshot = null;
      data.backendMarketStats = {};
      data.macroIndicators = normalizeMacroIndicators([]);
      data.apiUnavailable = true;
      data.apiErrorMessage = "Live market data temporarily unavailable.";
      data.source = {
        type: "api",
        label: "OilPriceAPI (Unavailable)",
        lastRefreshed: null,
        unavailable: true,
        errorMessage: "Live market data temporarily unavailable."
      };
      data.marketDataStatus = {
        configured: true,
        stale: true,
        totalObservations: 0,
        missingInstruments: Object.keys(global.OilRiskConfig.MARKET_INSTRUMENTS || {}),
        error: {
          code: "API_UNAVAILABLE",
          message: "Live market data temporarily unavailable."
        }
      };

      // Set KRIs to unavailable/null so no legacy prices leak
      const kriCodes = global.OilRiskLegacyMarketDataAdapter.DASHBOARD_KRI_CODES;
      Object.keys(kriCodes).forEach((id) => {
        const kri = data.kris && data.kris[kriCodes[id]];
        if (kri) {
          kri.currentValue = null;
          kri.previousValue = null;
          kri.history = [];
        }
      });
      data.plattsBrentHistory = [];

      return data;
    }
  }

  function prepareLegacyDashboardData(dashboardData) {
    const data = global.OilRiskData.cloneDashboardData(dashboardData);
    const observations = legacyObservations(data);
    const status = global.OilRiskMarketDataModel.buildStatus(observations);
    const prepared = applyObservationsToDashboard(data, observations, status);
    prepared.macroIndicators = normalizeMacroIndicators(data.macroIndicators || data.macro_indicators || []);
    return prepared;
  }

  function observationsFromSnapshot(snapshot) {
    if (!snapshot || !Array.isArray(snapshot.market_stats)) {
      return [];
    }

    return snapshot.market_stats
      .filter((stat) => stat.current_value !== null && Number.isFinite(Number(stat.current_value)))
      .map((stat) => ({
        instrumentId: stat.instrument_id,
        providerSymbol: stat.provider_symbol || null,
        name: stat.provider_display_name || stat.display_name,
        value: Number(stat.current_value),
        unit: stat.unit || "USD/bbl",
        assessmentDate: stat.latest_date || snapshot.snapshot_date,
        retrievedAt: stat.retrieved_at || snapshot.generated_at,
        provider: stat.provider || "oilpriceapi",
        sourceType: stat.provider === "internal_excel" ? "excel" : "api",
        sourceTimestamp: stat.source_timestamp || null,
        ageSeconds: 0,
        freshnessStatus: stat.freshness_status || "fresh",
        benchmarkStatus: stat.benchmark_status,
        providerDisplayName: stat.provider_display_name,
        benchmarkDefinition: stat.benchmark_definition || ""
      }));
  }

  function indexMarketStats(statsList) {
    const map = {};
    (statsList || []).forEach((stat) => {
      if (stat && stat.instrument_id) {
        map[stat.instrument_id] = stat;
      }
    });
    return map;
  }

  async function loadMarketHistoryByInstrument(days) {
    const instruments = Object.values(global.OilRiskConfig.MARKET_INSTRUMENTS || {})
      .filter((instrument) => instrument.enabled)
      .map((instrument) => instrument.id);
    const entries = await Promise.all(instruments.map(async (instrumentId) => {
      try {
        return [instrumentId, await getMarketHistory(instrumentId, days)];
      } catch (_) {
        return [instrumentId, []];
      }
    }));

    return Object.fromEntries(entries);
  }

  function attachMarketHistories(statsMap, historyByInstrument) {
    Object.entries(historyByInstrument || {}).forEach(([instrumentId, history]) => {
      if (statsMap[instrumentId] && Array.isArray(history) && history.length) {
        statsMap[instrumentId].history = history;
      }
    });
  }

  function mergeObservations(...collections) {
    const byObservation = new Map();

    collections.flat().forEach((observation) => {
      if (!observation || !observation.instrumentId || !observation.assessmentDate) {
        return;
      }

      byObservation.set(
        `${observation.instrumentId}|${observation.assessmentDate}`,
        observation
      );
    });

    return global.OilRiskMarketDataModel.normalizeCollection(Array.from(byObservation.values()));
  }

  function normalizeMacroIndicators(indicators, options) {
    const settings = options || {};
    const byKey = {};

    (Array.isArray(indicators) ? indicators : []).forEach((indicator) => {
      if (indicator && indicator.indicator_key) {
        byKey[indicator.indicator_key] = indicator;
      }
    });

    return MACRO_INDICATOR_DEFAULTS.map((defaults) => {
      const raw = byKey[defaults.indicator_key];

      if (!raw) {
        return {
          id: null,
          indicator_key: defaults.indicator_key,
          display_name: defaults.display_name,
          value: null,
          unit: defaults.unit,
          reporting_period: "Unavailable",
          source: defaults.source,
          source_url: null,
          published_at: null,
          retrieved_at: null,
          status: "unavailable",
          freshness_status: "unavailable",
          metadata_json: {}
        };
      }

      const valueNumber = raw.value === null || raw.value === undefined || raw.value === ""
        ? null
        : Number(raw.value);
      const hasNumericValue = Number.isFinite(valueNumber);
      const rawFreshness = String(raw.freshness_status || raw.freshnessStatus || "").toLowerCase();
      const rawStatus = String(raw.status || "published").toLowerCase();
      const shouldForceStale = settings.forceStale && hasNumericValue &&
        rawFreshness !== "unavailable" &&
        rawFreshness !== "extraction_error" &&
        rawStatus !== "unavailable";

      return {
        id: raw.id ?? null,
        indicator_key: defaults.indicator_key,
        display_name: raw.display_name || defaults.display_name,
        value: hasNumericValue ? valueNumber : null,
        unit: raw.unit || defaults.unit,
        reporting_period: raw.reporting_period || "Unavailable",
        source: raw.source || defaults.source,
        source_url: raw.source_url || null,
        published_at: raw.published_at || null,
        retrieved_at: raw.retrieved_at || null,
        status: hasNumericValue ? (raw.status || "published") : "unavailable",
        freshness_status: shouldForceStale
          ? "stale"
          : (raw.freshness_status || raw.freshnessStatus || (hasNumericValue ? "fresh" : "unavailable")),
        metadata_json: raw.metadata_json || raw.metadataJson || {}
      };
    });
  }

  function applyObservationsToDashboard(dashboardData, observations, status) {
    const data = dashboardData;
    const normalized = global.OilRiskMarketDataModel.normalizeCollection(observations);
    const kriCodes = global.OilRiskLegacyMarketDataAdapter.DASHBOARD_KRI_CODES;

    data.marketObservations = normalized;
    data.marketDataStatus = status || global.OilRiskMarketDataModel.buildStatus(normalized);

    Object.keys(kriCodes).forEach((instrumentId) => {
      const history = global.OilRiskMarketCalculations.observationsForInstrument(normalized, instrumentId);
      const latest = history[history.length - 1];
      const previous = history[history.length - 2] || latest;
      const kri = data.kris && data.kris[kriCodes[instrumentId]];

      if (!kri) {
        return;
      }

      if (latest && Number.isFinite(Number(latest.value))) {
        kri.currentValue = latest.value;
        kri.previousValue = previous ? previous.value : null;
        kri.history = global.OilRiskMarketCalculations.toHistoryPoints(history);
        kri.unit = latest.unit || kri.unit;
        kri.providerSymbol = latest.providerSymbol;
      } else {
        kri.currentValue = null;
        kri.previousValue = null;
        kri.history = [];
      }
    });

    const brentHistory = global.OilRiskMarketCalculations.observationsForInstrument(normalized, "brent");
    data.plattsBrentHistory = global.OilRiskMarketCalculations.toHistoryPoints(brentHistory);

    if (data.source && data.marketDataStatus) {
      data.source.marketStatus = data.marketDataStatus;
    }

    return data;
  }

  function legacyObservations(data) {
    if (data && Array.isArray(data.marketObservations) && data.marketObservations.length) {
      return global.OilRiskMarketDataModel.normalizeCollection(data.marketObservations);
    }

    return global.OilRiskLegacyMarketDataAdapter.fromDashboardData(data || global.dashboardData);
  }

  function normalizeApiPayload(payload) {
    const rawObservations = Array.isArray(payload)
      ? payload
      : payload && Array.isArray(payload.observations)
        ? payload.observations
        : [];

    return global.OilRiskMarketDataModel.normalizeCollection(rawObservations, { strictApi: false });
  }

  async function requestJson(url, options) {
    if (typeof global.fetch !== "function") {
      throw new global.OilRiskMarketDataModel.MarketDataError(
        "PROVIDER_UNAVAILABLE",
        "The browser cannot reach the dashboard backend."
      );
    }

    let response;

    try {
      response = await global.fetch(url, {
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        ...(options || {})
      });
    } catch (error) {
      throw new global.OilRiskMarketDataModel.MarketDataError(
        "PROVIDER_UNAVAILABLE",
        "Live market data temporarily unavailable.",
        { cause: error.message }
      );
    }

    if (response.status === 429) {
      throw new global.OilRiskMarketDataModel.MarketDataError(
        "RATE_LIMITED",
        "The market data service rate limit has been reached."
      );
    }

    if (!response.ok) {
      throw new global.OilRiskMarketDataModel.MarketDataError(
        "PROVIDER_UNAVAILABLE",
        `Live market data temporarily unavailable (HTTP ${response.status}).`
      );
    }

    try {
      return await response.json();
    } catch (error) {
      throw new global.OilRiskMarketDataModel.MarketDataError(
        "INVALID_API_RESPONSE",
        "The market data service returned invalid JSON."
      );
    }
  }

  function getInstrument(instrumentId) {
    const instrument = global.OilRiskConfig.MARKET_INSTRUMENTS[String(instrumentId || "").toLowerCase()];

    if (!instrument || !instrument.enabled) {
      throw new global.OilRiskMarketDataModel.MarketDataError(
        "MISSING_INSTRUMENT",
        `Unknown or disabled market instrument: ${instrumentId || "(blank)"}.`
      );
    }

    return instrument;
  }

  function latestByInstrument(observations) {
    const groups = global.OilRiskMarketDataModel.groupByInstrument(observations);
    return Object.values(groups).map((history) => history[history.length - 1]);
  }

  function remember(observations) {
    const groups = global.OilRiskMarketDataModel.groupByInstrument(observations);
    Object.keys(groups).forEach((instrumentId) => memoryCache.set(instrumentId, groups[instrumentId]));
  }

  function positiveInteger(value, fallback) {
    const number = Number(value);
    return Number.isInteger(number) && number > 0 ? number : fallback;
  }

  function isLegacyMode() {
    return global.OilRiskConfig.dataSourceMode !== "api";
  }

  function serviceError(error) {
    return {
      code: error && error.code || "PROVIDER_UNAVAILABLE",
      message: error && error.message || "Live market data temporarily unavailable."
    };
  }

  function formatIsoToUtc(isoString) {
    if (!isoString) return "--";
    try {
      const dt = new Date(isoString);
      if (isNaN(dt.getTime())) return isoString;
      return dt.toUTCString().replace("GMT", "UTC");
    } catch (_) {
      return isoString;
    }
  }

  function clearSessionCache() {
    lastSuccessfulSnapshot = null;
    lastSuccessfulObservations = null;
    lastSuccessfulHistoryByInstrument = {};
    memoryCache.clear();
  }

  global.OilRiskMarketDataService = {
    applyObservationsToDashboard,
    clearSessionCache,
    getDashboardSnapshot,
    getLatestMarketData,
    getMarketHistory,
    importExcelWorkbook,
    normalizeMacroIndicators,
    prepareDashboardData,
    prepareLegacyDashboardData,
    refreshMarketData
  };
})(typeof window !== "undefined" ? window : globalThis);
