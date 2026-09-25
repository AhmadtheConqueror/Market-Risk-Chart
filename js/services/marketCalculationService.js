// ============================================================
// MARKET CALCULATION SERVICE
// All price and spread calculations consume normalized observations.
// ============================================================

(function registerMarketCalculationService(global) {
  "use strict";

  const REFINED_PRODUCT_ORDER = ["naphtha", "gasoil", "gasoline", "jet"];

  function observationsForInstrument(observations, instrumentId) {
    return global.OilRiskMarketDataModel.normalizeCollection(observations)
      .filter((observation) => observation.instrumentId === instrumentId);
  }

  function latestObservation(observations, instrumentId) {
    const history = observationsForInstrument(observations, instrumentId);
    return history[history.length - 1] || null;
  }

  function previousValidObservation(observations, instrumentId) {
    const history = observationsForInstrument(observations, instrumentId);
    return history[history.length - 2] || null;
  }

  function calendarWindow(observations, days) {
    const history = (observations || []).slice().sort((left, right) => (
      Date.parse(left.assessmentDate) - Date.parse(right.assessmentDate)
    ));

    if (!history.length || !days) {
      return history;
    }

    const latestDate = Date.parse(`${history[history.length - 1].assessmentDate}T00:00:00Z`);

    if (!Number.isFinite(latestDate)) {
      return history;
    }

    const startDate = latestDate - (days - 1) * 24 * 60 * 60 * 1000;
    return history.filter((observation) => {
      const timestamp = Date.parse(`${observation.assessmentDate}T00:00:00Z`);
      return timestamp >= startDate && timestamp <= latestDate;
    });
  }

  function trendWindow(observations, days) {
    const history = (observations || []).slice().sort((left, right) => (
      Date.parse(left.assessmentDate) - Date.parse(right.assessmentDate)
    ));

    if (!history.length || !days) {
      return history;
    }

    const latestDate = Date.parse(`${history[history.length - 1].assessmentDate}T00:00:00Z`);

    if (!Number.isFinite(latestDate)) {
      return history;
    }

    const startDate = latestDate - days * 24 * 60 * 60 * 1000;
    return history.filter((observation) => {
      const timestamp = Date.parse(`${observation.assessmentDate}T00:00:00Z`);
      return timestamp >= startDate && timestamp <= latestDate;
    });
  }

  function average(values) {
    const validValues = (values || []).filter(Number.isFinite);

    if (!validValues.length) {
      return null;
    }

    return validValues.reduce((sum, value) => sum + value, 0) / validValues.length;
  }

  function sampleStandardDeviation(values, meanValue) {
    const validValues = (values || []).filter(Number.isFinite);

    if (validValues.length < 2 || !Number.isFinite(meanValue)) {
      return null;
    }

    const variance = validValues.reduce((sum, value) => (
      sum + Math.pow(value - meanValue, 2)
    ), 0) / (validValues.length - 1);

    return Math.sqrt(variance);
  }

  function calculateInstrumentStats(observations, instrumentId, windowDays) {
    const history = observationsForInstrument(observations, instrumentId);
    const latest = history[history.length - 1] || null;
    const previous = history[history.length - 2] || null;
    const currentValue = latest ? latest.value : null;
    const previousValue = previous ? previous.value : null;
    const change = currentValue !== null && previousValue !== null
      ? currentValue - previousValue
      : null;
    const percentChange = change !== null && previousValue !== 0
      ? (change / Math.abs(previousValue)) * 100
      : null;
    const statisticalWindow = calendarWindow(history, windowDays || 90);
    const windowValues = statisticalWindow.map((observation) => observation.value);
    const mean90 = average(windowValues);
    const sd90 = sampleStandardDeviation(windowValues, mean90);
    const zScore = currentValue !== null && mean90 !== null && sd90 !== null && sd90 > 0
      ? (currentValue - mean90) / sd90
      : null;

    return {
      history,
      latestObservation: latest,
      previousObservation: previous,
      currentValue,
      previousValue,
      change,
      percentChange,
      mean90,
      sd90,
      zScore,
      windowObservationCount: windowValues.length
    };
  }

  function calculateProductSpreads(observations) {
    const brent = latestObservation(observations, "brent");
    const brentPrice = brent ? brent.value : NaN;

    return REFINED_PRODUCT_ORDER
      .map((instrumentId) => productBrentComparison(observations, instrumentId, brentPrice))
      .filter(Boolean);
  }

  function productBrentComparison(observations, instrumentId, brentPrice) {
    const instrument = global.OilRiskConfig.MARKET_INSTRUMENTS[instrumentId];
    const latest = latestObservation(observations, instrumentId);

    if (!instrument || !latest) {
      return null;
    }

    const configuredFactor = Number(global.OilRiskConfig.PRODUCT_CONVERSIONS[instrumentId]);
    const observationFactor = Number(latest.barrelsPerMT);
    const barrelsPerMT = Number.isFinite(observationFactor) && observationFactor > 0
      ? observationFactor
      : configuredFactor;
    const originalPrice = latest.value;
    const workbookConvertedPrice = Number(latest.convertedValue);
    const convertedPrice = Number.isFinite(workbookConvertedPrice)
      ? workbookConvertedPrice
      : Number.isFinite(originalPrice) && Number.isFinite(barrelsPerMT) && barrelsPerMT > 0
        ? originalPrice / barrelsPerMT
        : NaN;
    const isComparable = Number.isFinite(convertedPrice) && Number.isFinite(brentPrice);

    return {
      instrumentId,
      symbol: latest.providerSymbol,
      label: instrument.displayName,
      name: latest.name || instrument.displayName,
      date: latest.assessmentDate,
      originalPrice,
      originalUnit: latest.unit || instrument.unit,
      barrelsPerMT,
      convertedPrice,
      brentPrice,
      difference: isComparable ? convertedPrice - brentPrice : NaN,
      isComparable
    };
  }

  function toHistoryPoints(observations) {
    return (observations || []).map((observation) => ({
      date: observation.assessmentDate,
      value: observation.value
    }));
  }

  global.OilRiskMarketCalculations = {
    REFINED_PRODUCT_ORDER,
    average,
    calculateInstrumentStats,
    calculateProductSpreads,
    calendarWindow,
    trendWindow,
    latestObservation,
    observationsForInstrument,
    previousValidObservation,
    sampleStandardDeviation,
    toHistoryPoints
  };
})(typeof window !== "undefined" ? window : globalThis);
