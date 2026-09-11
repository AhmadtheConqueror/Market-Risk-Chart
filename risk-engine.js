// ============================================================
// RISK ENGINE
// Thresholds, changes, display values and aggregate ratings.
// ============================================================

(function registerRiskEngine(global) {
  "use strict";

  const RATING_SCORES = {
    Low: 1,
    Moderate: 2,
    High: 3
  };

  const KNOWN_CURRENCY_CODES = new Set([
    "USD",
    "EUR",
    "GBP",
    "NGN",
    "JPY",
    "CNY",
    "CHF",
    "CAD",
    "AUD",
    "SGD",
    "AED",
    "NOK",
    "SEK",
    "DKK",
    "ZAR",
    "INR"
  ]);

  function toNumber(value) {
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }

    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function normalizeRating(status) {
    const normalized = String(status || "").toLowerCase().trim();

    if (normalized === "low") {
      return "Low";
    }

    if (normalized === "medium" || normalized === "moderate") {
      return "Moderate";
    }

    if (normalized === "high" || normalized === "critical") {
      return "High";
    }

    return "";
  }

  function riskScoreForValue(kri, value) {
    const rating = riskRatingForValue(kri, value);
    return RATING_SCORES[rating] || RATING_SCORES.Moderate;
  }

  function riskRatingForValue(kri, value) {
    const numericValue = toNumber(value);
    const fallbackRating = normalizeRating(kri.externalStatus) || "Moderate";

    if (numericValue === null || !kri.riskRule) {
      return fallbackRating;
    }

    const rule = kri.riskRule;

    if (rule.method === "higher-is-risk") {
      if (numericValue >= rule.high) {
        return "High";
      }

      if (numericValue >= rule.moderate) {
        return "Moderate";
      }

      return "Low";
    }

    if (rule.method === "lower-is-risk") {
      if (numericValue <= rule.high) {
        return "High";
      }

      if (numericValue <= rule.moderate) {
        return "Moderate";
      }

      return "Low";
    }

    if (rule.method === "distance-from-target") {
      const distance = Math.abs(numericValue - rule.target);

      if (distance >= rule.highDistance) {
        return "High";
      }

      if (distance >= rule.moderateDistance) {
        return "Moderate";
      }

      return "Low";
    }

    return fallbackRating;
  }

  function formatNumber(value, decimals) {
    const numericValue = toNumber(value);

    if (numericValue === null) {
      return "N/A";
    }

    return numericValue.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  }

  function normalizeCommodityCurrency(currency, fallbackUnit) {
    const currencyText = String(currency || "").trim().toUpperCase();
    const fallbackText = String(fallbackUnit || "").trim().toUpperCase();
    const combinedText = `${currencyText} ${fallbackText}`;

    if (combinedText.includes("USD") || combinedText.includes("$") || combinedText.includes("US DOLLAR")) {
      return "USD";
    }

    const currencyCode = currencyText.match(/\b[A-Z]{3}\b/);

    if (currencyCode && KNOWN_CURRENCY_CODES.has(currencyCode[0])) {
      return currencyCode[0];
    }

    const cleanedCurrency = currencyText.replace(/[^A-Z]/g, "");

    if (["BBL", "BARREL", "MT", "METRIC", "TONNE"].includes(cleanedCurrency)) {
      return "";
    }

    return KNOWN_CURRENCY_CODES.has(cleanedCurrency) ? cleanedCurrency : "";
  }

  function normalizeCommodityUnit(unit) {
    const unitText = String(unit || "").trim().toUpperCase();

    if (unitText.includes("BBL") || unitText.includes("BARREL")) {
      return "bbl";
    }

    if (unitText.includes("MT") || unitText.includes("METRIC") || unitText.includes("TONNE")) {
      return "mt";
    }

    return unitText
      .replace(/USD/g, "")
      .replace(/\$/g, "")
      .replace(/[^A-Z0-9]+/g, "")
      .toLowerCase();
  }

  function formatCommodityValue(value, currency, unit) {
    const numericValue = Number(value);

    if (!Number.isFinite(numericValue)) {
      return "N/A";
    }

    const formatted = numericValue.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
    const normalizedCurrency = normalizeCommodityCurrency(currency, unit) || "USD";
    const displayUnit = normalizeCommodityUnit(unit);
    const currencySymbol = normalizedCurrency === "USD" ? "$" : `${normalizedCurrency} `;

    return displayUnit
      ? `${currencySymbol}${formatted}/${displayUnit}`
      : `${currencySymbol}${formatted}`;
  }

  function formatValue(kri, value) {
    const numericValue = toNumber(value);

    if (numericValue === null) {
      return "N/A";
    }

    const decimals = Number.isFinite(kri.decimals) ? kri.decimals : 1;

    if (kri.commodityValueFormat) {
      return formatCommodityValue(
        numericValue,
        kri.commodityCurrency,
        kri.commodityUnit || kri.unit
      );
    }

    if (kri.format === "currency" || kri.format === "currency0") {
      return "$" + formatNumber(numericValue, decimals);
    }

    if (kri.format === "percent") {
      return formatNumber(numericValue, decimals) + "%";
    }

    return formatNumber(numericValue, decimals);
  }

  function formatChangeValue(kri, value) {
    const decimals = kri.format === "currency0" ? 0 : Number(kri.decimals || 0);
    const absoluteValue = Math.abs(value);

    if (kri.commodityValueFormat) {
      return formatCommodityValue(
        absoluteValue,
        kri.commodityCurrency,
        kri.commodityUnit || kri.unit
      );
    }

    if (kri.format === "currency" || kri.format === "currency0") {
      return "$" + formatNumber(absoluteValue, decimals);
    }

    if (kri.format === "percent") {
      return formatNumber(absoluteValue, 1) + " pt" + (absoluteValue === 1 ? "" : "s");
    }

    return formatNumber(absoluteValue, decimals);
  }

  function formatDelta(kri, currentValue, previousValue) {
    if (currentValue === null || previousValue === null) {
      return "N/A";
    }

    const change = currentValue - previousValue;
    const sign = change > 0 ? "+" : change < 0 ? "-" : "";
    const denominator = Math.abs(previousValue);
    const changeText = sign + formatChangeValue(kri, change);

    if (denominator === 0) {
      return changeText;
    }

    const percentChange = Math.abs((change / denominator) * 100);
    return `${changeText} (${sign}${percentChange.toFixed(1)}%)`;
  }

  function distanceFromTarget(rule, value) {
    if (!rule || rule.method !== "distance-from-target") {
      return 0;
    }

    return Math.abs(value - rule.target);
  }

  function changeTone(kri, currentValue, previousValue) {
    if (currentValue === null || previousValue === null || currentValue === previousValue) {
      return "neutral";
    }

    const previousScore = riskScoreForValue(kri, previousValue);
    const currentScore = riskScoreForValue(kri, currentValue);

    if (currentScore > previousScore) {
      return "negative";
    }

    if (currentScore < previousScore) {
      return "positive";
    }

    if (!kri.riskRule) {
      return currentValue > previousValue ? "positive" : "negative";
    }

    if (kri.riskRule.method === "higher-is-risk") {
      return currentValue > previousValue ? "negative" : "positive";
    }

    if (kri.riskRule.method === "lower-is-risk") {
      return currentValue < previousValue ? "negative" : "positive";
    }

    if (kri.riskRule.method === "distance-from-target") {
      const previousDistance = distanceFromTarget(kri.riskRule, previousValue);
      const currentDistance = distanceFromTarget(kri.riskRule, currentValue);
      return currentDistance > previousDistance ? "negative" : "positive";
    }

    return "neutral";
  }

  function computeKriMetrics(kri) {
    const currentValue = toNumber(kri.currentValue);
    const previousValue = toNumber(kri.previousValue);
    const rating = riskRatingForValue(kri, currentValue);
    const score = RATING_SCORES[rating] || RATING_SCORES.Moderate;
    const change = currentValue === null || previousValue === null
      ? null
      : currentValue - previousValue;
    const percentChange = change === null || previousValue === 0
      ? null
      : (change / Math.abs(previousValue)) * 100;

    return {
      rating,
      score,
      currentValue,
      previousValue,
      change,
      percentChange,
      valueText: formatValue(kri, currentValue),
      deltaText: formatDelta(kri, currentValue, previousValue),
      tone: changeTone(kri, currentValue, previousValue),
      previousRating: riskRatingForValue(kri, previousValue)
    };
  }

  function ratingFromScore(score) {
    if (score >= 2.34) {
      return "High";
    }

    if (score >= 1.67) {
      return "Moderate";
    }

    return "Low";
  }

  function weightedAverage(items, getScore, getWeight) {
    let weightedScore = 0;
    let totalWeight = 0;

    items.forEach((item) => {
      const score = getScore(item);
      const weight = getWeight(item);

      if (!Number.isFinite(score) || !Number.isFinite(weight) || weight <= 0) {
        return;
      }

      weightedScore += score * weight;
      totalWeight += weight;
    });

    return totalWeight > 0 ? weightedScore / totalWeight : RATING_SCORES.Moderate;
  }

  function computeCategorySummary(data, categoryId) {
    const category = data.categories[categoryId];
    const kris = category.kriCodes
      .map((code) => data.kris[code])
      .filter(Boolean);

    const score = weightedAverage(
      kris,
      (kri) => kri.metrics.score,
      (kri) => Number(kri.riskWeight || 1)
    );

    return {
      id: category.id,
      name: category.name,
      score,
      rating: ratingFromScore(score),
      dotClass: category.dotClass
    };
  }

  function gaugeAngle(score) {
    const clampedScore = Math.max(1, Math.min(3, score));
    return -80 + ((clampedScore - 1) / 2) * 160;
  }

  function gaugeRatingFromScore(score) {
    if (score >= 2.5) {
      return "Catastrophic";
    }

    if (score >= 2) {
      return "High";
    }

    if (score >= 1.5) {
      return "Moderate";
    }

    return "Low";
  }

  function enrichDashboardData(rawData) {
    const data = global.OilRiskData.cloneDashboardData(rawData);

    Object.values(data.kris).forEach((kri) => {
      kri.metrics = computeKriMetrics(kri);
    });

    const categorySummaries = {};

    data.categoryOrder.forEach((categoryId) => {
      categorySummaries[categoryId] = computeCategorySummary(data, categoryId);
    });

    const categoryItems = data.categoryOrder.map((categoryId) => ({
      score: categorySummaries[categoryId].score,
      weight: Number(data.categories[categoryId].weight || 1)
    }));

    const overallScore = weightedAverage(
      categoryItems,
      (item) => item.score,
      (item) => item.weight
    );

    data.riskSummary = {
      categories: categorySummaries,
      overall: {
        score: overallScore,
        rating: gaugeRatingFromScore(overallScore),
        gaugeAngle: gaugeAngle(overallScore)
      }
    };

    return data;
  }

  global.OilRiskEngine = {
    enrichDashboardData,
    formatCommodityValue,
    formatValue,
    formatDelta,
    ratingFromScore,
    riskRatingForValue,
    riskScoreForValue
  };
})(typeof window !== "undefined" ? window : globalThis);
