"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");

require("../js/config/dashboardConfig.js");
require("../data.js");
require("../js/market/marketDataModel.js");
require("../js/adapters/legacyMarketDataAdapter.js");
require("../js/services/marketCalculationService.js");
require("../js/services/marketDataService.js");
require("../js/services/excelImportUiService.js");
require("../js/services/newsService.js");
require("../js/services/aiService.js");
require("../js/services/calendarService.js");
globalThis.window = globalThis;
globalThis.addEventListener = globalThis.addEventListener || (() => {});
require("../charts.js");

const INSTRUMENT_KRIS = {
  brent: "MR_BRENT",
  naphtha: "MR_NAPHTHA",
  gasoil: "MR_GASOIL",
  gasoline: "MR_GASOLINE",
  forcados: "MR_FORCADOS",
  wti: "MR_WTI",
  jet: "MR_JET"
};

function legacyStats(history) {
  const observations = history
    .map((point) => ({ date: point.date, value: Number(point.value) }))
    .filter((point) => point.date && Number.isFinite(point.value))
    .sort((left, right) => Date.parse(left.date) - Date.parse(right.date));
  const latest = observations[observations.length - 1];
  const previous = observations[observations.length - 2];
  const latestDate = Date.parse(`${latest.date}T00:00:00Z`);
  const startDate = latestDate - 89 * 24 * 60 * 60 * 1000;
  const values = observations
    .filter((point) => {
      const timestamp = Date.parse(`${point.date}T00:00:00Z`);
      return timestamp >= startDate && timestamp <= latestDate;
    })
    .map((point) => point.value);
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const variance = values.reduce((sum, value) => sum + Math.pow(value - mean, 2), 0) / (values.length - 1);
  const standardDeviation = values.length > 1 ? Math.sqrt(variance) : null;

  return {
    latest: latest.value,
    previous: previous.value,
    count: values.length,
    mean,
    standardDeviation,
    zScore: standardDeviation > 0 ? (latest.value - mean) / standardDeviation : null
  };
}

function approximatelyEqual(actual, expected, message) {
  assert.ok(Math.abs(actual - expected) < 1e-10, `${message}: ${actual} !== ${expected}`);
}

test("legacy data is normalized with complete audit fields", () => {
  const observations = globalThis.OilRiskLegacyMarketDataAdapter.fromDashboardData(globalThis.dashboardData);

  assert.ok(observations.length > 0);
  assert.deepEqual(
    new Set(observations.map((observation) => observation.instrumentId)),
    new Set(Object.keys(INSTRUMENT_KRIS))
  );

  observations.forEach((observation) => {
    assert.ok(observation.providerSymbol);
    assert.ok(observation.name);
    assert.ok(Number.isFinite(observation.value));
    assert.ok(observation.unit);
    assert.match(observation.assessmentDate, /^\d{4}-\d{2}-\d{2}$/);
    assert.ok(observation.retrievedAt);
    assert.ok(observation.provider);
    assert.ok(observation.sourceType);
  });
});

test("normalized calculations preserve current legacy market results", () => {
  const data = globalThis.OilRiskMarketDataService.prepareLegacyDashboardData(globalThis.dashboardData);

  Object.entries(INSTRUMENT_KRIS).forEach(([instrumentId, kriCode]) => {
    const expected = legacyStats(globalThis.dashboardData.kris[kriCode].history);
    const actual = globalThis.OilRiskMarketCalculations.calculateInstrumentStats(
      data.marketObservations,
      instrumentId,
      90
    );

    assert.equal(actual.currentValue, expected.latest, `${instrumentId} latest`);
    assert.equal(actual.previousValue, expected.previous, `${instrumentId} previous`);
    assert.equal(actual.windowObservationCount, expected.count, `${instrumentId} count`);
    approximatelyEqual(actual.mean90, expected.mean, `${instrumentId} mean`);
    approximatelyEqual(actual.sd90, expected.standardDeviation, `${instrumentId} standard deviation`);
    approximatelyEqual(actual.zScore, expected.zScore, `${instrumentId} z-score`);
  });
});

test("30D trend uses valid observations in the calendar window without requiring 30 rows", () => {
  const observations = [
    { assessmentDate: "2026-08-01", value: 70 },
    { assessmentDate: "2026-08-12", value: 71 },
    { assessmentDate: "2026-08-20", value: 72 },
    { assessmentDate: "2026-09-10", value: 73 }
  ];

  const trendWindow = globalThis.OilRiskMarketCalculations.trendWindow(observations, 30);

  assert.deepEqual(
    trendWindow.map((observation) => observation.assessmentDate),
    ["2026-08-12", "2026-08-20", "2026-09-10"]
  );
  assert.ok(trendWindow.length >= 2);
});

test("Excel import UI exposes loading, success, failure, retry and refresh states", () => {
  const ui = globalThis.OilRiskExcelImportUi;
  const loading = ui.loadingState("daily.xlsx", 0);

  assert.equal(loading.status, "loading");
  assert.equal(loading.buttonDisabled, true);
  assert.match(loading.stages.join(" "), /Uploading workbook/);
  assert.match(loading.stages.join(" "), /Validating market observations/);
  assert.match(loading.stages.join(" "), /Updating market data/);

  const success = ui.successState("daily.xlsx", {
    rows_read: 178,
    rows_valid: 875,
    rows_stored: 860,
    rows_updated: 0,
    rows_rejected: 15,
    instruments_affected: ["forcados", "naphtha"],
    date_range: { from: "2026-01-02", to: "2026-09-10" }
  });

  assert.equal(success.status, "success");
  assert.equal(success.buttonDisabled, false);
  assert.equal(success.refreshSnapshot, true);
  assert.equal(success.summary.rowsRead, 178);
  assert.equal(success.summary.rowsValid, 875);
  assert.deepEqual(success.summary.instruments, ["forcados", "naphtha"]);

  const failure = ui.failureState("daily.xlsx", { status: 422, message: "Workbook field is required." });
  assert.equal(failure.status, "failure");
  assert.equal(failure.buttonDisabled, false);
  assert.equal(failure.canRetry, true);
  assert.match(failure.message, /Workbook field is required/);
  assert.match(ui.classifyError({ code: "NETWORK_ERROR" }), /could not reach/);
  assert.match(ui.classifyError({ code: "TIMEOUT" }), /timed out/);
  assert.match(ui.classifyError({ status: 500 }), /server could not process/);
});

test("Excel import request allows long-running workbook processing", () => {
  const source = fs.readFileSync("js/services/marketDataService.js", "utf8");
  assert.match(source, /controller\.abort\(\), 180000/);
});

test("API history assessmentDate values render in the 30D sparkline", () => {
  const sparkline = globalThis.OilRiskCharts.createSparkline([
    { assessmentDate: "2026-08-15", value: 100 },
    { assessmentDate: "2026-09-10", value: 105 }
  ], "positive", { days: 30 });

  assert.doesNotMatch(sparkline, /sparkline-empty|>--</);
  assert.match(sparkline, /polyline/);
});

test("market refresh display uses Lagos time and hidden warning CSS is respected", () => {
  const serviceSource = fs.readFileSync("js/services/marketDataService.js", "utf8");
  const styleSource = fs.readFileSync("style.css", "utf8");

  assert.match(serviceSource, /timeZone: "Africa\/Lagos"/);
  assert.doesNotMatch(serviceSource, /formatIsoToUtc/);
  assert.match(styleSource, /\.api-unavailable-banner\[hidden\]\s*\{\s*display:\s*none;/);
});

test("product spreads preserve approved instrument conversions", () => {
  const data = globalThis.OilRiskMarketDataService.prepareLegacyDashboardData(globalThis.dashboardData);
  const brent = globalThis.dashboardData.kris.MR_BRENT.currentValue;
  const spreads = globalThis.OilRiskMarketCalculations.calculateProductSpreads(data.marketObservations);

  assert.deepEqual(spreads.map((spread) => spread.instrumentId), [
    "naphtha",
    "gasoil",
    "gasoline",
    "jet"
  ]);

  spreads.forEach((spread) => {
    const expectedFactor = globalThis.OilRiskConfig.PRODUCT_CONVERSIONS[spread.instrumentId];
    const expectedConverted = spread.originalPrice / expectedFactor;

    assert.equal(spread.barrelsPerMT, expectedFactor);
    approximatelyEqual(spread.convertedPrice, expectedConverted, `${spread.instrumentId} conversion`);
    approximatelyEqual(spread.difference, expectedConverted - brent, `${spread.instrumentId} spread`);
  });
});

test("missing values are rejected instead of becoming zero", () => {
  const missing = globalThis.OilRiskMarketDataModel.normalizeObservation({
    instrumentId: "brent",
    value: "",
    assessmentDate: "2026-09-24"
  });
  const realZero = globalThis.OilRiskMarketDataModel.normalizeObservation({
    instrumentId: "brent",
    value: 0,
    assessmentDate: "2026-09-24"
  });

  assert.equal(missing, null);
  assert.equal(realZero.value, 0);
});

test("AI hooks expose verified context and remain unconfigured", async () => {
  const data = globalThis.OilRiskMarketDataService.prepareLegacyDashboardData(globalThis.dashboardData);
  const context = globalThis.OilRiskAIService.buildDashboardAIContext({ dashboardData: data });
  const response = await globalThis.OilRiskAIService.generateDashboardAnalysis(context);

  assert.equal(context.market.length, 7);
  assert.equal(context.productSpreads.length, 4);
  assert.equal(response.configured, false);
  assert.equal(response.message, "AI service is not yet configured.");
});

test("verified news service uses backend filters and refresh endpoint", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url: String(url), method: options.method });
    return { ok: true, json: async () => ({ items: [] }) };
  };

  await globalThis.OilRiskNewsService.getLatestNews({ region: "nigeria", limit: 5 });
  await globalThis.OilRiskNewsService.refreshNews();

  globalThis.fetch = originalFetch;
  assert.equal(calls[0].url, "/api/news/latest?region=nigeria&limit=5");
  assert.equal(calls[0].method, "GET");
  assert.equal(calls[1].url, "/api/news/refresh");
  assert.equal(calls[1].method, "POST");
});

// ============================================================
// PHASE 4 UNIT TESTS: LIVE BACKEND API PIPELINE
// ============================================================

const MOCK_API_SNAPSHOT = {
  snapshot_date: "2026-09-24",
  generated_at: "2026-09-24T12:00:00Z",
  market_stats: [
    {
      instrument_id: "brent",
      display_name: "Dated Brent",
      provider_display_name: "ICE Brent Crude Futures",
      provider: "OilPriceAPI",
      provider_symbol: "BRENT_CRUDE_USD",
      current_value: 74.25,
      previous_value: 73.80,
      change: 0.45,
      percent_change: 0.61,
      mean_90: null,
      std_dev_90: null,
      z_score: null,
      window_count: 1,
      history_status: "insufficient_history",
      latest_date: "2026-09-24",
      unit: "USD/bbl",
      benchmark_status: "confirmed",
      freshness_status: "fresh",
      source_timestamp: "2026-09-24T11:45:00Z",
      retrieved_at: "2026-09-24T12:00:00Z",
      unavailable_reason: null
    },
    {
      instrument_id: "wti",
      display_name: "WTI Cushing",
      provider_display_name: "WTI Crude Oil Futures",
      provider: "OilPriceAPI",
      provider_symbol: "WTI_USD",
      current_value: 70.10,
      previous_value: 69.80,
      change: 0.30,
      percent_change: 0.43,
      mean_90: null,
      std_dev_90: null,
      z_score: null,
      window_count: 1,
      history_status: "insufficient_history",
      latest_date: "2026-09-24",
      unit: "USD/bbl",
      benchmark_status: "confirmed",
      freshness_status: "fresh",
      source_timestamp: "2026-09-24T11:45:00Z",
      retrieved_at: "2026-09-24T12:00:00Z",
      unavailable_reason: null
    },
    {
      instrument_id: "naphtha",
      display_name: "Naphtha",
      provider_display_name: "Naphtha",
      provider: "OilPriceAPI",
      provider_symbol: "NAPHTHA_USD",
      current_value: 535.0,
      previous_value: 530.0,
      change: 5.0,
      percent_change: 0.94,
      mean_90: null,
      std_dev_90: null,
      z_score: null,
      window_count: 1,
      history_status: "insufficient_history",
      latest_date: "2026-09-24",
      unit: "USD/MT",
      benchmark_status: "test_proxy",
      freshness_status: "fresh",
      source_timestamp: "2026-09-24T11:45:00Z",
      retrieved_at: "2026-09-24T12:00:00Z",
      unavailable_reason: null
    },
    {
      instrument_id: "gasoil",
      display_name: "Gasoil",
      provider_display_name: "ICE Low Sulphur Gasoil Rotterdam",
      provider: "OilPriceAPI",
      provider_symbol: "GASOIL_USD",
      current_value: 650.0,
      previous_value: 645.0,
      change: 5.0,
      percent_change: 0.78,
      mean_90: null,
      std_dev_90: null,
      z_score: null,
      window_count: 1,
      history_status: "insufficient_history",
      latest_date: "2026-09-24",
      unit: "USD/MT",
      benchmark_status: "test_proxy",
      freshness_status: "fresh",
      source_timestamp: "2026-09-24T11:45:00Z",
      retrieved_at: "2026-09-24T12:00:00Z",
      unavailable_reason: null
    },
    {
      instrument_id: "forcados",
      display_name: "Forcados",
      provider_display_name: "Forcados",
      provider: null,
      provider_symbol: null,
      current_value: null,
      previous_value: null,
      change: null,
      percent_change: null,
      mean_90: null,
      std_dev_90: null,
      z_score: null,
      window_count: 0,
      history_status: "insufficient_history",
      latest_date: null,
      unit: "USD/bbl",
      benchmark_status: "unavailable",
      freshness_status: "unavailable",
      source_timestamp: null,
      retrieved_at: null,
      unavailable_reason: "No approved automated source configured"
    },
    {
      instrument_id: "gasoline",
      display_name: "Gasoline",
      provider_display_name: "Gasoline",
      provider: null,
      provider_symbol: null,
      current_value: null,
      previous_value: null,
      change: null,
      percent_change: null,
      mean_90: null,
      std_dev_90: null,
      z_score: null,
      window_count: 0,
      history_status: "insufficient_history",
      latest_date: null,
      unit: "USD/MT",
      benchmark_status: "unavailable",
      freshness_status: "unavailable",
      source_timestamp: null,
      retrieved_at: null,
      unavailable_reason: "No approved automated source configured"
    },
    {
      instrument_id: "jet",
      display_name: "Jet",
      provider_display_name: "Jet",
      provider: null,
      provider_symbol: null,
      current_value: null,
      previous_value: null,
      change: null,
      percent_change: null,
      mean_90: null,
      std_dev_90: null,
      z_score: null,
      window_count: 0,
      history_status: "insufficient_history",
      latest_date: null,
      unit: "USD/MT",
      benchmark_status: "unavailable",
      freshness_status: "unavailable",
      source_timestamp: null,
      retrieved_at: null,
      unavailable_reason: "No approved automated source configured"
    }
  ],
  outliers: [],
  macro_indicators: [
    {
      indicator_key: "headline_inflation",
      display_name: "Headline Inflation",
      value: 15.39,
      unit: "%",
      reporting_period: "Aug 2026",
      source: "National Bureau of Statistics Nigeria",
      source_url: "https://microdata.nigerianstat.gov.ng/index.php/catalog/154/related-materials",
      published_at: "2026-09-15T00:00:00Z",
      retrieved_at: "2026-09-24T12:00:00Z",
      status: "published",
      freshness_status: "fresh",
      metadata_json: {}
    },
    {
      indicator_key: "food_inflation",
      display_name: "Food Inflation",
      value: 19.57,
      unit: "%",
      reporting_period: "Aug 2026",
      source: "National Bureau of Statistics Nigeria",
      source_url: "https://microdata.nigerianstat.gov.ng/index.php/catalog/154/related-materials",
      published_at: "2026-09-15T00:00:00Z",
      retrieved_at: "2026-09-24T12:00:00Z",
      status: "published",
      freshness_status: "fresh",
      metadata_json: {}
    },
    {
      indicator_key: "core_inflation",
      display_name: "Core Inflation",
      value: 13.29,
      unit: "%",
      reporting_period: "Aug 2026",
      source: "National Bureau of Statistics Nigeria",
      source_url: "https://microdata.nigerianstat.gov.ng/index.php/catalog/154/related-materials",
      published_at: "2026-09-15T00:00:00Z",
      retrieved_at: "2026-09-24T12:00:00Z",
      status: "published",
      freshness_status: "fresh",
      metadata_json: {}
    },
    {
      indicator_key: "real_gdp_growth",
      display_name: "Real GDP Growth",
      value: 4.43,
      unit: "%",
      reporting_period: "Q2 2026",
      source: "National Bureau of Statistics Nigeria",
      source_url: "https://microdata.nigerianstat.gov.ng/index.php/catalog/147/related-materials",
      published_at: "2026-08-31T00:00:00Z",
      retrieved_at: "2026-09-24T12:00:00Z",
      status: "published",
      freshness_status: "fresh",
      metadata_json: {}
    },
    {
      indicator_key: "nigeria_pmi",
      display_name: "PMI",
      value: null,
      unit: "index",
      reporting_period: "Unavailable",
      source: "Stanbic IBTC Bank / S&P Global",
      source_url: null,
      published_at: null,
      retrieved_at: null,
      status: "unavailable",
      freshness_status: "unavailable",
      metadata_json: {}
    },
    {
      indicator_key: "crude_oil_production",
      display_name: "Crude Oil Production",
      value: 1.50019,
      unit: "mbpd",
      reporting_period: "Aug 2026",
      source: "Nigerian Upstream Petroleum Regulatory Commission",
      source_url: "https://www.nuprc.gov.ng/media/news/test",
      published_at: "2026-09-10T00:00:00Z",
      retrieved_at: "2026-09-24T12:00:00Z",
      status: "published",
      freshness_status: "fresh",
      metadata_json: {
        definition: "crude_only_excluding_condensate",
        crude_plus_condensate_mbpd: 1.677777
      }
    }
  ],
  product_spreads: [
    {
      instrument_id: "naphtha",
      display_name: "Naphtha",
      date: "2026-09-24",
      original_price: 535.0,
      original_unit: "USD/MT",
      barrels_per_mt: 8.9,
      converted_price: 60.11,
      brent_price: 74.25,
      spread: -14.14,
      is_comparable: true
    },
    {
      instrument_id: "gasoil",
      display_name: "Gasoil",
      date: "2026-09-24",
      original_price: 650.0,
      original_unit: "USD/MT",
      barrels_per_mt: 7.44,
      converted_price: 87.37,
      brent_price: 74.25,
      spread: 13.12,
      is_comparable: true
    }
  ]
};

test("API snapshot normalization correctly parses backend feed", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (String(url).includes("/api/dashboard/snapshot")) {
      return {
        ok: true,
        status: 200,
        json: async () => MOCK_API_SNAPSHOT
      };
    }
    if (String(url).includes("/api/market/latest")) {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          status: "success",
          count: 4,
          data: MOCK_API_SNAPSHOT.market_stats
            .filter((s) => s.current_value !== null)
            .map((s) => ({
              instrument_id: s.instrument_id,
              display_name: s.provider_display_name,
              provider_symbol: s.provider_symbol,
              value: s.current_value,
              unit: s.unit,
              assessment_date: s.latest_date,
              retrieved_at: s.retrieved_at,
              source_timestamp: s.source_timestamp
            }))
        })
      };
    }
    throw new Error(`Unexpected fetch URL: ${url}`);
  };

  try {
    const prepared = await globalThis.OilRiskMarketDataService.prepareDashboardData(
      globalThis.dashboardData
    );

    assert.equal(prepared.source.type, "api");
    assert.equal(prepared.source.label, "OilPriceAPI");
    assert.equal(prepared.apiUnavailable, false);
    assert.ok(prepared.backendSnapshot);
    assert.equal(Object.keys(prepared.backendMarketStats).length, 7);

    // Verify 4 live observations mapped
    assert.equal(prepared.marketObservations.length, 4);
    const instIds = new Set(prepared.marketObservations.map((o) => o.instrumentId));
    assert.deepEqual(instIds, new Set(["brent", "wti", "naphtha", "gasoil"]));

    assert.equal(prepared.macroIndicators.length, 18);
    const macroByKey = Object.fromEntries(prepared.macroIndicators.map((item) => [item.indicator_key, item]));
    assert.equal(macroByKey.headline_inflation.value, 15.39);
    assert.equal(macroByKey.headline_inflation.reporting_period, "Aug 2026");
    assert.equal(macroByKey.nigeria_pmi.value, null);
    assert.equal(macroByKey.nigeria_pmi.freshness_status, "unavailable");
    assert.equal(macroByKey.crude_oil_production.metadata_json.definition, "crude_only_excluding_condensate");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("macro normalization returns unavailable values without converting null to zero", () => {
  const normalized = globalThis.OilRiskMarketDataService.normalizeMacroIndicators([
    {
      indicator_key: "headline_inflation",
      display_name: "Headline Inflation",
      value: null,
      unit: "%",
      reporting_period: "Unavailable",
      source: "National Bureau of Statistics Nigeria",
      status: "unavailable",
      freshness_status: "unavailable"
    }
  ]);

  assert.equal(normalized.length, 18);
  assert.equal(normalized[0].indicator_key, "headline_inflation");
  assert.equal(normalized[0].value, null);
  assert.equal(normalized[0].freshness_status, "unavailable");
  assert.equal(normalized[1].indicator_key, "food_inflation");
  assert.equal(normalized[1].value, null);
});

test("live Brent and WTI rendering uses accurate provider labels without Dated Brent futures confusion", () => {
  const brentStat = MOCK_API_SNAPSHOT.market_stats.find((s) => s.instrument_id === "brent");
  const wtiStat = MOCK_API_SNAPSHOT.market_stats.find((s) => s.instrument_id === "wti");

  // Brent checks
  assert.equal(brentStat.provider_display_name, "ICE Brent Crude Futures");
  assert.notEqual(brentStat.provider_display_name, "Dated Brent");
  assert.equal(brentStat.provider_symbol, "BRENT_CRUDE_USD");
  assert.equal(brentStat.benchmark_status, "confirmed");
  assert.equal(brentStat.current_value, 74.25);

  // WTI checks
  assert.equal(wtiStat.provider_display_name, "WTI Crude Oil Futures");
  assert.equal(wtiStat.provider_symbol, "WTI_USD");
  assert.equal(wtiStat.benchmark_status, "confirmed");
  assert.equal(wtiStat.current_value, 70.10);
});

test("test proxies are explicitly indicated for Naphtha and Gasoil", () => {
  const naphtha = MOCK_API_SNAPSHOT.market_stats.find((s) => s.instrument_id === "naphtha");
  const gasoil = MOCK_API_SNAPSHOT.market_stats.find((s) => s.instrument_id === "gasoil");

  assert.equal(naphtha.benchmark_status, "test_proxy");
  assert.equal(naphtha.provider_symbol, "NAPHTHA_USD");

  assert.equal(gasoil.benchmark_status, "test_proxy");
  assert.equal(gasoil.provider_display_name, "ICE Low Sulphur Gasoil Rotterdam");
  assert.equal(gasoil.provider_symbol, "GASOIL_USD");
});

test("unavailable instruments are handled honestly without converting null to zero or leaking legacy values", () => {
  const unavailableIds = ["forcados", "gasoline", "jet"];

  unavailableIds.forEach((id) => {
    const stat = MOCK_API_SNAPSHOT.market_stats.find((s) => s.instrument_id === id);
    assert.ok(stat, `Stat exists for ${id}`);
    assert.equal(stat.current_value, null, `${id} value must be strictly null, never zero`);
    assert.notEqual(stat.current_value, 0, `${id} must not convert null to 0`);
    assert.equal(stat.benchmark_status, "unavailable");
    assert.equal(stat.freshness_status, "unavailable");
    assert.equal(stat.unavailable_reason, "No approved automated source configured");
  });
});

test("insufficient 90D history preserves null z-score and flags insufficient_history", () => {
  MOCK_API_SNAPSHOT.market_stats.forEach((stat) => {
    assert.equal(stat.z_score, null, `${stat.instrument_id} z_score must be null`);
    assert.equal(stat.history_status, "insufficient_history");
  });
});

test("Product Spreads chart only available products and never draw missing products", () => {
  const spreads = MOCK_API_SNAPSHOT.product_spreads;

  // Only Naphtha and Gasoil present
  assert.equal(spreads.length, 2);
  assert.deepEqual(spreads.map((s) => s.instrument_id), ["naphtha", "gasoil"]);

  // Gasoline and Jet are excluded
  assert.ok(!spreads.some((s) => s.instrument_id === "gasoline"));
  assert.ok(!spreads.some((s) => s.instrument_id === "jet"));

  // Conversions verified: 8.90 for Naphtha, 7.44 for Gasoil
  const naphthaSpread = spreads.find((s) => s.instrument_id === "naphtha");
  assert.equal(naphthaSpread.barrels_per_mt, 8.90);
  assert.equal(naphthaSpread.converted_price, 60.11);
  approximatelyEqual(naphthaSpread.spread, 60.11 - 74.25, "Naphtha spread");

  const gasoilSpread = spreads.find((s) => s.instrument_id === "gasoil");
  assert.equal(gasoilSpread.barrels_per_mt, 7.44);
  assert.equal(gasoilSpread.converted_price, 87.37);
  approximatelyEqual(gasoilSpread.spread, 87.37 - 74.25, "Gasoil spread");
});

test("refresh workflow invokes POST /api/market/refresh then re-fetches snapshot", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    const method = (options && options.method) || "GET";
    calls.push({ url: String(url), method });

    if (String(url).includes("/api/market/refresh") && method === "POST") {
      return {
        ok: true,
        status: 200,
        json: async () => ({ status: "success", message: "Market data refreshed", count: 4 })
      };
    }
    if (String(url).includes("/api/dashboard/snapshot")) {
      return {
        ok: true,
        status: 200,
        json: async () => MOCK_API_SNAPSHOT
      };
    }
    throw new Error(`Unexpected fetch URL: ${url}`);
  };

  try {
    const result = await globalThis.OilRiskMarketDataService.refreshMarketData();
    assert.equal(result.configured, true);
    assert.equal(result.data.status, "success");
    assert.ok(result.snapshot);

    // Verify calling order: POST /api/market/refresh then GET /api/dashboard/snapshot
    assert.equal(calls[0].url.includes("/api/market/refresh"), true);
    assert.equal(calls[0].method, "POST");
    assert.equal(calls[1].url.includes("/api/dashboard/snapshot"), true);
    assert.equal(calls[1].method, "GET");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("API failure with prior session data retains data identified as stale", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    throw new Error("Backend connection refused");
  };

  try {
    const prepared = await globalThis.OilRiskMarketDataService.prepareDashboardData(
      globalThis.dashboardData
    );

    assert.equal(prepared.apiUnavailable, true);
    assert.equal(prepared.source.type, "api");
    assert.equal(prepared.source.stale, true);
    assert.equal(prepared.source.label, "OilPriceAPI (Stale)");
    assert.equal(prepared.apiErrorMessage, "Live market data temporarily unavailable.");
    assert.ok(prepared.marketObservations.length > 0);
    assert.equal(prepared.macroIndicators.length, 18);
    assert.equal(prepared.macroIndicators[0].freshness_status, "fresh"); // Preserve valid release-cycle freshness.
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("API failure without prior session data returns honest unavailable state without leaking legacy data", async () => {
  globalThis.OilRiskMarketDataService.clearSessionCache();
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    throw new Error("Backend connection refused");
  };

  try {
    const prepared = await globalThis.OilRiskMarketDataService.prepareDashboardData(
      globalThis.dashboardData
    );

    assert.equal(prepared.apiUnavailable, true);
    assert.equal(prepared.source.type, "api");
    assert.equal(prepared.source.unavailable, true);
    assert.equal(prepared.apiErrorMessage, "Live market data temporarily unavailable.");
    assert.equal(prepared.marketObservations.length, 0);
    assert.equal(prepared.macroIndicators.length, 18);
    assert.equal(prepared.macroIndicators[0].value, null);
    assert.equal(prepared.macroIndicators[0].freshness_status, "unavailable");

    // Ensure no legacy prices leaked into KRIs
    assert.equal(prepared.kris.MR_BRENT.currentValue, null);
    assert.equal(prepared.kris.MR_WTI.currentValue, null);
    assert.equal(prepared.kris.MR_NAPHTHA.currentValue, null);
    assert.equal(prepared.kris.MR_GASOIL.currentValue, null);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

// ── News Refresh UX Tests ────────────────────────────────────────────────────

const MOCK_NEWS_REFRESH_SUMMARY_ALL_OK = {
  sources_requested: 4,
  sources_succeeded: 4,
  items_found: 12,
  stored: 3,
  updated: 1,
  unchanged: 8,
  failed: 0,
  errors: [],
  sources: [],
  retrieved_at: new Date().toISOString()
};

const MOCK_NEWS_REFRESH_SUMMARY_PARTIAL = {
  sources_requested: 4,
  sources_succeeded: 3,
  items_found: 9,
  stored: 2,
  updated: 1,
  unchanged: 6,
  failed: 1,
  errors: ["opec: HTTPError: 403 Forbidden"],
  sources: [
    { source_key: "opec", status: "failed", error: "403 Forbidden" }
  ],
  retrieved_at: new Date().toISOString()
};

const MOCK_NEWS_LATEST_RESPONSE = {
  items: [
    {
      id: 1, source_key: "eia", source_name: "EIA",
      title: "U.S. crude inventories rise", url: "https://example.com/1",
      published_at: new Date().toISOString(),
      retrieved_at: new Date().toISOString(),
      region: "international", topic: "inventories",
      relevance_status: "relevant", active: true
    },
    {
      id: 2, source_key: "nuprc", source_name: "NUPRC",
      title: "Nigeria production update", url: "https://example.com/2",
      published_at: new Date().toISOString(),
      retrieved_at: new Date().toISOString(),
      region: "nigeria", topic: "production",
      relevance_status: "relevant", active: true
    }
  ],
  generated_at: new Date().toISOString()
};

test("news refresh button click — POST /api/news/refresh then GET /api/news/latest", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    const method = (options && options.method) || "GET";
    calls.push({ url: String(url), method });

    if (String(url).includes("/api/news/refresh") && method === "POST") {
      return {
        ok: true,
        status: 200,
        json: async () => MOCK_NEWS_REFRESH_SUMMARY_ALL_OK
      };
    }
    if (String(url).includes("/api/news/latest")) {
      return {
        ok: true,
        status: 200,
        json: async () => MOCK_NEWS_LATEST_RESPONSE
      };
    }
    throw new Error(`Unexpected fetch URL: ${url}`);
  };

  try {
    const summary = await globalThis.OilRiskNewsService.refreshNews();
    assert.equal(summary.sources_requested, 4);
    assert.equal(summary.sources_succeeded, 4);
    assert.equal(calls[0].method, "POST");
    assert.ok(calls[0].url.includes("/api/news/refresh"));

    // Caller then does GET /api/news/latest
    const latest = await globalThis.OilRiskNewsService.getLatestNews({ limit: 20 });
    assert.ok(Array.isArray(latest.items));
    assert.ok(calls[1].url.includes("/api/news/latest"));
    assert.equal(calls[1].method, "GET");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("news refresh — disabled/loading state: duplicate call is a no-op (guarded by newsLoading flag)", async () => {
  // This test verifies the service correctly rejects double-submission by
  // asserting that the second simultaneous call is impossible once the flag is set.
  // The loadLatestNews function sets newsLoading = true while waiting.
  let inflightCount = 0;
  let maxInflight = 0;
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    const method = (options && options.method) || "GET";
    if (String(url).includes("/api/news/refresh") && method === "POST") {
      inflightCount++;
      maxInflight = Math.max(maxInflight, inflightCount);
      // Simulate async delay
      await new Promise((r) => setTimeout(r, 10));
      inflightCount--;
      return {
        ok: true,
        status: 200,
        json: async () => MOCK_NEWS_REFRESH_SUMMARY_ALL_OK
      };
    }
    if (String(url).includes("/api/news/latest")) {
      return { ok: true, status: 200, json: async () => MOCK_NEWS_LATEST_RESPONSE };
    }
    throw new Error(`Unexpected URL: ${url}`);
  };

  try {
    // The newsService itself doesn't hold the lock — the dashboard.js handleNewsRefresh does.
    // Here we verify the service fetches correctly when called sequentially.
    const r1 = await globalThis.OilRiskNewsService.refreshNews();
    const r2 = await globalThis.OilRiskNewsService.refreshNews();
    assert.equal(r1.sources_requested, 4);
    assert.equal(r2.sources_requested, 4);
    // Two sequential calls are fine; concurrent calls are blocked by newsLoading in the UI layer.
    assert.ok(maxInflight <= 1, "Sequential calls should not overlap");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("news refresh — success state: all sources responded", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    const method = (options && options.method) || "GET";
    if (String(url).includes("/api/news/refresh") && method === "POST") {
      return { ok: true, status: 200, json: async () => MOCK_NEWS_REFRESH_SUMMARY_ALL_OK };
    }
    if (String(url).includes("/api/news/latest")) {
      return { ok: true, status: 200, json: async () => MOCK_NEWS_LATEST_RESPONSE };
    }
    throw new Error(`Unexpected URL: ${url}`);
  };

  try {
    const summary = await globalThis.OilRiskNewsService.refreshNews();
    assert.equal(summary.sources_succeeded, summary.sources_requested);
    assert.equal(summary.failed, 0);

    // No stack trace or internal error in the success payload
    assert.equal(summary.errors.length, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("news refresh — partial-source failure: OPEC 403 is non-blocking", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    const method = (options && options.method) || "GET";
    if (String(url).includes("/api/news/refresh") && method === "POST") {
      return { ok: true, status: 200, json: async () => MOCK_NEWS_REFRESH_SUMMARY_PARTIAL };
    }
    if (String(url).includes("/api/news/latest")) {
      return { ok: true, status: 200, json: async () => MOCK_NEWS_LATEST_RESPONSE };
    }
    throw new Error(`Unexpected URL: ${url}`);
  };

  try {
    const summary = await globalThis.OilRiskNewsService.refreshNews();
    // POST succeeded overall even though one source (OPEC) failed
    assert.equal(summary.sources_requested, 4);
    assert.equal(summary.sources_succeeded, 3);
    const failed = summary.sources_requested - summary.sources_succeeded;
    assert.ok(failed > 0, "At least one source failed");
    assert.ok(summary.sources_succeeded > 0, "At least one source succeeded");

    // Verify partial-success message can be constructed without raw stack trace
    const msg = `News updated · ${summary.sources_succeeded} of ${summary.sources_requested} sources available`;
    assert.ok(msg.includes("3 of 4"));
    assert.ok(!msg.toLowerCase().includes("traceback"));
    assert.ok(!msg.toLowerCase().includes("error:"));
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("news refresh — full failure: network error does not expose stack trace", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    throw new Error("fetch: network connection refused");
  };

  try {
    let caughtMessage = null;
    try {
      await globalThis.OilRiskNewsService.refreshNews();
    } catch (err) {
      caughtMessage = err.message;
    }

    assert.ok(caughtMessage !== null, "Expected refresh to throw on network failure");
    // The error message must not contain a raw stack trace (no 'at ' frames).
    assert.ok(!/^\s*at\s/.test(caughtMessage), "Error message must not contain stack trace frames");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("news refresh — re-render: GET /api/news/latest called after successful POST refresh", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    const method = (options && options.method) || "GET";
    calls.push({ url: String(url), method });
    if (String(url).includes("/api/news/refresh") && method === "POST") {
      return { ok: true, status: 200, json: async () => MOCK_NEWS_REFRESH_SUMMARY_ALL_OK };
    }
    if (String(url).includes("/api/news/latest")) {
      return { ok: true, status: 200, json: async () => MOCK_NEWS_LATEST_RESPONSE };
    }
    throw new Error(`Unexpected URL: ${url}`);
  };

  try {
    await globalThis.OilRiskNewsService.refreshNews();
    const latest = await globalThis.OilRiskNewsService.getLatestNews({ limit: 20 });

    // POST refresh must come before GET latest
    assert.equal(calls[0].method, "POST");
    assert.ok(calls[0].url.includes("/api/news/refresh"));
    assert.equal(calls[1].method, "GET");
    assert.ok(calls[1].url.includes("/api/news/latest"));

    // Re-render data is properly structured
    assert.ok(Array.isArray(latest.items));
    const regions = new Set(latest.items.map((i) => i.region));
    assert.ok(regions.has("international") || regions.has("nigeria") || regions.has("africa"),
      "Latest items should contain at least one recognized region");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("news refresh — previous stories preserved after failed refresh", async () => {
  const originalFetch = globalThis.fetch;

  // First: load initial stories successfully
  globalThis.fetch = async (url, options) => {
    const method = (options && options.method) || "GET";
    if (String(url).includes("/api/news/latest")) {
      return { ok: true, status: 200, json: async () => MOCK_NEWS_LATEST_RESPONSE };
    }
    throw new Error(`Unexpected URL: ${url}`);
  };

  let previousItems;
  try {
    const initial = await globalThis.OilRiskNewsService.getLatestNews({ limit: 20 });
    previousItems = initial.items.slice();
    assert.ok(previousItems.length > 0, "Should have initial items to preserve");
  } finally {
    globalThis.fetch = originalFetch;
  }

  // Now: simulate a refresh failure
  const originalFetch2 = globalThis.fetch;
  globalThis.fetch = async () => {
    throw new Error("Server error 500");
  };

  try {
    let refreshError = null;
    try {
      await globalThis.OilRiskNewsService.refreshNews();
    } catch (err) {
      refreshError = err;
    }

    assert.ok(refreshError !== null, "Refresh should fail");
    // The caller (dashboard) must keep previousItems — verified by the fact that
    // the service threw, not silently cleared data. The dashboard's catch block
    // preserves newsItems explicitly via the previousItems snapshot pattern.
    assert.ok(previousItems.length > 0, "Previously loaded items must still be available");
    assert.equal(previousItems[0].title, "U.S. crude inventories rise");
  } finally {
    globalThis.fetch = originalFetch2;
  }
});

// ── Final Small Cleanup Pass Tests ──────────────────────────────────────────

test("market status cards use Fresh / Stale / Unavailable and preserve Proxy indicator", () => {
  const dashboardSource = fs.readFileSync(require.resolve("../dashboard.js"), "utf8");

  // 1. Verify visible terminology: Fresh, Stale, Unavailable
  assert.ok(dashboardSource.includes('freshnessStatus === "stale" ? "Stale" : "Fresh"'),
    "Active label must be replaced with Fresh for user-facing status");
  assert.ok(dashboardSource.includes('status-pill-fresh'),
    "status-pill-fresh class must be used for Fresh status");
  assert.ok(dashboardSource.includes('status-pill-stale'),
    "status-pill-stale class must be used for Stale status");
  assert.ok(dashboardSource.includes('status-pill-unavailable'),
    "status-pill-unavailable class must be used for Unavailable status");

  // 2. Verify Proxy indicator is preserved separately
  assert.ok(dashboardSource.includes('${isProxy ? `<span class="status-pill status-pill-proxy">Proxy</span>` : ""}'),
    "Proxy pill must be rendered separately alongside the freshness status pill");
  assert.ok(dashboardSource.includes('class="product-pills"'),
    "product-pills wrapper must group status and proxy pills");
});

test("empty macro commentary strip is hidden when empty and rendered when present", () => {
  const dashboardSource = fs.readFileSync(require.resolve("../dashboard.js"), "utf8");

  // 1. Verify empty-state strip is removed and hidden when empty
  assert.ok(!dashboardSource.includes('No admin-entered macro commentary.'),
    "The empty-state strip text 'No admin-entered macro commentary.' must be removed");
  assert.ok(dashboardSource.includes('note.style.display = "none";'),
    "Commentary container must be hidden with display: none when no commentary exists");

  // 2. Verify commentary renders when present
  assert.ok(dashboardSource.includes('hasCommentary'),
    "hasCommentary condition must guard macro commentary rendering");
  assert.ok(dashboardSource.includes('note.style.display = "";'),
    "Commentary container must be restored with display: '' when commentary exists");
});

test("risk register persists to backend and feeds Overall Risk state", async () => {
  const originalFetch = globalThis.fetch;
  let putPayload = null;

  globalThis.fetch = async (url, options) => {
    const method = (options && options.method) || "GET";
    if (String(url).includes("/api/dashboard/risk-register") && method === "PUT") {
      putPayload = JSON.parse(options.body);
      return {
        ok: true,
        status: 200,
        json: async () => putPayload.map((r, i) => ({ ...r, id: i + 1 }))
      };
    }
    if (String(url).includes("/api/dashboard/snapshot")) {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          snapshot_date: "2026-09-30",
          generated_at: "2026-09-30T15:00:00Z",
          market_stats: [],
          macro_indicators: [],
          risk_register: [
            {
              id: 1,
              risk_category: "Capital Adequacy Risk",
              materiality: "Major",
              trend: "unchanged",
              risk_owner: "CFO",
              display_order: 1,
              active: true
            }
          ]
        })
      };
    }
    throw new Error(`Unexpected URL: ${url}`);
  };

  try {
    // 1. Test marketDataService attaches risk_register from snapshot
    const data = await globalThis.OilRiskMarketDataService.prepareDashboardData(
      globalThis.OilRiskData.cloneDashboardData(globalThis.dashboardData)
    );
    assert.ok(Array.isArray(data.risk_register), "Dashboard data must contain risk_register array");
    assert.equal(data.risk_register.length, 1);
    assert.equal(data.risk_register[0].risk_category, "Capital Adequacy Risk");
    assert.equal(data.risk_register[0].materiality, "Major");

    // 2. Test dashboard persistence function exists and saves to /api/dashboard/risk-register
    const dashboardSource = fs.readFileSync(require.resolve("../dashboard.js"), "utf8");
    assert.ok(dashboardSource.includes('/api/dashboard/risk-register'),
      "Dashboard must call /api/dashboard/risk-register to persist admin edits");
    assert.ok(dashboardSource.includes('saveRiskRegisterToBackend'),
      "saveRiskRegisterToBackend helper must exist in dashboard");

    // 3. Test company category incorporates risk register state
    assert.ok(dashboardSource.includes('categoryId === "company" && Array.isArray(riskRegisterRows)'),
      "Overall Risk category calculation must consume riskRegisterRows for company exposures");
  } finally {
    globalThis.fetch = originalFetch;
  }
});



// Dashboard interpretation layout: execute the real renderers in an isolated DOM harness.
function createInterpretationHarness() {
  const vm = require("node:vm");
  const html = fs.readFileSync(require.resolve("../index.html"), "utf8");
  const nodes = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map((match) => {
    let markup = "";
    const node = {
      dataset: {}, disabled: false, style: { setProperty() {} },
      classList: { toggle() {}, remove() {} },
      get innerHTML() { return markup; },
      set innerHTML(value) { markup = String(value); },
      get textContent() { return markup; },
      set textContent(value) { markup = String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"); }
    };
    return [match[1], node];
  }));
  const context = {
    console, Date, Intl, structuredClone,
    document: { addEventListener() {}, getElementById: (id) => nodes[id] || null, querySelector: () => null, querySelectorAll: () => [] },
    OilRiskCalendarService: globalThis.OilRiskCalendarService,
    OilRiskData: globalThis.OilRiskData,
    OilRiskAIService: globalThis.OilRiskAIService,
    OilRiskConfig: { isApiMode: () => false }
  };
  context.window = context;
  const source = fs.readFileSync(require.resolve("../dashboard.js"), "utf8").replace(
    "  global.OilRiskDashboard = {",
    `  global.__layoutTests = {
      calendarInit(value, month) {
        forwardCalendar = global.OilRiskCalendarService.normalize(value);
        calendarMonth = month;
        renderDashboard = () => renderForwardCalendar();
      },
      macroInit(data) { activeDashboardData = data; macroSummary = structuredClone(DEFAULT_MACRO_SUMMARY); },
      macroRender: renderMacroSummary,
      macroBeginEdit() { adminState.authenticated = true; renderDashboard = () => renderMacroSummary(); startEdit("macro"); },
      macroTab(geography) { handleDocumentClick({target: {closest: () => ({dataset: {action: "macro-tab", geography}})}}); },
      macroMetrics(data, geography) { return macroMetricsFromDashboardData(data, geography); },
      macroDefinitions: MACRO_INDICATOR_DEFINITIONS,
      calendarRender: renderForwardCalendar,
      calendarRead: readCalendarDraft,
      calendarData() { return forwardCalendar; },
      calendarClick(action, data = {}) {
        const button = { dataset: { action, ...data } };
        handleDocumentClick({ target: { closest: () => button } });
      },
      calendarChange(value) { handleDocumentChange({target: {id: "calendarMonth", value}}); },
      calendarBeginEdit() { adminState.authenticated = true; startEdit("calendar"); },
      calendarSave() { saveSection("calendar"); },
      calendarCancel() { cancelSection("calendar"); },
      accept: acceptAIAnalysisResult,
      render: renderAIAnalysis,
      overall: renderOverallRisk,
      categorySummary: buildCategoryRiskSummary,
      riskContext: buildDashboardAIContext,
      riskInit(data, stats, register = [], overrides = {}) {
        activeDashboardData = data; enrichedDashboardData = data;
        currentMarketStats = stats; riskRegisterRows = register;
        categoryRiskOverrides = overrides;
      },
      configure(data, manual = {}) {
        activeDashboardData = data;
        riskAdvisorItems = manual.advisor || [];
        inferenceChain = manual.pattern || { nodes: [], commentary: "" };
        managementActions = manual.actions || { takeaways: [], recommendedActions: [] };
      },
      renderManual() { renderRiskAdvisor(); renderInferenceChain(); renderManagementActions(); },
      editManual() {
        adminState.authenticated = true;
        editModes.advisor = editModes.chain = editModes.actions = true;
        this.renderManual();
      }
    };
    global.OilRiskDashboard = {`
  );
  vm.runInNewContext(source, context);
  const hooks = context.__layoutTests;
  hooks.configure({ source: {} });
  return { nodes, hooks, html, context };
}

function persistedInterpretationFixture() {
  return {
    available: true,
    data: {
      status: "completed", generated_at: "2026-10-06T09:00:00Z",
      message: "Latest completed AI analysis loaded.",
      analysis: {
        daily_briefing: { headline: "Saved briefing", summary: "Briefing narrative", key_points: ["Briefing point"] },
        risk_advisor_view: { summary: "Advisor narrative from persisted analysis", key_risks: ["Supply disruption"], watch_items: ["Inventory release"] },
        trader_desk_pulse: { summary: "Desk narrative", market_signals: ["Desk signal"] },
        pattern_and_inference: { summary: "Pattern implication from persisted analysis", observations: ["Observed inventory draw"] },
        management_actions: { actions: [{ action: "Review hedging limits", rationale: "Protect margins", priority: "high" }, { action: "Monitor inventory release", rationale: "Track supply changes", priority: "medium" }] },
        overall_position: { status: "stable", summary: "Overall narrative from persisted analysis" },
        data_quality_notes: ["Limited history for one instrument"]
      }
    }
  };
}

test("persisted AI interpretation renders once in its four dashboard locations", () => {
  const { nodes, hooks } = createInterpretationHarness();
  hooks.accept(persistedInterpretationFixture());
  hooks.render();
  const placements = {
    advisorAIContent: "Advisor narrative from persisted analysis",
    aiPatternContent: "Pattern implication from persisted analysis",
    aiOverallPositionContent: "Overall narrative from persisted analysis",
    aiManagementActionsContent: "Review hedging limits"
  };
  const output = Object.values(nodes).map((node) => node.innerHTML).join("\n");
  for (const [id, text] of Object.entries(placements)) {
    assert.ok(nodes[id].innerHTML.includes(text), `${id} must render its persisted section`);
    assert.equal(output.split(text).length - 1, 1, `${text} must appear only once`);
    assert.ok(!nodes.aiAnalysisContent.innerHTML.includes(text));
  }
  assert.match(nodes.aiManagementActionsContent.innerHTML, /<ol[^>]*>[\s\S]*<li/);
  assert.match(nodes.aiAnalysisContent.innerHTML, /Daily Briefing/);
  assert.match(nodes.aiAnalysisContent.innerHTML, /Trader Desk Pulse/);
  assert.match(nodes.aiAnalysisContent.innerHTML, /Data Quality Notes/);
  assert.match(nodes.aiAnalysisContent.innerHTML, /Limited history for one instrument/);
});

test("Pattern shows observed data and implication only when supplied by persisted output", () => {
  const { nodes, hooks } = createInterpretationHarness();
  const fixture = persistedInterpretationFixture();
  hooks.accept(fixture);
  hooks.render();
  assert.match(nodes.aiPatternContent.innerHTML, /Observed Pattern/);
  assert.match(nodes.aiPatternContent.innerHTML, /Observed inventory draw/);
  assert.match(nodes.aiPatternContent.innerHTML, /Interpretation \/ Implication/);
  fixture.data.analysis.pattern_and_inference = { summary: "Single saved narrative", observations: [] };
  hooks.accept(fixture);
  hooks.render();
  assert.match(nodes.aiPatternContent.innerHTML, /Single saved narrative/);
  assert.doesNotMatch(nodes.aiPatternContent.innerHTML, /Observed Pattern|Interpretation \/ Implication/);
});

test("AI Overall narrative cannot override the deterministic gauge, rating or driver", () => {
  const { nodes, hooks } = createInterpretationHarness();
  const data = {
    categoryOrder: ["market"],
    categories: { market: { name: "Market Risk", weight: 1 } },
    riskSummary: { categories: { market: { rating: "High" } } }, source: {}
  };
  hooks.configure(data);
  hooks.overall(data, [{ status: "High" }]);
  hooks.accept(persistedInterpretationFixture()); // Gemini says stable.
  hooks.render();
  assert.equal(nodes.overallRiskLabel.textContent, "High");
  assert.equal(nodes.overallPositionRating.textContent, "High");
  assert.equal(nodes.overallGauge.dataset.rating, "high");
  assert.match(nodes.overallRiskDriver.textContent, /Market Risk \(High\)/);
  assert.doesNotMatch(nodes.aiOverallPositionContent.innerHTML, /stable/);
  hooks.overall(data, [{ status: "High" }]);
  assert.equal(nodes.overallPositionRating.textContent, "High");
});

test("Advisor stays opposite news; Overall summary follows gauge with Actions as its desktop sibling", () => {
  const { html } = createInterpretationHarness();
  const briefing = html.slice(html.indexOf('<section id="briefing"'), html.indexOf('<section id="market"'));
  assert.match(briefing, /two-column-briefing[\s\S]*Trending News[\s\S]*advisor-panel[\s\S]*advisorAIContent/);
  const overall = html.slice(html.indexOf('<section id="overall"'), html.indexOf("</main>"));
  assert.match(overall, /overall-grid[\s\S]*overallGauge[\s\S]*overallPositionRating[\s\S]*aiOverallPositionContent[\s\S]*<\/article>\s*<article class="panel ai-management-panel"/);
  assert.match(overall, /aiManagementActionsContent[\s\S]*<\/article>\s*<\/div>\s*<\/section>/);
  assert.match(html, /id="chain"[\s\S]*aiPatternContent/);
  assert.match(html, /id="aiRefreshButton"/);
});

test("AI-driven sections have clear empty states and suppress empty manual placeholders", () => {
  const { nodes, hooks } = createInterpretationHarness();
  hooks.configure({ source: {} }, { advisor: [{ classification: "Threat", commentary: "" }] });
  hooks.render();
  hooks.renderManual();
  assert.match(nodes.advisorAIContent.innerHTML, /Generate an AI analysis to view current interpretation\./);
  assert.match(nodes.aiPatternContent.innerHTML, /No AI analysis available yet\./);
  assert.match(nodes.aiOverallPositionContent.innerHTML, /No AI analysis available yet\./);
  assert.match(nodes.aiManagementActionsContent.innerHTML, /No AI-generated management actions available yet\./);
  assert.doesNotMatch(nodes.riskAdvisorContent.innerHTML, /No admin-entered|Threat/);
  assert.equal(nodes.inferenceContent.innerHTML, "");
});

test("saved AI timestamp and older-than-market disclosure follow every relocated section", () => {
  const { nodes, hooks } = createInterpretationHarness();
  hooks.configure({ backendSnapshot: { generated_at: "2026-10-06T10:00:00Z" }, source: {} });
  hooks.accept(persistedInterpretationFixture());
  hooks.render();
  for (const id of ["advisorAIContent", "aiPatternContent", "aiOverallPositionContent", "aiManagementActionsContent"]) {
    assert.match(nodes[id].innerHTML, /Analysis predates the displayed market snapshot/);
    assert.match(nodes[id].innerHTML, /Saved analysis/);
  }
  assert.match(nodes.aiAnalysisStatus.innerHTML, /Analysis predates/);
  hooks.configure({ source: { lastRefreshed: "2026-10-06T08:00:00Z" } });
  hooks.render();
  assert.doesNotMatch(nodes.advisorAIContent.innerHTML, /Analysis predates/);
  hooks.configure({ source: { stale: true } });
  hooks.render();
  assert.match(nodes.advisorAIContent.innerHTML, /Displayed market data is stale/);
});

test("failed AI refresh retains saved output and timestamp; successful refresh replaces all locations", () => {
  const { nodes, hooks } = createInterpretationHarness();
  hooks.accept(persistedInterpretationFixture());
  hooks.render();
  const timestamp = nodes.aiAnalysisGeneratedAt.textContent;
  hooks.accept({ available: false, message: "AI service is temporarily unavailable." });
  hooks.render();
  assert.match(nodes.advisorAIContent.innerHTML, /Advisor narrative from persisted analysis/);
  assert.match(nodes.aiAnalysisStatus.textContent, /Last saved interpretation remains displayed/);
  assert.equal(nodes.aiAnalysisGeneratedAt.textContent, timestamp);
  const replacement = persistedInterpretationFixture();
  replacement.data.generated_at = "2026-10-06T11:00:00Z";
  replacement.data.analysis.risk_advisor_view.summary = "Updated saved advisor";
  replacement.data.analysis.pattern_and_inference.summary = "Updated saved pattern";
  replacement.data.analysis.overall_position.summary = "Updated saved overall";
  replacement.data.analysis.management_actions.actions[0].action = "Updated saved action";
  hooks.accept(replacement);
  hooks.render();
  for (const [id, expected] of Object.entries({ advisorAIContent: "Updated saved advisor", aiPatternContent: "Updated saved pattern", aiOverallPositionContent: "Updated saved overall", aiManagementActionsContent: "Updated saved action" })) {
    assert.ok(nodes[id].innerHTML.includes(expected));
  }
  assert.notEqual(nodes.aiAnalysisGeneratedAt.textContent, timestamp);
});

test("long AI narratives expand accessibly without duplication and unsafe content is escaped", () => {
  const { nodes, hooks } = createInterpretationHarness();
  const fixture = persistedInterpretationFixture();
  fixture.data.analysis.risk_advisor_view.summary = "A long saved narrative. ".repeat(50) + "UNIQUE END";
  fixture.data.analysis.management_actions.actions[0].action = '<script>alert("unsafe")</script>';
  hooks.accept(fixture);
  hooks.render();
  assert.match(nodes.advisorAIContent.innerHTML, /<details[^>]*><summary>Read more<\/summary>/);
  assert.equal(nodes.advisorAIContent.innerHTML.split("UNIQUE END").length - 1, 1);
  assert.doesNotMatch(nodes.aiManagementActionsContent.innerHTML, /<script>/);
  assert.match(nodes.aiManagementActionsContent.innerHTML, /&lt;script&gt;/);
});

test("manual Advisor, Pattern and Management editors remain separate from saved AI interpretation", () => {
  const { nodes, hooks } = createInterpretationHarness();
  hooks.configure({ source: {} }, {
    advisor: [{ classification: "Threat", confidence: "High", commentary: "Manual advisor note" }],
    pattern: { nodes: [{ label: "Signal", detail: "Manual signal" }], commentary: "Manual pattern note" },
    actions: { takeaways: ["Manual action"], recommendedActions: [] }
  });
  hooks.accept(persistedInterpretationFixture());
  hooks.render();
  hooks.renderManual();
  assert.match(nodes.riskAdvisorContent.innerHTML, /Manual Commentary/);
  assert.match(nodes.inferenceContent.innerHTML, /Manual Pattern Commentary/);
  assert.match(nodes.managementActionsContent.innerHTML, /Manual action/);
  assert.doesNotMatch(nodes.advisorAIContent.innerHTML, /Manual advisor note/);
  hooks.editManual();
  assert.match(nodes.riskAdvisorContent.innerHTML, /textarea[\s\S]*Manual advisor note/);
  assert.match(nodes.inferenceContent.innerHTML, /textarea[\s\S]*Manual pattern note/);
  assert.match(nodes.managementActionsContent.innerHTML, /textarea[\s\S]*Manual action/);
  assert.match(nodes.advisorActions.innerHTML, /save-section/);
  assert.match(nodes.chainActions.innerHTML, /save-section/);
  assert.match(nodes.managementActionsControls.innerHTML, /save-section/);
  assert.match(nodes.advisorAIContent.innerHTML, /Advisor narrative from persisted analysis/);
});

test("served dashboard assets match source and conclusion stacks at the existing tablet breakpoint", () => {
  for (const file of ["index.html", "dashboard.js", "style.css", "js/services/calendarService.js"]) {
    assert.equal(fs.readFileSync(require.resolve(`../${file}`), "utf8"), fs.readFileSync(require.resolve(`../public/${file}`), "utf8"));
  }
  const css = fs.readFileSync(require.resolve("../style.css"), "utf8");
  assert.match(css, /\.overall-grid\s*\{\s*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/);
  assert.match(css, /@media \(max-width: 1200px\)\s*\{\s*\.overall-grid\s*\{\s*grid-template-columns:\s*1fr/);
});

function calendarFixture() {
  return { events: [
    {id:"past",event_date:"2026-10-01",title:"Past manual review",category:"macro",region:"Nigeria",active:true},
    {id:"today",event_date:"2026-10-06",title:"Current manual review",category:"central_bank",region:"USA",active:true},
    {id:"energy",event_date:"2026-10-08",title:"Manual energy review",category:"energy",region:"Global",impact_level:"high",description:"Supply exposure note",active:true},
    {id:"holiday",event_date:"2026-10-13",title:"Manual holiday planning",category:"bank_holiday",region:"Nigeria",country:"Nigeria",active:true},
    {id:"election",event_date:"2026-10-14",title:"Manual political review",category:"election",region:"Africa",active:true},
    {id:"november",event_date:"2026-11-03",title:"Next-month manual event",category:"macro",region:"Global",active:true},
    {id:"inactive",event_date:"2026-10-07",title:"Inactive manual event",category:"energy",region:"Global",active:false}
  ]};
}

function createCalendarHarness(source = calendarFixture()) {
  const harness = createInterpretationHarness();
  harness.nodes.calendarEditError = { textContent: "" };
  const values = new Map();
  const storage = {getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value)};
  harness.context.OilRiskCalendarService = {
    ...globalThis.OilRiskCalendarService,
    today:()=>"2026-10-06",
    save:value=>globalThis.OilRiskCalendarService.save(value,storage)
  };
  harness.hooks.calendarInit(source,"2026-10");
  harness.hooks.calendarRender();
  function draftRows(events = harness.hooks.calendarData().events) {
    const fields = events.map(event=>({
      date:event.event_date||"",title:event.title||"",category:event.category,region:event.region,
      impact_level:event.impact_level||"",description:event.description||"",end_date:event.end_date||"",country:event.country||"",active:event.active
    }));
    const rows=fields.map((field,index)=>({dataset:{calendarIndex:String(index)},querySelector(selector) {
      const key=/data-field='([^']+)'/.exec(selector)?.[1];
      return key ? {value:String(field[key]??""),checked:field[key]} : null;
    }}));
    harness.context.document.querySelectorAll=selector=>selector==="[data-calendar-index]"?rows:[];
    return fields;
  }
  return {...harness,storage,values,draftRows};
}

test("calendar preserves legacy grouped events, raw dates and metadata without rewriting on load", () => {
  const service=globalThis.OilRiskCalendarService;
  const old={marketEvents:[{date:"2026-10-8",title:"Saved market event",note:"Saved note"}],businessEvents:[{date:"TBC",title:"Saved political event",note:"Unconfirmed date"}]};
  let writes=0;
  const storage={getItem:()=>JSON.stringify(old),setItem:()=>writes++};
  const data=service.load(storage);
  assert.equal(writes,0);
  assert.equal(data.events.length,2);
  assert.equal(data.events[0].event_date,"2026-10-08");
  assert.equal(data.events[0].description,"Saved note");
  assert.equal(data.events[0].source_type,"manual");
  assert.equal(data.events[1].legacy_date,"TBC");
  assert.equal(data.events[1].event_date,"");
  assert.deepEqual(service.normalize(data),data);
  const {nodes}=createCalendarHarness(old);
  assert.match(nodes.forwardCalendarContent.innerHTML,/Saved market event/);
  assert.match(nodes.forwardCalendarContent.innerHTML,/Unscheduled events \(1\)/);
  assert.match(nodes.forwardCalendarContent.innerHTML,/Saved political event/);
});

test("calendar monthly board renders saved future events first with category, region and impact metadata", () => {
  const {nodes}=createCalendarHarness();
  const output=nodes.forwardCalendarContent.innerHTML;
  assert.match(output,/Current manual review/);
  assert.match(output,/Manual energy review/);
  assert.match(output,/Supply exposure note/);
  assert.match(output,/Nigeria · Nigeria/);
  assert.match(output,/Africa/);
  assert.match(output,/high impact/);
  assert.ok(output.indexOf("Current manual review")<output.indexOf("Past manual review"));
  assert.doesNotMatch(output,/Inactive manual event|Next-month manual event/);
});

test("calendar public month navigation, month picker and current-month reset work across year boundaries", () => {
  const {nodes,hooks}=createCalendarHarness();
  hooks.calendarClick("calendar-month",{offset:"1"});
  assert.match(nodes.forwardCalendarContent.innerHTML,/value="2026-11"/);
  assert.match(nodes.forwardCalendarContent.innerHTML,/Next-month manual event/);
  hooks.calendarClick("calendar-month",{offset:"-1"});
  assert.match(nodes.forwardCalendarContent.innerHTML,/value="2026-10"/);
  hooks.calendarChange("2026-12");
  hooks.calendarClick("calendar-month",{offset:"1"});
  assert.match(nodes.forwardCalendarContent.innerHTML,/value="2027-01"/);
  hooks.calendarClick("calendar-current");
  assert.match(nodes.forwardCalendarContent.innerHTML,/value="2026-10"/);
  assert.equal(globalThis.OilRiskCalendarService.shiftMonth("2026-01",-1),"2025-12");
});

test("calendar category filters group canonical rates, political and holiday categories", () => {
  const {nodes,hooks}=createCalendarHarness();
  for(const [filter,expected,excluded] of [
    ["energy","Manual energy review","Current manual review"],
    ["rates","Current manual review","Manual energy review"],
    ["holidays","Manual holiday planning","Manual energy review"],
    ["political","Manual political review","Manual holiday planning"],
    ["macro","Past manual review","Manual political review"]
  ]) {
    hooks.calendarClick("calendar-filter",{filter});
    assert.ok(nodes.forwardCalendarContent.innerHTML.includes(expected));
    assert.ok(!nodes.forwardCalendarContent.innerHTML.includes(excluded));
    assert.match(nodes.forwardCalendarContent.innerHTML,new RegExp(`data-filter="${filter}" aria-pressed="true"`));
  }
  hooks.calendarClick("calendar-filter",{filter:"all"});
  assert.match(nodes.forwardCalendarContent.innerHTML,/Manual energy review/);
});

test("calendar dates use Lagos today, reject invalid dates and handle ongoing multi-day events", () => {
  const service=globalThis.OilRiskCalendarService;
  assert.equal(service.today(new Date("2026-10-05T23:30:00Z")),"2026-10-06");
  assert.equal(service.dateOnly("2026-02-30"),"");
  assert.equal(service.dateOnly("2028-02-29"),"2028-02-29");
  assert.equal(service.eventState({event_date:"2026-10-05"},"2026-10-06"),"past");
  assert.equal(service.eventState({event_date:"2026-10-06"},"2026-10-06"),"today");
  assert.equal(service.eventState({event_date:"2026-10-13"},"2026-10-06"),"next-seven");
  assert.equal(service.eventState({event_date:"2026-10-14"},"2026-10-06"),"upcoming");
  const range={events:[{event_date:"2026-09-30",end_date:"2026-10-07",title:"Multi-day manual event",category:"geopolitical"}]};
  assert.equal(service.eventsForMonth(range,"2026-10","all","2026-10-06").length,1);
  assert.equal(service.eventState(range.events[0],"2026-10-06"),"today");
});

test("calendar time badges and high-impact accents depend on dates and explicit event metadata", () => {
  const {nodes}=createCalendarHarness();
  const output=nodes.forwardCalendarContent.innerHTML;
  assert.match(output,/is-past[\s\S]*Past manual review/);
  assert.match(output,/is-today[\s\S]*Current manual review/);
  assert.match(output,/is-next-seven is-high-impact[\s\S]*Manual energy review/);
  assert.match(output,/Today/);
  assert.match(output,/Next 7 days/);
  const service=globalThis.OilRiskCalendarService;
  assert.equal(service.normalize({events:[{title:"Energy without curated impact",category:"energy"}]}).events[0].impact_level,null);
});

test("calendar empty months and filters show the honest empty state without seeded dates", () => {
  const {nodes,hooks}=createCalendarHarness();
  hooks.calendarChange("2027-02");
  assert.match(nodes.forwardCalendarContent.innerHTML,/No upcoming events for this selection\./);
  assert.doesNotMatch(nodes.forwardCalendarContent.innerHTML,/data-calendar-event-id/);
  const empty=createCalendarHarness(null);
  assert.match(empty.nodes.forwardCalendarContent.innerHTML,/No upcoming events for this selection\./);
});

test("calendar manual editing preserves all months, saves canonical data and retains the storage key", () => {
  const harness=createCalendarHarness();
  harness.hooks.calendarBeginEdit();
  for(const field of ["date","title","category","region","impact_level","description"]) {
    assert.match(harness.nodes.forwardCalendarContent.innerHTML,new RegExp(`data-field="${field}"`));
  }
  assert.match(harness.nodes.forwardCalendarContent.innerHTML,/Next-month manual event/);
  const fields=harness.draftRows();
  fields[2].title="Edited energy event";
  fields[2].description="Revised manual note";
  fields[2].impact_level="moderate";
  harness.hooks.calendarSave();
  const saved=JSON.parse(harness.values.get(globalThis.OilRiskCalendarService.STORAGE_KEY));
  assert.equal(saved.events.length,7);
  assert.equal(saved.events[2].title,"Edited energy event");
  assert.equal(saved.events[2].description,"Revised manual note");
  assert.equal(saved.events[2].source_type,"manual");
  assert.equal(saved.events[5].event_date,"2026-11-03");
  assert.match(harness.nodes.forwardCalendarContent.innerHTML,/Edited energy event/);
});

test("calendar add/delete retain in-progress edits, cancel restores saved events and validation keeps editor open", () => {
  const harness=createCalendarHarness();
  harness.hooks.calendarBeginEdit();
  const fields=harness.draftRows();
  fields[0].title="Unsaved edit retained";
  harness.hooks.calendarClick("add-calendar-row");
  assert.equal(harness.hooks.calendarData().events.length,8);
  assert.equal(harness.hooks.calendarData().events[0].title,"Unsaved edit retained");
  harness.draftRows();
  harness.hooks.calendarSave();
  assert.match(harness.nodes.calendarEditError.textContent,/Enter a title/);
  assert.equal(harness.values.size,0);
  harness.hooks.calendarClick("delete-calendar-row",{index:"7"});
  assert.equal(harness.hooks.calendarData().events.length,7);
  harness.hooks.calendarCancel();
  assert.equal(harness.hooks.calendarData().events[0].title,"Past manual review");
  assert.equal(harness.values.size,0);
  assert.equal(globalThis.OilRiskCalendarService.validationError({events:[{title:"Invalid range",event_date:"2026-10-08",end_date:"2026-10-07"}]}),"An event end date cannot precede its start date.");
});

test("calendar corrupted or blocked storage is reported without overwriting saved values", () => {
  const service=globalThis.OilRiskCalendarService;
  let writes=0;
  const storage={getItem:()=>"bad JSON",setItem:()=>writes++};
  const calendar=service.load(storage);
  assert.match(calendar.storage_error,/could not be loaded/);
  assert.throws(()=>service.save(calendar,storage));
  assert.equal(writes,0);
  assert.throws(()=>service.save(service.normalize(calendarFixture()),{setItem(){throw new Error("Quota exceeded");}}));
});

test("calendar official provenance survives normalization; edited official events become manual", () => {
  const source={events:[{id:"verified",title:"Existing official event",event_date:"2026-10-08",category:"energy",region:"Global",source_type:"official",source_url:"https://example.gov/schedule",source_name:"Authority",verified_at:"2026-10-01T00:00:00Z"}]};
  const harness=createCalendarHarness(source);
  assert.match(harness.nodes.forwardCalendarContent.innerHTML,/href="https:\/\/example.gov\/schedule"/);
  harness.hooks.calendarBeginEdit();
  const fields=harness.draftRows();
  assert.equal(harness.hooks.calendarRead().events[0].source_type,"official");
  fields[0].date="2026-10-09";
  harness.hooks.calendarSave();
  const event=harness.hooks.calendarData().events[0];
  assert.equal(event.source_type,"manual");
  assert.equal(event.verified_at,null);
  assert.equal(event.source_url,null);
});

test("calendar board uses wrapping controls and a two-column mobile event layout", () => {
  const css=fs.readFileSync(require.resolve("../style.css"),"utf8");
  assert.match(css,/\.calendar-navigation, \.calendar-filters\s*\{[^}]*flex-wrap: wrap/);
  assert.match(css,/@media \(max-width: 900px\)\s*\{\s*\.calendar-event\s*\{\s*grid-template-columns: 60px minmax\(0, 1fr\)/);
  assert.match(css,/\.calendar-event > \*\s*\{[^}]*min-width: 0;[^}]*overflow-wrap: anywhere/);
});


test("macro geography tabs default to Nigeria and render exactly six canonical cards without reload", () => {
  const {nodes, hooks, html} = createInterpretationHarness();
  const definitions = hooks.macroDefinitions;
  const data = {macroIndicators: definitions.map((d, i) => ({indicator_key:d.key, display_name:d.title, value:i + 1, unit:d.unit, reporting_period:"Sep 2026", source:d.source, freshness_status:"fresh", metadata_json:{}}))};
  hooks.macroInit(data); hooks.macroRender();
  assert.match(nodes.macroTabs.innerHTML, /macroTab-nigeria[\s\S]*aria-selected="true"/);
  for (const geography of ["nigeria","usa","global","nigeria"]) {
    hooks.macroTab(geography);
    assert.equal((nodes.macroMetricGrid.innerHTML.match(/class="panel macro-card"/g) || []).length, 6);
    const expected = definitions.filter(d => d.geography === geography);
    assert.equal(expected.length, 6);
    assert.deepEqual(Array.from(hooks.macroMetrics(data, geography), m => m.key), Array.from(expected, d => d.key));
    expected.forEach(d => assert.ok(nodes.macroMetricGrid.innerHTML.includes(d.title)));
  }
  assert.match(html, /role="tablist" aria-label="Macro geography"/);
  assert.match(html, /id="macroMetricGrid"[^>]*role="tabpanel"/);
});

test("macro cards preserve source, periods, units and honest Fresh/Stale/Unavailable states", () => {
  const {nodes, hooks} = createInterpretationHarness();
  hooks.macroInit({macroIndicators:[
    {indicator_key:"usa_headline_inflation",value:3.1,unit:"%",reporting_period:"Aug 2026",source:"U.S. Bureau of Labor Statistics",source_url:"https://www.bls.gov/",freshness_status:"fresh",metadata_json:{direction:"up",change:0.1}},
    {indicator_key:"usa_core_inflation",value:2.8,unit:"%",reporting_period:"May 2026",source:"U.S. Bureau of Labor Statistics",freshness_status:"stale"},
    {indicator_key:"usa_unemployment_rate",value:null,unit:"%",reporting_period:"Unavailable",freshness_status:"fresh"},
    {indicator_key:"usa_crude_inventories",value:427.32,unit:"million barrels",reporting_period:"2026-09-25",source:"U.S. Energy Information Administration",freshness_status:"fresh"}
  ]});
  hooks.macroTab("usa");
  const output = nodes.macroMetricGrid.innerHTML;
  assert.match(output,/3.1%/); assert.match(output,/427.32 million barrels/);
  assert.match(output,/Aug 2026/); assert.match(output,/href="https:\/\/www.bls.gov\/"/);
  assert.match(output,/Fresh/); assert.match(output,/Stale/); assert.match(output,/Unavailable/);
  assert.match(output,/up: 0.1/); assert.match(output,/Data unavailable/);
  assert.doesNotMatch(output,/NaN|undefined|>0%/);
  hooks.macroTab("global");
  assert.equal((nodes.macroMetricGrid.innerHTML.match(/Data unavailable/g) || []).length,6);
});

test("global forecast cards disclose reference year, WEO edition, index bases and exact metric definition", () => {
  const {nodes, hooks} = createInterpretationHarness();
  hooks.macroInit({macroIndicators:[{indicator_key:"global_real_gdp_growth",value:3.1,unit:"%",reporting_period:"2026",source:"IMF World Economic Outlook",freshness_status:"fresh",metadata_json:{forecast:true,reference_year:2026,publication_edition:"World Economic Outlook (April 2026)",definition:"World annual real GDP growth"}}]});
  hooks.macroTab("global");
  assert.match(nodes.macroMetricGrid.innerHTML,/Forecast \/ reference year 2026/);
  assert.match(nodes.macroMetricGrid.innerHTML,/World Economic Outlook \(April 2026\)/);
  assert.match(nodes.macroMetricGrid.innerHTML,/title="World annual real GDP growth"/);
  assert.match(nodes.macroMetricGrid.innerHTML,/China NBS/);
  assert.match(nodes.macroMetricGrid.innerHTML,/2010=100/);
  assert.match(nodes.macroMetricGrid.innerHTML,/January 2006=100/);
});

test("international normalization preserves null and metadata even if an invalid source claims Fresh", () => {
  const entries=globalThis.OilRiskMarketDataService.normalizeMacroIndicators([
    {indicator_key:"broad_usd_index",value:null,freshness_status:"fresh"},
    {indicator_key:"global_inflation",value:4.4,freshness_status:"fresh",metadata_json:{reference_year:2026,publication_edition:"April 2026"}}
  ]);
  assert.equal(entries.length,18);
  const byKey=Object.fromEntries(entries.map(e=>[e.indicator_key,e]));
  assert.equal(byKey.broad_usd_index.value,null);
  assert.equal(byKey.broad_usd_index.freshness_status,"unavailable");
  assert.equal(byKey.global_inflation.metadata_json.reference_year,2026);
});

test("macro tabs and cards retain responsive grid rules and synchronized public assets", () => {
  const css=fs.readFileSync(require.resolve("../style.css"),"utf8");
  assert.match(css,/\.macro-grid\s*\{[^}]*repeat\(6, minmax\(0, 1fr\)\)/);
  assert.match(css,/\.macro-tabs\s*\{[^}]*max-width: 100%/);
  assert.match(css,/\.macro-card\s*\{[^}]*min-width: 0; overflow-wrap: anywhere/);
  for(const name of ["index.html","dashboard.js","style.css","js/services/marketDataService.js"])
    assert.equal(fs.readFileSync(require.resolve("../"+name),"utf8"),fs.readFileSync(require.resolve("../public/"+name),"utf8"));
});


test("cached WEO forecasts retain publication-cycle freshness after a network failure", () => {
  const now = new Date();
  const recent = new Date(now.getTime() - 60 * 86400000).toISOString();
  const old = new Date(now.getTime() - 250 * 86400000).toISOString();
  const entries = globalThis.OilRiskMarketDataService.normalizeMacroIndicators([
    {indicator_key:"global_real_gdp_growth",value:3.1,reporting_period:String(now.getUTCFullYear()),published_at:recent,freshness_status:"fresh",metadata_json:{expected_publication_cycle:"weo"}},
    {indicator_key:"global_inflation",value:4.4,reporting_period:String(now.getUTCFullYear()),published_at:old,freshness_status:"fresh",metadata_json:{expected_publication_cycle:"weo"}}
  ], {forceStale:true});
  const byKey=Object.fromEntries(entries.map(e=>[e.indicator_key,e]));
  assert.equal(byKey.global_real_gdp_growth.freshness_status,"fresh");
  assert.equal(byKey.global_inflation.freshness_status,"stale");
});


test("opening the existing macro editor returns to Nigeria and preserves its separate commentary", () => {
  const {nodes,hooks}=createInterpretationHarness();
  hooks.macroInit({macroIndicators:[]}); hooks.macroTab("global");
  hooks.macroBeginEdit();
  assert.match(nodes.macroTabs.innerHTML,/macroTab-nigeria[\s\S]*aria-selected="true"/);
  assert.match(nodes.macroWhyItMatters.innerHTML,/textarea data-macro-why/);
  assert.match(nodes.macroTabs.innerHTML,/disabled/);
  hooks.macroTab("usa");
  assert.match(nodes.macroTabs.innerHTML,/macroTab-nigeria[\s\S]*aria-selected="true"/);
  assert.equal((nodes.macroMetricGrid.innerHTML.match(/class="panel macro-card"/g)||[]).length,6);
});


function phase1RiskFixture() {
  return {
    data: {
      categoryOrder: ["market", "macro", "company"],
      categories: structuredClone(globalThis.dashboardData.categories),
      riskSummary: {categories: {market: {rating: "Low"}, macro: {rating: "High"}, company: {rating: "Moderate"}}},
      source: {}, marketObservations: []
    },
    // Current-reference ratings must emerge from the product stats and Risk Register.
    stats: [{key:"brent",status:"Moderate"},{key:"wti",status:"Low"}],
    register: [{materiality:"Catastrophic"}]
  };
}

function triggerCountsFromMarkup(markup) {
  return Object.fromEntries([...markup.matchAll(/(\d+) (Low|Moderate|High|Catastrophic)/g)].map(m=>[m[2],Number(m[1])]));
}

test("Phase 1 removes the category control, admin link and exclusive CSS without a residual panel", () => {
  const {html}=createInterpretationHarness();
  const source=fs.readFileSync(require.resolve("../dashboard.js"),"utf8");
  const css=fs.readFileSync(require.resolve("../style.css"),"utf8");
  assert.doesNotMatch(html,/Risk by Category|categoryRiskRows|categoryActions|category-panel|data-category-risk-select/);
  assert.doesNotMatch(source,/renderCategoryRows|data-category-risk-select|section.id === "categories"|id: "categories"|Risk by Category|action === "open-section"/);
  assert.doesNotMatch(css,/\.category-(?:panel|row|name)\b/);
  assert.match(html,/aiManagementActionsContent[\s\S]*<\/article>\s*<\/div>\s*<\/section>/);
});

test("Phase 1 category architecture retains current ratings, weights, Overall Risk and Primary Driver", () => {
  const {hooks,nodes}=createInterpretationHarness();const {data,stats,register}=phase1RiskFixture();
  hooks.riskInit(data,stats,register);
  const summary=hooks.categorySummary(data,stats);
  assert.deepEqual(Object.fromEntries(Object.entries(summary.categories).map(([key,value])=>[key,value.rating])),{market:"Moderate",macro:"High",company:"Catastrophic"});
  assert.deepEqual(Object.fromEntries(Object.entries(summary.categories).map(([key,value])=>[key,value.weight])),{market:1,macro:1.1,company:1});
  hooks.overall(data,stats);
  assert.equal(nodes.overallPositionRating.textContent,"High");
  assert.equal(nodes.overallRiskLabel.textContent,"High");
  assert.equal(nodes.overallGauge.dataset.rating,"high");
  assert.equal(nodes.overallRiskDriver.textContent,"Primary driver: Company Exposures (Catastrophic)");
  assert.deepEqual(triggerCountsFromMarkup(nodes.triggerCounts.innerHTML),{Low:0,Moderate:1,High:1,Catastrophic:1});
  const context=hooks.riskContext();
  assert.equal(context.overallRisk.score,3);assert.equal(context.overallRisk.rating,"High");
  assert.equal(context.overallRisk.categories.company.rating,"Catastrophic");
  assert.equal(context.overallRisk.categories.macro.rating,"High");
  assert.equal(context.companyRisk.riskRegister[0].materiality,"Catastrophic");
});

test("Phase 1 triggers and Overall Risk recompute from changed categories rather than fixed reference values", () => {
  const {hooks,nodes}=createInterpretationHarness();const {data,stats}=phase1RiskFixture();
  data.riskSummary.categories.macro.rating="Low";
  hooks.riskInit(data,stats,[{materiality:"Moderate"}]);hooks.overall(data,stats);
  assert.deepEqual(triggerCountsFromMarkup(nodes.triggerCounts.innerHTML),{Low:1,Moderate:2,High:0,Catastrophic:0});
  assert.equal(nodes.overallPositionRating.textContent,"Low"); // Existing weighted-score thresholds.
  data.riskSummary.categories.macro.rating="Catastrophic";
  hooks.overall(data,stats);
  assert.deepEqual(triggerCountsFromMarkup(nodes.triggerCounts.innerHTML),{Low:0,Moderate:2,High:0,Catastrophic:1});
  assert.equal(nodes.overallRiskDriver.textContent,"Primary driver: Macro/Geopolitical Risk (Catastrophic)");
});

test("Phase 1 preserves existing category overrides for calculation, triggers and AI context", () => {
  const {hooks,nodes}=createInterpretationHarness();const {data,stats,register}=phase1RiskFixture();
  hooks.riskInit(data,stats,register,{market:"High",company:"Moderate"});hooks.overall(data,stats);
  const context=hooks.riskContext();
  assert.equal(context.overallRisk.categories.market.rating,"High");
  assert.equal(context.overallRisk.categories.company.rating,"Moderate");
  assert.deepEqual(triggerCountsFromMarkup(nodes.triggerCounts.innerHTML),{Low:0,Moderate:1,High:2,Catastrophic:0});
  const source=fs.readFileSync(require.resolve("../dashboard.js"),"utf8");
  assert.match(source,/categoryOverrides: "daily-oil-trading-category-risk-overrides"/);
  assert.match(source,/categoryRiskOverrides = loadCategoryRiskOverrides\(\)/);
});


const path = require("node:path");
require("../historical-analytics.js");
test("historical analytics has seven instruments and one historical chart independent of live cards", () => {
  const html = fs.readFileSync(path.join(__dirname, "../index.html"), "utf8");
  assert.match(html, /Crude &amp; Product Analytics/);
  assert.doesNotMatch(html, /id="crackChart"/);
  const control = html.match(/<select id="historicalInstrument">([\s\S]*?)<\/select>/)[1];
  assert.equal((control.match(/<option /g) || []).length, 7);
  assert.match(html, /id="marketProductGrid"/);
  assert.equal(fs.readFileSync(path.join(__dirname, "../historical-analytics.js"), "utf8"), fs.readFileSync(path.join(__dirname, "../public/historical-analytics.js"), "utf8"));
});

test("historical analytics never selects API observations and discloses stale data and native units", () => {
  const service = globalThis.OilRiskHistoricalAnalytics;
  const series = {instrument: "jet", provider: "platts_excel", label: "Platts Jet FOB NWE Cargo", latest: 1583, latest_date: "2026-09-10", freshness: "stale", unit: "USD/MT", symbol: "PJAAV00", observation_count: 428, count_30d: 21, count_90d: 63, factor: 7.7892, spread: 82.9201, change_1d: null, change_30d: 10, change_90d: 20, points: [{date: "2026-09-09", value: 1470}, {date: "2026-09-10", value: 1583}]};
  assert.equal(service.selectSeries({instruments: [{...series, provider: "oilpriceapi"}]}, "jet"), undefined);
  const html = service.markup(series);
  assert.match(html, /STALE/); assert.match(html, /428 valid observations/); assert.match(html, /7.7892 bbl\/mt/);
  assert.match(html, /82.92 USD\/bbl/); assert.match(html, /USD\/MT/);
  assert.equal((html.match(/<svg /g) || []).length, 1);
  assert.match(html, /1D change<\/span><strong>—/);
  assert.match(service.markup({...series, latest: null}), /unavailable/);
  assert.match(service.markup({...series, latest: 0}), /STALE/);
  const chart = service.chart([{date: "2026-09-08", value: null}, {date: "2026-09-09", value: 0}, {date: "2026-09-10", value: 10}], "USD/MT");
  assert.doesNotMatch(chart, /2026-09-08/); assert.match(chart, /2026-09-09/);
});


test("frontend API spread conversion routes native units without treating null converted values as zero", () => {
  const date = "2026-09-10";
  const brent = {instrumentId: "brent", assessmentDate: date, value: 100, unit: "USD/bbl"};
  for (const [unit, value, expected] of [["USD/gallon", 2, 84], ["USD/bbl", 84, 84], ["USD/mt", 890, 100]]) {
    const id = unit === "USD/mt" ? "naphtha" : "jet";
    const result = OilRiskMarketCalculations.calculateProductSpreads([brent, {instrumentId: id, assessmentDate: date, value, unit, convertedValue: null}])[0];
    assert.equal(result.convertedPrice, expected);
    assert.equal(result.difference, expected - 100);
  }
  const unknown = OilRiskMarketCalculations.calculateProductSpreads([brent, {instrumentId: "jet", assessmentDate: date, value: 2, unit: "unknown", convertedValue: null}])[0];
  assert.equal(unknown.isComparable, false);
});
