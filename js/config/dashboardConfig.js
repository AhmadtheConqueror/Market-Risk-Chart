// ============================================================
// DASHBOARD RUNTIME CONFIGURATION
// Public configuration only. Never place API credentials here.
// ============================================================

(function registerDashboardConfig(global) {
  "use strict";

  const runtimeConfig = global.OIL_RISK_RUNTIME_CONFIG || {};
  const DATA_SOURCE_MODE = "api";

  const MARKET_INSTRUMENTS = Object.freeze({
    brent: Object.freeze({
      id: "brent",
      displayName: "Dated Brent",
      canonicalName: "Dated Brent",
      providerDisplayName: "ICE Brent Crude Futures",
      providerSymbol: "BRENT_CRUDE_USD",
      currentProviderSymbol: "BRENT_CRUDE_USD",
      provider: "oilpriceapi",
      benchmarkStatus: "confirmed",
      unit: "USD/bbl",
      enabled: true
    }),
    wti: Object.freeze({
      id: "wti",
      displayName: "WTI Cushing",
      canonicalName: "WTI Cushing",
      providerDisplayName: "WTI Crude Oil Futures",
      providerSymbol: "WTI_USD",
      currentProviderSymbol: "WTI_USD",
      provider: "oilpriceapi",
      benchmarkStatus: "confirmed",
      unit: "USD/bbl",
      enabled: true
    }),
    forcados: Object.freeze({
      id: "forcados",
      displayName: "Forcados",
      canonicalName: "Forcados",
      providerDisplayName: "Forcados Blend",
      providerSymbol: null,
      currentProviderSymbol: null,
      provider: null,
      benchmarkStatus: "unavailable",
      unavailableReason: "No approved automated source configured",
      unit: "USD/bbl",
      enabled: true
    }),
    naphtha: Object.freeze({
      id: "naphtha",
      displayName: "Naphtha",
      canonicalName: "Naphtha",
      providerDisplayName: "Naphtha",
      providerSymbol: "NAPHTHA_USD",
      currentProviderSymbol: "NAPHTHA_USD",
      provider: "oilpriceapi",
      benchmarkStatus: "test_proxy",
      unit: "USD/mt",
      enabled: true
    }),
    gasoil: Object.freeze({
      id: "gasoil",
      displayName: "Gasoil",
      canonicalName: "Gasoil",
      providerDisplayName: "ICE Low Sulphur Gasoil Rotterdam",
      providerSymbol: "GASOIL_USD",
      currentProviderSymbol: "GASOIL_USD",
      provider: "oilpriceapi",
      benchmarkStatus: "test_proxy",
      unit: "USD/mt",
      enabled: true
    }),
    gasoline: Object.freeze({
      id: "gasoline",
      displayName: "Gasoline",
      canonicalName: "Gasoline",
      providerDisplayName: "Premium Motor Gasoline 10ppm",
      providerSymbol: null,
      currentProviderSymbol: null,
      provider: null,
      benchmarkStatus: "unavailable",
      unavailableReason: "No approved automated source configured",
      unit: "USD/mt",
      enabled: true
    }),
    jet: Object.freeze({
      id: "jet",
      displayName: "Jet",
      canonicalName: "Jet",
      providerDisplayName: "Aviation Jet Fuel CIF NWE Cargoes",
      providerSymbol: null,
      currentProviderSymbol: null,
      provider: null,
      benchmarkStatus: "unavailable",
      unavailableReason: "No approved automated source configured",
      unit: "USD/mt",
      enabled: true
    })
  });

  // Retained for compatibility with the approved legacy Platts mappings.
  const BBL_PER_MT = Object.freeze({
    PAAAM00: 8.90,
    AAVJI00: 7.44,
    PGABM00: 8.33,
    PJAAV00: 7.70
  });

  // Calculation code uses instrument IDs, not provider-specific symbols.
  const PRODUCT_CONVERSIONS = Object.freeze({
    naphtha: 8.90,
    gasoil: 7.44,
    gasoline: 8.33,
    jet: 7.70
  });

  const MARKET_API_ENDPOINTS = Object.freeze({
    snapshot: "/api/dashboard/snapshot",
    latest: "/api/market/latest",
    history: "/api/market/history",
    refresh: "/api/market/refresh",
    importExcel: "/api/market/import-excel"
  });

  const AI_API_ENDPOINTS = Object.freeze({
    analyse: "/api/ai/analyse",
    latest: "/api/ai/latest",
    chat: "/api/ai/chat"
  });

  const NEWS_API_ENDPOINTS = Object.freeze({
    latest: "/api/news/latest",
    refresh: "/api/news/refresh"
  });

  global.OilRiskConfig = Object.freeze({
    DATA_SOURCE_MODE,
    dataSourceMode: runtimeConfig.dataSourceMode || DATA_SOURCE_MODE,
    isApiMode: () => (runtimeConfig.dataSourceMode || DATA_SOURCE_MODE) === "api",
    isLegacyMode: () => (runtimeConfig.dataSourceMode || DATA_SOURCE_MODE) === "legacy",
    MARKET_INSTRUMENTS,
    PRODUCT_CONVERSIONS,
    BBL_PER_MT,
    MARKET_API_ENDPOINTS,
    AI_API_ENDPOINTS,
    NEWS_API_ENDPOINTS,
    aiEnabled: runtimeConfig.aiEnabled === true,
    marketHistoryDays: 90,
    staleAfterHours: 72
  });
})(typeof window !== "undefined" ? window : globalThis);
