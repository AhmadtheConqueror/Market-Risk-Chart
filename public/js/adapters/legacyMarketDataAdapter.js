// ============================================================
// LEGACY MARKET DATA ADAPTER
// Excel/demo dashboard data -> normalized market observations.
// ============================================================

(function registerLegacyMarketDataAdapter(global) {
  "use strict";

  const LEGACY_SYMBOLS = Object.freeze({
    brent: "PCAAS00",
    naphtha: "PAAAM00",
    gasoil: "AAVJI00",
    gasoline: "PGABM00",
    forcados: "PCABC00",
    wti: "PCACG00",
    jet: "PJAAV00"
  });

  const DASHBOARD_KRI_CODES = Object.freeze({
    brent: "MR_BRENT",
    naphtha: "MR_NAPHTHA",
    gasoil: "MR_GASOIL",
    gasoline: "MR_GASOLINE",
    forcados: "MR_FORCADOS",
    wti: "MR_WTI",
    jet: "MR_JET"
  });

  const REFINED_PRODUCTS = new Set(["naphtha", "gasoil", "gasoline", "jet"]);

  function fromDashboardData(dashboardData) {
    const data = dashboardData || {};
    const source = data.source || {};
    const retrievedAt = validTimestamp(source.lastRefreshed) || new Date().toISOString();
    const provider = source.provider || legacyProviderName(source);
    const sourceType = source.type === "excel" ? "excel" : source.type === "demo" ? "demo" : "legacy";
    const observations = [];

    Object.values(global.OilRiskConfig.MARKET_INSTRUMENTS).forEach((instrument) => {
      if (!instrument.enabled) {
        return;
      }

      const kriCode = DASHBOARD_KRI_CODES[instrument.id];
      const kri = data.kris && data.kris[kriCode] || {};
      const product = data.marketProductPrices && data.marketProductPrices[instrument.id] || {};
      const history = getLegacyHistory(data, instrument.id, kri, product);
      const providerSymbol = product.code || kri.marketDataCode || LEGACY_SYMBOLS[instrument.id] || "";
      const name = product.name || kri.name || instrument.displayName;
      const unit = product.unit || kri.unit || instrument.unit;
      const conversionHistory = Array.isArray(product.conversionHistory) ? product.conversionHistory : [];

      history.forEach((point) => {
        const conversion = REFINED_PRODUCTS.has(instrument.id)
          ? conversionAtDate(conversionHistory, point && point.date)
          : null;
        const observation = global.OilRiskMarketDataModel.normalizeObservation({
          instrumentId: instrument.id,
          providerSymbol,
          name,
          value: point && point.value,
          unit,
          assessmentDate: point && point.date,
          retrievedAt,
          provider,
          sourceType,
          convertedValue: conversion && conversion.convertedValue,
          barrelsPerMT: conversion && conversion.barrelsPerMT
        });

        if (observation) {
          observations.push(observation);
        }
      });
    });

    return global.OilRiskMarketDataModel.normalizeCollection(observations);
  }

  function getLegacyHistory(data, instrumentId, kri, product) {
    if (instrumentId === "brent" && Array.isArray(data.plattsBrentHistory) && data.plattsBrentHistory.length) {
      return data.plattsBrentHistory;
    }

    if (REFINED_PRODUCTS.has(instrumentId) && Array.isArray(product.history) && product.history.length) {
      return product.history;
    }

    return Array.isArray(kri.history) ? kri.history : [];
  }

  function conversionAtDate(history, targetDate) {
    const targetTimestamp = Date.parse(targetDate || "");
    const eligible = (history || [])
      .filter((point) => point && point.date && Date.parse(point.date) <= targetTimestamp)
      .sort((left, right) => Date.parse(left.date) - Date.parse(right.date));

    if (!eligible.length) {
      return null;
    }

    return eligible[eligible.length - 1];
  }

  function legacyProviderName(source) {
    if (source.type === "excel") {
      return "legacy-workbook";
    }

    if (source.type === "demo") {
      return "dashboard-demo";
    }

    return "legacy-dashboard";
  }

  function validTimestamp(value) {
    const timestamp = Date.parse(value || "");
    return Number.isFinite(timestamp) ? new Date(timestamp).toISOString() : "";
  }

  global.OilRiskLegacyMarketDataAdapter = {
    DASHBOARD_KRI_CODES,
    LEGACY_SYMBOLS,
    fromDashboardData
  };
})(typeof window !== "undefined" ? window : globalThis);
