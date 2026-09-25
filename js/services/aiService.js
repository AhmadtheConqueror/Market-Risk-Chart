// ============================================================
// AI SERVICE
// Gemini is an interpretation layer, not the source of truth for
// market prices or calculated risk metrics. The browser calls only
// our backend; credentials and provider calls remain server-side.
// ============================================================

(function registerAIService(global) {
  "use strict";

  const AI_ANALYSIS_CONTRACT = Object.freeze({
    daily_briefing: {},
    risk_advisor_view: {},
    trader_desk_pulse: {},
    pattern_and_inference: {},
    management_actions: { actions: [] },
    overall_position: {},
    data_quality_notes: []
  });

  function buildDashboardAIContext(source) {
    const contextSource = source || {};
    const data = contextSource.dashboardData || contextSource.data || {};
    const observations = Array.isArray(data.marketObservations) ? data.marketObservations : [];
    const suppliedStats = Array.isArray(contextSource.marketStats) ? contextSource.marketStats : [];
    const market = Object.values(global.OilRiskConfig.MARKET_INSTRUMENTS)
      .filter((instrument) => instrument.enabled)
      .map((instrument) => {
        const calculated = global.OilRiskMarketCalculations.calculateInstrumentStats(
          observations,
          instrument.id,
          90
        );
        const supplied = suppliedStats.find((item) => item.key === instrument.id) || {};
        const latest = calculated.latestObservation;

        return {
          instrumentId: instrument.id,
          name: instrument.displayName,
          providerSymbol: latest ? latest.providerSymbol : "",
          unit: latest ? latest.unit : instrument.unit,
          assessmentDate: latest ? latest.assessmentDate : "",
          retrievedAt: latest ? latest.retrievedAt : "",
          provider: latest ? latest.provider : "",
          sourceType: latest ? latest.sourceType : "",
          latestPrice: calculated.currentValue,
          previousPrice: calculated.previousValue,
          oneDayChange: calculated.change,
          oneDayPercentageChange: calculated.percentChange,
          mean90: calculated.mean90,
          standardDeviation90: calculated.sd90,
          zScore: calculated.zScore,
          observationCount90: calculated.windowObservationCount,
          riskLabel: supplied.status || "",
          trend30: global.OilRiskMarketCalculations.toHistoryPoints(
            global.OilRiskMarketCalculations.calendarWindow(calculated.history, 30)
          )
        };
      });
    const outliers = market
      .filter((item) => Number.isFinite(item.zScore))
      .sort((left, right) => Math.abs(right.zScore) - Math.abs(left.zScore))
      .map((item) => ({
        instrumentId: item.instrumentId,
        name: item.name,
        zScore: item.zScore,
        riskLabel: item.riskLabel,
        observationCount90: item.observationCount90
      }));

    return {
      generatedAt: new Date().toISOString(),
      marketDataStatus: data.marketDataStatus || null,
      market,
      outliers,
      productSpreads: global.OilRiskMarketCalculations.calculateProductSpreads(observations),
      macro: clone(contextSource.macro || {}),
      geopolitical: clone(contextSource.geopolitical || {}),
      companyRisk: clone(contextSource.companyRisk || {}),
      overallRisk: clone(contextSource.overallRisk || {}),
      briefing: clone(contextSource.briefing || []),
      riskAdvisor: clone(contextSource.riskAdvisor || {}),
      traderDesk: clone(contextSource.traderDesk || {}),
      managementActions: clone(contextSource.managementActions || {})
    };
  }

  async function generateDashboardAnalysis(context) {
    if (!global.OilRiskConfig.aiEnabled) {
      return notConfigured();
    }

    const options = context && typeof context === "object" ? context : {};
    return postToBackend(global.OilRiskConfig.AI_API_ENDPOINTS.analyse, {
      force_refresh: options.forceRefresh === true
    });
  }

  async function getLatestDashboardAnalysis() {
    if (!global.OilRiskConfig.aiEnabled) {
      return notConfigured();
    }

    return getFromBackend(global.OilRiskConfig.AI_API_ENDPOINTS.latest);
  }

  async function sendChatMessage(message, context) {
    if (!global.OilRiskConfig.aiEnabled) {
      return notConfigured();
    }

    const cleanMessage = String(message || "").trim();

    if (!cleanMessage) {
      return {
        configured: true,
        available: false,
        code: "INVALID_REQUEST",
        message: "Enter a message before sending."
      };
    }

    return postToBackend(global.OilRiskConfig.AI_API_ENDPOINTS.chat, {
      message: cleanMessage,
      context: context || buildDashboardAIContext({})
    });
  }

  async function postToBackend(url, body) {
    try {
      const response = await global.fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });

      if (response.status === 429) {
        return unavailable("RATE_LIMITED", "AI analysis is temporarily rate limited.");
      }

      if (!response.ok) {
        return unavailable("AI_UNAVAILABLE", `AI service returned HTTP ${response.status}.`);
      }

      return {
        configured: true,
        available: true,
        data: await response.json()
      };
    } catch (error) {
      return unavailable("AI_UNAVAILABLE", "AI service is temporarily unavailable.");
    }
  }

  async function getFromBackend(url) {
    try {
      const response = await global.fetch(url, {
        method: "GET",
        credentials: "same-origin",
        headers: { Accept: "application/json" }
      });

      if (!response.ok) {
        return unavailable("AI_UNAVAILABLE", `AI service returned HTTP ${response.status}.`);
      }

      return {
        configured: true,
        available: true,
        data: await response.json()
      };
    } catch (error) {
      return unavailable("AI_UNAVAILABLE", "AI service is temporarily unavailable.");
    }
  }

  function notConfigured() {
    return {
      configured: false,
      available: false,
      message: "AI service is not yet configured."
    };
  }

  function unavailable(code, message) {
    return {
      configured: true,
      available: false,
      code,
      message
    };
  }

  function clone(value) {
    if (value === undefined) {
      return null;
    }

    if (typeof structuredClone === "function") {
      return structuredClone(value);
    }

    return JSON.parse(JSON.stringify(value));
  }

  global.buildDashboardAIContext = buildDashboardAIContext;
  global.OilRiskAIService = {
    AI_ANALYSIS_CONTRACT,
    buildDashboardAIContext,
    generateDashboardAnalysis,
    getLatestDashboardAnalysis,
    sendChatMessage
  };
})(typeof window !== "undefined" ? window : globalThis);
