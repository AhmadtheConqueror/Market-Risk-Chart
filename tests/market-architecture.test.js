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

    assert.equal(prepared.macroIndicators.length, 6);
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

  assert.equal(normalized.length, 6);
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
    assert.equal(prepared.macroIndicators.length, 6);
    assert.equal(prepared.macroIndicators[0].freshness_status, "stale");
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
    assert.equal(prepared.macroIndicators.length, 6);
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
