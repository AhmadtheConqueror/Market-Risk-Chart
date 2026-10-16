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
      id: "brent", displayName: "Dated Brent", canonicalName: "Dated Brent",
      providerDisplayName: "Platts Dated Brent", providerSymbol: "PCAAS00",
      currentProviderSymbol: "PCAAS00", provider: "platts_excel",
      benchmarkStatus: "confirmed", unit: "USD/bbl", enabled: true
    }),
    wti: Object.freeze({
      id: "wti", displayName: "WTI Cushing Mo01", canonicalName: "WTI Cushing Mo01",
      providerDisplayName: "Platts WTI Cushing Mo01", providerSymbol: "PCACG00",
      currentProviderSymbol: "PCACG00", provider: "platts_excel",
      benchmarkStatus: "confirmed", unit: "USD/bbl", enabled: true
    }),
    forcados: Object.freeze({
      id: "forcados", displayName: "Forcados FOB Nigeria", canonicalName: "Forcados FOB Nigeria",
      providerDisplayName: "Platts Forcados FOB Nigeria", providerSymbol: "PCABC00",
      currentProviderSymbol: "PCABC00", provider: "platts_excel",
      benchmarkStatus: "confirmed", unit: "USD/bbl", enabled: true
    }),
    naphtha: Object.freeze({
      id: "naphtha", displayName: "Naphtha FOB Rotterdam Barge", canonicalName: "Naphtha FOB Rotterdam Barge",
      providerDisplayName: "Platts Naphtha FOB Rotterdam Barge", providerSymbol: "PAAAM00",
      currentProviderSymbol: "PAAAM00", provider: "platts_excel",
      benchmarkStatus: "confirmed", unit: "USD/mt", enabled: true
    }),
    gasoil: Object.freeze({
      id: "gasoil", displayName: "Gasoil 0.1%S FOB Med Cargo", canonicalName: "Gasoil 0.1%S FOB Med Cargo",
      providerDisplayName: "Platts Gasoil 0.1%S FOB Med Cargo", providerSymbol: "AAVJI00",
      currentProviderSymbol: "AAVJI00", provider: "platts_excel",
      benchmarkStatus: "confirmed", unit: "USD/mt", enabled: true
    }),
    gasoline: Object.freeze({
      id: "gasoline", displayName: "Premium Unleaded 10ppm FOB AR Barge", canonicalName: "Premium Unleaded 10ppm FOB AR Barge",
      providerDisplayName: "Platts Premium Unleaded 10ppm FOB AR Barge", providerSymbol: "PGABM00",
      currentProviderSymbol: "PGABM00", provider: "platts_excel",
      benchmarkStatus: "confirmed", unit: "USD/mt", enabled: true
    }),
    jet: Object.freeze({
      id: "jet", displayName: "Jet FOB NWE Cargo", canonicalName: "Jet FOB NWE Cargo",
      providerDisplayName: "Platts Jet FOB NWE Cargo", providerSymbol: "PJAAV00",
      currentProviderSymbol: "PJAAV00", provider: "platts_excel",
      benchmarkStatus: "confirmed", unit: "USD/mt", enabled: true
    })
  });

  // Approved workbook-specific factors. API conversion defaults remain separate.
  const BBL_PER_MT = Object.freeze({
    PAAAM00: 8.90,
    AAVJI00: 7.3137,
    PGABM00: 8.5286,
    PJAAV00: 7.7892
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

  const CALENDAR_API_ENDPOINTS = Object.freeze({
    events: "/api/calendar/events",
    refresh: "/api/calendar/refresh",
    migrateLegacy: "/api/calendar/migrate-legacy"
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
    CALENDAR_API_ENDPOINTS,
    aiEnabled: runtimeConfig.aiEnabled === true,
    marketHistoryDays: 90,
    staleAfterHours: 72
  });
})(typeof window !== "undefined" ? window : globalThis);
