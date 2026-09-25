// ============================================================
// NORMALIZED MARKET DATA MODEL
// Provider payloads must enter this model before calculations run.
// ============================================================

(function registerMarketDataModel(global) {
  "use strict";

  class MarketDataError extends Error {
    constructor(code, message, details) {
      super(message);
      this.name = "MarketDataError";
      this.code = code;
      this.details = details || null;
    }
  }

  function finiteNumber(value) {
    if (value === "" || value === null || value === undefined) {
      return null;
    }

    const numericValue = Number(value);
    return Number.isFinite(numericValue) ? numericValue : null;
  }

  function isoDate(value) {
    if (!value) {
      return "";
    }

    const text = String(value).trim();
    const timestamp = Date.parse(text.length === 10 ? `${text}T00:00:00Z` : text);
    return Number.isFinite(timestamp) ? new Date(timestamp).toISOString().slice(0, 10) : "";
  }

  function isoTimestamp(value) {
    const timestamp = Date.parse(value || "");
    return Number.isFinite(timestamp) ? new Date(timestamp).toISOString() : "";
  }

  function normalizeObservation(rawObservation, defaults) {
    const raw = rawObservation || {};
    const fallback = defaults || {};
    const instrumentId = String(raw.instrumentId || fallback.instrumentId || "").trim().toLowerCase();
    const instrument = global.OilRiskConfig.MARKET_INSTRUMENTS[instrumentId];
    const value = finiteNumber(raw.value);
    const assessmentDate = isoDate(raw.assessmentDate || raw.date || fallback.assessmentDate);

    if (!instrument || !instrument.enabled || value === null || !assessmentDate) {
      return null;
    }

    const normalized = {
      instrumentId,
      providerSymbol: String(raw.providerSymbol || fallback.providerSymbol || instrument.currentProviderSymbol || "").trim(),
      name: String(raw.name || fallback.name || instrument.displayName).trim(),
      value,
      unit: String(raw.unit || fallback.unit || instrument.unit).trim(),
      assessmentDate,
      retrievedAt: isoTimestamp(raw.retrievedAt || fallback.retrievedAt),
      provider: String(raw.provider || fallback.provider || "").trim(),
      sourceType: String(raw.sourceType || fallback.sourceType || "").trim(),
      benchmarkDefinition: String(raw.benchmarkDefinition || fallback.benchmarkDefinition || "").trim()
    };

    const convertedValue = finiteNumber(raw.convertedValue);
    const barrelsPerMT = finiteNumber(raw.barrelsPerMT);

    if (convertedValue !== null) {
      normalized.convertedValue = convertedValue;
    }

    if (barrelsPerMT !== null && barrelsPerMT > 0) {
      normalized.barrelsPerMT = barrelsPerMT;
    }

    return normalized;
  }

  function validateApiObservation(rawObservation) {
    const observation = normalizeObservation(rawObservation);

    if (!observation) {
      throw new MarketDataError(
        "INVALID_API_RESPONSE",
        "The market API returned an invalid or incomplete observation."
      );
    }

    const requiredAuditFields = ["providerSymbol", "retrievedAt", "provider", "sourceType", "unit"];
    const missingFields = requiredAuditFields.filter((field) => !observation[field]);

    if (missingFields.length) {
      throw new MarketDataError(
        "INVALID_API_RESPONSE",
        `The market API observation is missing: ${missingFields.join(", ")}.`,
        { missingFields }
      );
    }

    return observation;
  }

  function normalizeCollection(observations, options) {
    const settings = options || {};
    const normalize = settings.strictApi ? validateApiObservation : normalizeObservation;
    const byKey = new Map();

    (Array.isArray(observations) ? observations : []).forEach((rawObservation) => {
      const observation = normalize(rawObservation);

      if (!observation) {
        return;
      }

      const key = [
        observation.instrumentId,
        observation.assessmentDate,
        observation.providerSymbol
      ].join("|");
      const existing = byKey.get(key);

      if (!existing || Date.parse(observation.retrievedAt || 0) >= Date.parse(existing.retrievedAt || 0)) {
        byKey.set(key, observation);
      }
    });

    return Array.from(byKey.values()).sort(compareObservations);
  }

  function compareObservations(left, right) {
    const instrumentOrder = Object.keys(global.OilRiskConfig.MARKET_INSTRUMENTS);
    const instrumentDelta = instrumentOrder.indexOf(left.instrumentId) - instrumentOrder.indexOf(right.instrumentId);

    if (instrumentDelta !== 0) {
      return instrumentDelta;
    }

    return Date.parse(left.assessmentDate) - Date.parse(right.assessmentDate);
  }

  function groupByInstrument(observations) {
    return normalizeCollection(observations).reduce((groups, observation) => {
      if (!groups[observation.instrumentId]) {
        groups[observation.instrumentId] = [];
      }

      groups[observation.instrumentId].push(observation);
      return groups;
    }, {});
  }

  function buildStatus(observations, overrides) {
    const settings = overrides || {};
    const normalized = normalizeCollection(observations);
    const enabledIds = Object.values(global.OilRiskConfig.MARKET_INSTRUMENTS)
      .filter((instrument) => instrument.enabled)
      .map((instrument) => instrument.id);
    const groups = groupByInstrument(normalized);
    const latestAssessmentDate = normalized.reduce((latest, observation) => (
      !latest || observation.assessmentDate > latest ? observation.assessmentDate : latest
    ), "");
    const lastMarketUpdate = normalized.reduce((latest, observation) => (
      !latest || observation.retrievedAt > latest ? observation.retrievedAt : latest
    ), "");
    const staleAfterHours = Number(global.OilRiskConfig.staleAfterHours || 72);
    const assessmentTimestamp = latestAssessmentDate
      ? Date.parse(`${latestAssessmentDate}T23:59:59Z`)
      : NaN;
    const stale = settings.stale === true || (
      Number.isFinite(assessmentTimestamp) &&
      Date.now() - assessmentTimestamp > staleAfterHours * 60 * 60 * 1000
    );

    return {
      provider: settings.provider || (normalized[0] && normalized[0].provider) || "",
      sourceType: settings.sourceType || (normalized[0] && normalized[0].sourceType) || "",
      lastMarketUpdate,
      latestAssessmentDate,
      freshness: normalized.length ? (stale ? "stale" : "current") : "unavailable",
      stale,
      fallbackUsed: settings.fallbackUsed === true,
      missingInstruments: enabledIds.filter((instrumentId) => !groups[instrumentId] || !groups[instrumentId].length),
      error: settings.error || null
    };
  }

  global.OilRiskMarketDataModel = {
    MarketDataError,
    buildStatus,
    finiteNumber,
    groupByInstrument,
    isoDate,
    normalizeCollection,
    normalizeObservation,
    validateApiObservation
  };
})(typeof window !== "undefined" ? window : globalThis);
