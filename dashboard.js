// ============================================================
// PORTABLE DASHBOARD RENDERER
// Browser-only admin mode, Excel upload and local editable content.
// ============================================================

(function registerPortableOilRiskDashboard(global) {
  "use strict";

  const PRODUCT_ORDER = [
    { key: "brent", kriCode: "MR_BRENT", name: "Dated Brent" },
    { key: "naphtha", kriCode: "MR_NAPHTHA", name: "Naphtha" },
    { key: "gasoil", kriCode: "MR_GASOIL", name: "Gasoil" },
    { key: "gasoline", kriCode: "MR_GASOLINE", name: "Gasoline" },
    { key: "forcados", kriCode: "MR_FORCADOS", name: "Forcados" },
    { key: "wti", kriCode: "MR_WTI", name: "WTI Cushing" },
    { key: "jet", kriCode: "MR_JET", name: "Jet" }
  ];
  const Z_SCORE_RISK_CONFIG = {
    normalMaxAbsZ: 1,
    watchMaxAbsZ: 2,
    outlierMaxAbsZ: 3,
    labels: {
      normal: "Low",
      watch: "Moderate",
      outlier: "High",
      extreme: "Catastrophic"
    }
  };
  const RISK_SCALE = ["Low", "Moderate", "High", "Catastrophic"];
  const RISK_SCORES = {
    Low: 1,
    Moderate: 2,
    High: 3,
    Catastrophic: 4
  };
  const MATERIALITY_OPTIONS = ["Low", "Moderate", "Major", "Catastrophic"];
  const MOVEMENT_OPTIONS = [
    { value: "increased", label: "Increasing", symbol: "\u2191" },
    { value: "unchanged", label: "Unchanged", symbol: "\u2194" },
    { value: "reduced", label: "Decreasing", symbol: "\u2193" }
  ];
  const STORAGE_KEYS = {
    riskRegister: "daily-oil-trading-risk-register",
    macroSummary: "daily-oil-trading-macro-summary",
    briefing: "daily-oil-trading-trending-news",
    managementActions: "daily-oil-trading-management-actions",
    riskAdvisor: "daily-oil-trading-risk-advisor",
    traderDesk: "daily-oil-trading-trader-desk",
    inference: "daily-oil-trading-inference-chain",
    geopolitical: "daily-oil-trading-geopolitical-cards",
    forwardCalendar: "daily-oil-trading-forward-calendar",
    categoryOverrides: "daily-oil-trading-category-risk-overrides"
  };
  const SECTION_TARGETS = {
    briefing: "#briefing",
    advisor: "#briefing",
    desk: "#desk",
    macro: "#macro",
    chain: "#chain",
    geo: "#geo",
    register: "#company",
    actions: "#company",
    calendar: "#calendar",
    categories: "#overall"
  };
  const EDITABLE_SECTIONS = [
    { id: "briefing", label: "Trending News & Market Watch", detail: "Verified regional energy headlines" },
    { id: "advisor", label: "Risk Advisor", detail: "Threat, opportunity and watch commentary" },
    { id: "desk", label: "Trader Desk Pulse", detail: "Counterparty colour and session watch" },
    { id: "macro", label: "Macro Drivers", detail: "Macro values and why-it-matters note" },
    { id: "chain", label: "Pattern & Inference", detail: "Manual indicator-to-implication chain" },
    { id: "geo", label: "Geopolitical Risk", detail: "Jurisdiction ratings and implications" },
    { id: "register", label: "Risk Register", detail: "Rows, materiality, trend and owners" },
    { id: "actions", label: "Management Actions", detail: "Takeaways and recommended actions" },
    { id: "calendar", label: "Forward Calendar", detail: "Market/economic and business/political events" },
    { id: "categories", label: "Risk by Category", detail: "Overall-risk category selectors" }
  ];

  // Local-only gate for a portable static file. This is not secure server authentication.
  const ADMIN_USERNAME = "riskadmin";
  const ADMIN_PASSWORD = "Password123";

  const DEFAULT_RISK_REGISTER_ROWS = [
    {
      riskCategory: "Capital Adequacy Risk",
      materiality: "Major",
      movement: "unchanged",
      riskOwner: "CFO"
    },
    {
      riskCategory: "Legal and Contract Management Risk",
      materiality: "Moderate",
      movement: "unchanged",
      riskOwner: "General Counsel"
    },
    {
      riskCategory: "Counterparty Default Risk",
      materiality: "Major",
      movement: "increased",
      riskOwner: "Chief Risk Officer"
    },
    {
      riskCategory: "Project Selection and Planning Risk",
      materiality: "Moderate",
      movement: "unchanged",
      riskOwner: "COO"
    },
    {
      riskCategory: "Market Opportunity Risk",
      materiality: "Moderate",
      movement: "reduced",
      riskOwner: "Commercial Director"
    }
  ];
  const MACRO_INDICATOR_DEFINITIONS = [
    {
      key: "headline_inflation",
      title: "Headline Inflation",
      unit: "%",
      source: "National Bureau of Statistics Nigeria"
    },
    {
      key: "food_inflation",
      title: "Food Inflation",
      unit: "%",
      source: "National Bureau of Statistics Nigeria"
    },
    {
      key: "core_inflation",
      title: "Core Inflation",
      unit: "%",
      source: "National Bureau of Statistics Nigeria"
    },
    {
      key: "real_gdp_growth",
      title: "Real GDP Growth",
      unit: "%",
      source: "National Bureau of Statistics Nigeria"
    },
    {
      key: "nigeria_pmi",
      title: "PMI",
      unit: "index",
      source: "Stanbic IBTC Bank / S&P Global"
    },
    {
      key: "crude_oil_production",
      title: "Crude Oil Production",
      unit: "mbpd",
      source: "Nigerian Upstream Petroleum Regulatory Commission",
      note: "Crude only, excluding condensate"
    }
  ];
  const DEFAULT_MACRO_SUMMARY = {
    metrics: MACRO_INDICATOR_DEFINITIONS.map((indicator) => ({
      key: indicator.key,
      title: indicator.title,
      period: "Unavailable",
      value: "Data unavailable",
      source: indicator.source,
      freshnessStatus: "unavailable",
      note: indicator.note || ""
    })),
    whyItMatters: ""
  };
  const DEFAULT_BRIEFING = [
    {
      id: "international",
      title: "International",
      sections: [
        {
          id: "international-oil-gas",
          title: "Oil & Gas",
          items: [
            {
              id: "international-oil-gas-1",
              headline: "OPEC+ supply discipline remains a key market driver as traders balance gradual production increases against resilient crude demand and ongoing geopolitical risk."
            }
          ]
        },
        {
          id: "international-supply-demand",
          title: "Supply / Demand",
          items: [
            {
              id: "international-supply-demand-1",
              headline: "Refinery maintenance schedules and shifting product inventories continue to shape near-term crude balances and regional price spreads."
            }
          ]
        }
      ]
    },
    {
      id: "africa",
      title: "Africa",
      sections: [
        {
          id: "africa-refining",
          title: "Refining",
          items: [
            {
              id: "africa-refining-1",
              headline: "African refiners are adjusting crude runs and product procurement as local demand, import economics and freight costs diverge across regional markets."
            }
          ]
        },
        {
          id: "africa-fx-macro",
          title: "FX / Macro",
          items: [
            {
              id: "africa-fx-macro-1",
              headline: "Currency liquidity and inflation pressures remain important watchpoints for regional fuel pricing, working capital and trade settlement."
            }
          ]
        }
      ]
    },
    {
      id: "nigeria",
      title: "Nigeria",
      sections: [
        {
          id: "nigeria-oil-gas",
          title: "Oil & Gas",
          items: [
            {
              id: "nigeria-oil-gas-1",
              headline: "The 700,000 bpd Dangote refinery utilization rate dropped to 71% in July after operating near full capacity for three consecutive months, amid weaker domestic fuel demand, higher local prices and a renewed increase in imports."
            },
            {
              id: "nigeria-oil-gas-2",
              headline: "Domestic crude supply, terminal availability and export programme changes remain key variables for Nigerian production and physical market participants."
            }
          ]
        }
      ]
    }
  ];
  const DEFAULT_RISK_ADVISOR = [
    { classification: "Threat", confidence: "Unassigned", commentary: "" },
    { classification: "Opportunity", confidence: "Unassigned", commentary: "" },
    { classification: "Watch", confidence: "Unassigned", commentary: "" }
  ];
  const DEFAULT_TRADER_DESK = [
    { title: "Counterparty Colour", body: "" },
    { title: "Risk Strategy", body: "" },
    { title: "What to Watch This Session", body: "" }
  ];
  const DEFAULT_INFERENCE_CHAIN = {
    nodes: [
      { label: "Indicator", detail: "" },
      { label: "Intermediate effect", detail: "" },
      { label: "Operational/business effect", detail: "" },
      { label: "Oil/trading implication", detail: "" }
    ],
    commentary: ""
  };
  const DEFAULT_GEOPOLITICAL_CARDS = [
    { jurisdiction: "Nigeria", rating: "Moderate", currentDevelopment: "", implication: "" },
    { jurisdiction: "Africa", rating: "Moderate", currentDevelopment: "", implication: "" },
    { jurisdiction: "Middle East / Global Supply Routes", rating: "Moderate", currentDevelopment: "", implication: "" },
    { jurisdiction: "International", rating: "Moderate", currentDevelopment: "", implication: "" }
  ];
  const DEFAULT_FORWARD_CALENDAR = {
    marketEvents: [],
    businessEvents: []
  };

  let activeDashboardData = null;
  let enrichedDashboardData = null;
  let currentMarketStats = [];
  let lastUploadedFile = null;
  let adminState = {
    authenticated: false
  };
  let riskRegisterRows = [];
  let macroSummary = null;
  let briefingItems = [];
  let newsItems = [];
  let newsLoaded = false;
  let newsLoading = false;
  let selectedWorkbookFile = null;
  let riskAdvisorItems = [];
  let traderDeskItems = [];
  let inferenceChain = null;
  let geopoliticalCards = [];
  let forwardCalendar = null;
  let managementActions = null;
  let categoryRiskOverrides = {};
  let latestAIAnalysis = null;
  let aiAnalysisEnvelope = null;
  let openCategoryRiskId = "";
  const editModes = {
    briefing: false,
    advisor: false,
    desk: false,
    macro: false,
    chain: false,
    geo: false,
    register: false,
    actions: false,
    calendar: false
  };
  const editSnapshots = {};

  document.addEventListener("DOMContentLoaded", () => {
    initialiseDashboard().catch(() => {
      setDataMessage("Unable to prepare market data. Legacy dashboard data remains available.", true);
    });
  });

  async function initialiseDashboard() {
    try {
      activeDashboardData = await global.OilRiskMarketDataService.prepareDashboardData(
        global.OilRiskData.cloneDashboardData(global.dashboardData)
      );
    } catch (_) {
      if (global.OilRiskConfig && typeof global.OilRiskConfig.isApiMode === "function" && global.OilRiskConfig.isApiMode()) {
        activeDashboardData = {
          ...global.dashboardData,
          apiUnavailable: true,
          apiErrorMessage: "Live market data temporarily unavailable.",
          marketObservations: [],
          source: { type: "api", label: "OilPriceAPI (Unavailable)", unavailable: true }
        };
      } else {
        activeDashboardData = global.OilRiskMarketDataService.prepareLegacyDashboardData(
          global.OilRiskData.cloneDashboardData(global.dashboardData)
        );
      }
    }
    riskRegisterRows = loadRiskRegisterRows();
    macroSummary = loadMacroSummary(activeDashboardData);
    briefingItems = loadBriefingItems();
    riskAdvisorItems = loadRiskAdvisorItems();
    traderDeskItems = loadTraderDeskItems();
    inferenceChain = loadInferenceChain();
    geopoliticalCards = loadGeopoliticalCards();
    forwardCalendar = loadForwardCalendar();
    managementActions = loadManagementActions(activeDashboardData);
    categoryRiskOverrides = loadCategoryRiskOverrides();

    if (apiModeEnabled()) {
      await loadLatestNews();
    }

    bindControls();
    renderDashboard(activeDashboardData);
    updateAdminUi();
    loadLatestAIAnalysis();
  }

  function bindControls() {
    const excelInput = document.getElementById("excelUpload");
    const loadExcelButton = document.getElementById("loadExcelButton");
    const adminButton = document.getElementById("adminModeButton");
    const adminLoginSubmit = document.getElementById("adminLoginSubmit");
    const adminLoginClose = document.getElementById("adminLoginClose");
    const adminPanelClose = document.getElementById("adminPanelClose");
    const adminLogoutButton = document.getElementById("adminLogoutButton");
    const marketRefreshButton = document.getElementById("marketRefreshButton");
    const aiRefreshButton = document.getElementById("aiRefreshButton");

    if (excelInput) {
      excelInput.addEventListener("change", handleExcelUpload);
    }

    if (loadExcelButton) {
      loadExcelButton.addEventListener("click", () => {
        if (!isAdmin()) {
          return;
        }

        excelInput.click();
      });
    }

    if (marketRefreshButton) {
      marketRefreshButton.addEventListener("click", handleMarketRefresh);
    }

    if (aiRefreshButton) {
      aiRefreshButton.addEventListener("click", handleAIRefresh);
    }

    if (adminButton) {
      adminButton.addEventListener("click", () => {
        if (isAdmin()) {
          openAdminPanel();
        } else {
          openModal("adminLoginModal");
        }
      });
    }

    if (adminLoginSubmit) {
      adminLoginSubmit.addEventListener("click", handleAdminLogin);
    }

    ["adminUsername", "adminPassword"].forEach((id) => {
      const input = document.getElementById(id);

      if (input) {
        input.addEventListener("keydown", (event) => {
          if (event.key === "Enter") {
            handleAdminLogin();
          }
        });
      }
    });

    if (adminLoginClose) {
      adminLoginClose.addEventListener("click", () => closeModal("adminLoginModal"));
    }

    if (adminPanelClose) {
      adminPanelClose.addEventListener("click", () => closeModal("adminPanelModal"));
    }

    if (adminLogoutButton) {
      adminLogoutButton.addEventListener("click", handleAdminLogout);
    }

    document.addEventListener("click", handleDocumentClick);
    document.addEventListener("change", handleDocumentChange);
  }

  async function handleMarketRefresh() {
    const btn = document.getElementById("marketRefreshButton");
    const label = document.getElementById("marketRefreshLabel") || btn;
    if (!btn) {
      return;
    }

    const originalText = label.textContent;
    btn.disabled = true;
    label.textContent = "Refreshing…";

    try {
      const result = await global.OilRiskMarketDataService.refreshMarketData();
      if (result && result.configured) {
        activeDashboardData = await global.OilRiskMarketDataService.prepareDashboardData(
          global.OilRiskData.cloneDashboardData(activeDashboardData)
        );
        renderDashboard(activeDashboardData);
        label.textContent = "Refreshed ✓";
        setTimeout(() => {
          label.textContent = originalText;
          btn.disabled = false;
        }, 2000);
      } else {
        label.textContent = "Refresh unavailable";
        setTimeout(() => {
          label.textContent = originalText;
          btn.disabled = false;
        }, 2500);
      }
    } catch (_) {
      label.textContent = "Refresh failed";
      setTimeout(() => {
        label.textContent = originalText;
        btn.disabled = false;
      }, 2500);
    }
  }

  function handleDocumentClick(event) {
    const button = event.target.closest("[data-action]");

    if (!button) {
      return;
    }

    const action = button.dataset.action;
    const section = button.dataset.section || "";

    if (action === "open-section") {
      closeModal("adminPanelModal");
      scrollToSection(button.dataset.target || SECTION_TARGETS[section]);
      return;
    }

    if (!isAdmin()) {
      return;
    }

    if (action === "edit-section") {
      startEdit(section);
      return;
    }

    if (action === "save-section") {
      saveSection(section);
      return;
    }

    if (action === "cancel-section") {
      cancelSection(section);
      return;
    }

    if (action === "refresh-news") {
      handleNewsRefresh();
      return;
    }

    handleEditAction(action, button);
  }

  function handleDocumentChange(event) {
    const select = event.target.closest("[data-category-risk-select]");

    if (!select || !isAdmin()) {
      return;
    }

    const categoryId = select.dataset.categoryRiskSelect;
    const rating = normalizeRiskRating(select.value);

    if (!categoryId || !rating) {
      return;
    }

    categoryRiskOverrides[categoryId] = rating;
    saveJson(STORAGE_KEYS.categoryOverrides, categoryRiskOverrides);
    renderDashboard(activeDashboardData);
  }

  function handleEditAction(action, button) {
    if (action === "add-risk-row") {
      riskRegisterRows = readRiskRegisterDraft();
      riskRegisterRows.push({
        riskCategory: "",
        materiality: "Moderate",
        movement: "unchanged",
        riskOwner: ""
      });
      renderDashboard(activeDashboardData);
      return;
    }

    if (action === "delete-risk-row") {
      riskRegisterRows = readRiskRegisterDraft();
      riskRegisterRows.splice(Number(button.dataset.index), 1);
      renderDashboard(activeDashboardData);
      return;
    }

    if (action === "add-briefing-region") {
      briefingItems = readBriefingDraft();
      briefingItems.push({
        id: uniqueId("region"),
        title: "New Region",
        sections: []
      });
      renderDashboard(activeDashboardData);
      return;
    }

    if (action === "delete-briefing-region") {
      briefingItems = readBriefingDraft();
      briefingItems.splice(Number(button.dataset.region), 1);
      renderDashboard(activeDashboardData);
      return;
    }

    if (action === "add-briefing-section") {
      briefingItems = readBriefingDraft();
      const region = briefingItems[Number(button.dataset.region)];

      if (region) {
        region.sections.push({
          id: uniqueId("section"),
          title: "Market",
          items: []
        });
      }

      renderDashboard(activeDashboardData);
      return;
    }

    if (action === "delete-briefing-section") {
      briefingItems = readBriefingDraft();
      const region = briefingItems[Number(button.dataset.region)];

      if (region) {
        region.sections.splice(Number(button.dataset.sectionIndex), 1);
      }

      renderDashboard(activeDashboardData);
      return;
    }

    if (action === "add-briefing-item") {
      briefingItems = readBriefingDraft();
      const region = briefingItems[Number(button.dataset.region)];
      const section = region && region.sections[Number(button.dataset.sectionIndex)];

      if (section) {
        section.items.push({
          id: uniqueId("item"),
          headline: ""
        });
      }

      renderDashboard(activeDashboardData);
      return;
    }

    if (action === "delete-briefing-item") {
      briefingItems = readBriefingDraft();
      const region = briefingItems[Number(button.dataset.region)];
      const section = region && region.sections[Number(button.dataset.sectionIndex)];

      if (section) {
        section.items.splice(Number(button.dataset.item), 1);
      }

      renderDashboard(activeDashboardData);
      return;
    }

    if (action === "add-calendar-row") {
      forwardCalendar = readCalendarDraft();
      const group = button.dataset.group === "businessEvents" ? "businessEvents" : "marketEvents";
      forwardCalendar[group].push({ date: "", title: "", note: "" });
      renderDashboard(activeDashboardData);
      return;
    }

    if (action === "delete-calendar-row") {
      forwardCalendar = readCalendarDraft();
      const group = button.dataset.group === "businessEvents" ? "businessEvents" : "marketEvents";
      forwardCalendar[group].splice(Number(button.dataset.index), 1);
      renderDashboard(activeDashboardData);
      return;
    }

    if (action === "add-management-item") {
      managementActions = readManagementDraft();
      const list = button.dataset.list === "recommendedActions" ? "recommendedActions" : "takeaways";
      managementActions[list].push("");
      renderDashboard(activeDashboardData);
      return;
    }

    if (action === "delete-management-item") {
      managementActions = readManagementDraft();
      const list = button.dataset.list === "recommendedActions" ? "recommendedActions" : "takeaways";
      managementActions[list].splice(Number(button.dataset.index), 1);
      renderDashboard(activeDashboardData);
    }
  }

  function isAdmin() {
    return Boolean(adminState.authenticated);
  }

  function apiModeEnabled() {
    return Boolean(global.OilRiskConfig && typeof global.OilRiskConfig.isApiMode === "function" && global.OilRiskConfig.isApiMode());
  }

  async function loadLatestNews() {
    newsLoading = true;
    try {
      const response = await global.OilRiskNewsService.getLatestNews({ limit: 20 });
      newsItems = response && Array.isArray(response.items) ? response.items : [];
    } catch (_) {
      newsItems = [];
    } finally {
      newsLoaded = true;
      newsLoading = false;
    }
  }

  async function handleNewsRefresh() {
    if (!isAdmin() || newsLoading) {
      return;
    }

    newsLoading = true;
    renderDashboard(activeDashboardData);
    try {
      const summary = await global.OilRiskNewsService.refreshNews();
      await loadLatestNews();
      setDataMessage(`News refreshed: ${summary.stored || 0} new, ${summary.updated || 0} updated, ${summary.failed || 0} failed source/item checks.`);
      renderDashboard(activeDashboardData);
    } catch (error) {
      newsLoading = false;
      setDataMessage(error.message || "Unable to refresh verified news.", true);
      renderDashboard(activeDashboardData);
    }
  }

  function handleAdminLogin() {
    const username = document.getElementById("adminUsername");
    const password = document.getElementById("adminPassword");
    const message = document.getElementById("adminLoginMessage");
    const usernameValue = username ? username.value.trim() : "";
    const passwordValue = password ? password.value : "";

    if (message) {
      message.textContent = "";
    }

    if (usernameValue === ADMIN_USERNAME && passwordValue === ADMIN_PASSWORD) {
      adminState.authenticated = true;

      if (password) {
        password.value = "";
      }

      closeModal("adminLoginModal");
      renderDashboard(activeDashboardData);
      openAdminPanel();
      return;
    }

    if (message) {
      message.textContent = "Invalid username or password.";
    }
  }

  function handleAdminLogout() {
    adminState.authenticated = false;
    Object.keys(editModes).forEach((key) => {
      editModes[key] = false;
      delete editSnapshots[key];
    });
    closeModal("adminPanelModal");
    renderDashboard(activeDashboardData);
  }

  function openAdminPanel() {
    renderAdminPanel();
    openModal("adminPanelModal");
  }

  function openModal(id) {
    const modal = document.getElementById(id);

    if (modal) {
      modal.hidden = false;
    }
  }

  function closeModal(id) {
    const modal = document.getElementById(id);

    if (modal) {
      modal.hidden = true;
    }
  }

  async function handleExcelUpload(event) {
    const file = event.target.files && event.target.files[0];

    if (!file || !isAdmin()) {
      return;
    }

    selectedWorkbookFile = file;
    await uploadWorkbook(file, event.target);
  }

  async function uploadWorkbook(file, input) {
    const uploadUi = global.OilRiskExcelImportUi;

    if (!file || !isAdmin() || !uploadUi) {
      return;
    }

    setExcelUploadState(uploadUi.loadingState(file.name, 0));
    setDataMessage(`Uploading workbook: ${file.name}`);

    try {
      const summary = await global.OilRiskMarketDataService.importExcelWorkbook(file);
      setExcelUploadState(uploadUi.loadingState(file.name, 2));
      activeDashboardData = await global.OilRiskMarketDataService.prepareDashboardData(
        global.OilRiskData.cloneDashboardData(activeDashboardData)
      );
      lastUploadedFile = {
        name: file.name,
        uploadedAt: summary.uploaded_at || new Date().toISOString(),
        rowsRead: summary.rows_read,
        rowsValid: summary.rows_valid,
        recordsLoaded: summary.rows_valid,
        rowsStored: summary.rows_stored,
        rowsUpdated: summary.rows_updated,
        rowsRejected: summary.rows_rejected,
        instrumentsAffected: summary.instruments_affected || [],
        dateRange: summary.date_range || null
      };
      renderDashboard(activeDashboardData);
      renderAdminPanel();
      setExcelUploadState(uploadUi.successState(file.name, summary));
      setDataMessage(`Workbook imported successfully: ${file.name}`);
    } catch (error) {
      const failure = uploadUi.failureState(file.name, error);
      setExcelUploadState(failure);
      setDataMessage(`Workbook import failed: ${failure.message}`, true);
    } finally {
      if (input) {
        input.value = "";
      }
    }
  }

  function setExcelUploadState(state) {
    const panel = document.getElementById("excelUploadStatus");
    const button = document.getElementById("loadExcelButton");
    const input = document.getElementById("excelUpload");

    if (button) {
      button.disabled = Boolean(state && state.buttonDisabled);
      button.textContent = state && state.status === "loading" ? "Uploading..." : "Load / Refresh Excel";
    }
    if (input) {
      input.disabled = Boolean(state && state.buttonDisabled);
    }

    if (!panel || !state) {
      return;
    }

    panel.hidden = false;
    panel.className = `excel-upload-status is-${state.status}`;

    if (state.status === "loading") {
      panel.innerHTML = `
        <div class="excel-upload-status-title"><span class="loading-spinner" aria-hidden="true"></span>Processing workbook</div>
        <div class="excel-upload-file">${escapeHtml(state.fileName)}</div>
        <ul class="excel-upload-stages">
          ${state.stages.map((stage, index) => `<li class="${index === state.activeStage ? "is-active" : index < state.activeStage ? "is-complete" : ""}">${escapeHtml(stage)}</li>`).join("")}
        </ul>
      `;
      return;
    }

    if (state.status === "success") {
      const summary = state.summary || {};
      const instruments = summary.instruments.length
        ? summary.instruments.map((instrument) => titleCase(instrument)).join(", ")
        : "--";
      const dateRange = summary.dateFrom && summary.dateTo
        ? `${formatDate(summary.dateFrom)} &ndash; ${formatDate(summary.dateTo)}`
        : "--";
      panel.innerHTML = `
        <div class="excel-upload-status-title">Workbook imported successfully</div>
        <div class="excel-upload-file">${escapeHtml(state.fileName)}</div>
        <dl class="excel-upload-summary">
          <div><dt>Rows read</dt><dd>${summary.rowsRead}</dd></div>
          <div><dt>Valid observations</dt><dd>${summary.rowsValid}</dd></div>
          <div><dt>Stored</dt><dd>${summary.rowsStored}</dd></div>
          <div><dt>Updated</dt><dd>${summary.rowsUpdated}</dd></div>
          <div><dt>Rejected</dt><dd>${summary.rowsRejected}</dd></div>
          <div><dt>Instruments affected</dt><dd>${escapeHtml(instruments)}</dd></div>
          <div><dt>Date range</dt><dd>${dateRange}</dd></div>
        </dl>
      `;
      return;
    }

    panel.innerHTML = `
      <div class="excel-upload-status-title">Workbook import failed</div>
      <div class="excel-upload-file">${escapeHtml(state.fileName)}</div>
      <p class="excel-upload-error">${escapeHtml(state.message)}</p>
      <button class="admin-action-button secondary" type="button" data-action="retry-excel-upload">Try Again</button>
    `;
    const retryButton = panel.querySelector("[data-action='retry-excel-upload']");
    if (retryButton) {
      retryButton.addEventListener("click", () => {
        const input = document.getElementById("excelUpload");
        uploadWorkbook(selectedWorkbookFile, input);
      });
    }
  }

  function renderDashboard(rawData) {
    const nextData = global.OilRiskData.cloneDashboardData(rawData || activeDashboardData);
    const isApi = (nextData.source && nextData.source.type === "api") ||
      (global.OilRiskConfig && typeof global.OilRiskConfig.isApiMode === "function" && global.OilRiskConfig.isApiMode());

    if (isApi) {
      activeDashboardData = nextData;
    } else {
      activeDashboardData = Array.isArray(nextData.marketObservations) && nextData.marketObservations.length
        ? nextData
        : global.OilRiskMarketDataService.prepareLegacyDashboardData(nextData);
    }
    enrichedDashboardData = global.OilRiskEngine.enrichDashboardData(activeDashboardData);
    currentMarketStats = buildMarketProductStats(enrichedDashboardData);
    if (!editModes.macro) {
      macroSummary = mergeMacroSummaryWithApi(macroSummary, activeDashboardData);
    }

    renderMetadata(enrichedDashboardData);
    renderMarketProductCards(currentMarketStats);
    renderOutlierScan(currentMarketStats);
    renderBriefing();
    renderAIAnalysis();
    renderRiskAdvisor();
    renderTraderDesk();
    renderMacroSummary();
    renderInferenceChain();
    renderGeopoliticalRisk(enrichedDashboardData);
    renderRiskRegister();
    renderForwardCalendar();
    renderManagementActions();
    renderOverallRisk(enrichedDashboardData, currentMarketStats);

    global.OilRiskCharts.renderAll(enrichedDashboardData);
    updateAdminUi();
  }

  function renderMetadata(data) {
    const source = data.source || {};
    const isApi = source.type === "api" || (global.OilRiskConfig && typeof global.OilRiskConfig.isApiMode === "function" && global.OilRiskConfig.isApiMode());
    const sourceLabel = isApi
      ? (source.stale ? `${source.label || "Market data"} (Stale)` : (source.unavailable ? `${source.label || "Market data"} (Unavailable)` : (source.label || "OilPriceAPI")))
      : (source.label || titleCase(source.type || "Demo"));
    const refreshed = source.refreshedAtFormatted || formatDateTime(source.lastRefreshed) || (lastUploadedFile && lastUploadedFile.uploadedAt) || "--";

    setText("dataSourceLabel", sourceLabel);
    setText("lastRefreshed", refreshed);
    setText("dashboardDate", formatDate(new Date()));
    setText("marketRefreshText", `Last market refresh: ${refreshed}`);

    const banner = document.getElementById("apiUnavailableBanner");
    if (banner) {
      const hasUsableMarketData = (Array.isArray(data.marketObservations) && data.marketObservations.some((observation) => (
        observation && Number.isFinite(Number(observation.value))
      ))) || (data.backendMarketStats && Object.values(data.backendMarketStats).some((stat) => (
        stat && Number.isFinite(Number(stat.current_value))
      )));

      const shouldShowWarning = data.apiUnavailable === true && !hasUsableMarketData;

      if (shouldShowWarning) {
        banner.hidden = false;
        const msg = document.getElementById("apiUnavailableMessage");
        if (msg) {
          msg.textContent = data.apiErrorMessage || "Live market data temporarily unavailable.";
        }
      } else {
        banner.hidden = true;
      }
    }
  }

  function renderTriggerStrip(categories) {
    const counts = RISK_SCALE.reduce((result, rating) => {
      result[rating] = 0;
      return result;
    }, {});

    const validCategories = Object.values(categories || {}).filter((category) => (
      category && Object.prototype.hasOwnProperty.call(counts, category.rating)
    ));

    if (!validCategories.length) {
      const container = document.getElementById("triggerCounts");
      if (container) {
        container.innerHTML = `<span class="trigger-chip trigger-empty">&mdash;</span>`;
      }
      return;
    }

    validCategories.forEach((category) => {
      counts[category.rating] += 1;
    });

    const container = document.getElementById("triggerCounts");

    if (!container) {
      return;
    }

    container.innerHTML = RISK_SCALE.map((rating) => `
      <span class="trigger-chip status-${rating.toLowerCase()}">
        <span class="dot ${rating.toLowerCase()}"></span>
        ${counts[rating] || 0} ${escapeHtml(rating)}
      </span>
    `).join("");
  }

  function renderMarketProductCards(stats) {
    const container = document.getElementById("marketProductGrid");
    const note = document.getElementById("marketWindowNote");

    if (!container) {
      return;
    }

    const maxObservationCount = Math.max(...stats.map((stat) => stat.windowObservationCount), 0);

    if (note) {
      const isApi = global.OilRiskConfig && typeof global.OilRiskConfig.isApiMode === "function" && global.OilRiskConfig.isApiMode();
      note.textContent = isApi
        ? `90 calendar-day window (${maxObservationCount} observations accumulated)`
        : `90 calendar-day window, valid observations only (${maxObservationCount || 0} max)`;
    }

    container.innerHTML = stats.map((stat) => {
      if (stat.isUnavailable) {
        return `
          <article class="product-card is-unavailable status-unavailable" data-instrument="${escapeHtml(stat.key)}">
            <div class="product-top">
              <div>
                <h3 class="product-name">${escapeHtml(stat.name)}</h3>
                <span class="product-unit">${escapeHtml(stat.unit || "")}</span>
              </div>
              <span class="status-pill status-pill-unavailable">Unavailable</span>
            </div>
            <div class="product-price-row">
              <span class="product-price price-unavailable">Price unavailable</span>
              <span class="product-change change-flat">—</span>
            </div>
            <div class="product-unavailable-notice">
              ${escapeHtml(stat.unavailableReason || "No approved automated source configured")}
            </div>
            <div class="product-source-line">
              ${escapeHtml(stat.sourceLineText || "Automated source not configured")}
            </div>
          </article>
        `;
      }

      const statusClass = (stat.status || "low").toLowerCase();
      const statusPillClass = stat.freshnessStatus === "stale"
        ? "status-pill-stale"
        : stat.benchmarkStatus === "test_proxy"
          ? "status-pill-proxy"
          : `status-${statusClass}`;
      const statusPillText = stat.freshnessStatus === "stale"
        ? "Stale"
        : stat.benchmarkStatus === "test_proxy"
          ? "Proxy"
          : stat.status;

      const trendHistory = stat.history
        ? global.OilRiskMarketCalculations.trendWindow(stat.history, 30)
        : [];
      let sparkHtml = "";
      if (trendHistory.length >= 2) {
        sparkHtml = global.OilRiskCharts.createSparkline(stat.history, stat.tone, {
          days: 30,
          interactiveTooltip: true,
          tooltipTitle: `${stat.name} 30D`,
          commodityCurrency: stat.currency,
          commodityUnit: stat.commodityUnit || stat.unit
        });
      } else {
        sparkHtml = `<div class="spark-insufficient"><span>30D Trend: Insufficient history</span></div>`;
      }

      let zDisplayHtml = "";
      if (stat.historyStatus === "insufficient_history" || !Number.isFinite(stat.zScore)) {
        zDisplayHtml = `
          <div class="product-z z-insufficient">
            Z-score <strong>Insufficient 90D history</strong>
            <span class="outlier-meta">${stat.windowObservationCount} valid observation${stat.windowObservationCount === 1 ? "" : "s"}</span>
          </div>
        `;
      } else {
        const zText = `${stat.zScore >= 0 ? "+" : ""}${stat.zScore.toFixed(2)} sigma`;
        const meanText = formatPlainNumber(stat.mean90, stat.decimals);
        zDisplayHtml = `
          <div class="product-z">
            Z-score <strong>${escapeHtml(zText)}</strong> vs mean ${escapeHtml(meanText)}
            <span class="outlier-meta">${stat.windowObservationCount} valid observations</span>
            ${renderZBar(stat)}
          </div>
        `;
      }

      return `
        <article class="product-card status-${statusClass}" data-instrument="${escapeHtml(stat.key)}">
          <div class="product-top">
            <div>
              <h3 class="product-name">${escapeHtml(stat.name)}</h3>
              <span class="product-unit">${escapeHtml(stat.unit || "")}</span>
            </div>
            <span class="status-pill ${statusPillClass}">${escapeHtml(statusPillText)}</span>
          </div>
          <div class="product-price-row">
            <span class="product-price">${escapeHtml(stat.latestText)}</span>
            <span class="product-change ${escapeHtml(stat.changeClass)}">${escapeHtml(stat.changeText)}</span>
          </div>
          <div class="product-spark">
            ${sparkHtml}
          </div>
          ${zDisplayHtml}
          <div class="product-source-line">
            ${escapeHtml(stat.sourceLineText || "")}
          </div>
        </article>
      `;
    }).join("");
  }

  function renderZBar(stat) {
    const statusColor = {
      Low: "var(--green)",
      Moderate: "var(--amber)",
      High: "var(--oando-red-orange)",
      Catastrophic: "var(--deep-red)"
    }[stat.status] || "var(--muted)";
    const zScore = Number.isFinite(stat.zScore) ? Math.max(-3, Math.min(3, stat.zScore)) : 0;
    const markLeft = ((zScore + 3) / 6) * 100;
    const fillLeft = Math.min(50, markLeft);
    const fillWidth = Math.abs(markLeft - 50);

    return `
      <div class="zbar" aria-hidden="true">
        <span class="zbar-fill" style="left:${fillLeft.toFixed(2)}%;width:${fillWidth.toFixed(2)}%;background:${statusColor};"></span>
        <span class="zbar-mark" style="left:${markLeft.toFixed(2)}%;"></span>
      </div>
    `;
  }

  function renderOutlierScan(stats) {
    const container = document.getElementById("outlierScan");

    if (!container) {
      return;
    }

    const validStats = stats.filter((stat) => Number.isFinite(stat.zScore));

    if (!validStats.length) {
      container.innerHTML = `
        <div class="outlier-empty-state">
          <p class="outlier-empty-title">Insufficient 90D History</p>
          <p class="outlier-empty-desc">Outlier z-scores require minimum 60 daily observations. Statistical outlier detection will activate automatically as daily provider observations accumulate in Supabase.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = validStats
      .slice()
      .sort((a, b) => Math.abs(b.zScore || 0) - Math.abs(a.zScore || 0))
      .map((stat) => {
        const statusClass = (stat.status || "low").toLowerCase();
        const zText = `${stat.zScore >= 0 ? "+" : ""}${stat.zScore.toFixed(2)} sigma`;

        return `
          <div class="outlier-row">
            <div class="outlier-name">
              ${escapeHtml(stat.name)}
              <span class="outlier-meta">${escapeHtml(stat.marketCode)} - ${stat.windowObservationCount} observations</span>
            </div>
            <span class="outlier-score rating-${statusClass}">${escapeHtml(zText)}</span>
          </div>
        `;
      }).join("");
  }

  function buildMarketProductStats(data) {
    const isApi = (data.source && data.source.type === "api") ||
      (global.OilRiskConfig && typeof global.OilRiskConfig.isApiMode === "function" && global.OilRiskConfig.isApiMode());

    return PRODUCT_ORDER.map((product) => {
      const kri = (data.kris && data.kris[product.kriCode]) || {};
      const backendStat = data.backendMarketStats && data.backendMarketStats[product.key];
      const configInst = (global.OilRiskConfig && global.OilRiskConfig.MARKET_INSTRUMENTS && global.OilRiskConfig.MARKET_INSTRUMENTS[product.key]) || {};

      if (isApi) {
        const isUnavailable = backendStat
          ? (backendStat.benchmark_status === "unavailable" || backendStat.current_value === null)
          : (configInst.benchmarkStatus === "unavailable");

        let displayName = product.name;
        if (backendStat && backendStat.provider_display_name) {
          displayName = backendStat.provider_display_name;
        } else if (configInst.providerDisplayName) {
          displayName = configInst.providerDisplayName;
        } else if (configInst.displayName) {
          displayName = configInst.displayName;
        }

        if (product.key === "forcados") displayName = "Forcados";
        if (product.key === "gasoline") displayName = "Gasoline";
        if (product.key === "jet") displayName = "Jet";

        const providerSymbol = (backendStat && backendStat.provider_symbol) || configInst.providerSymbol || null;
        const benchmarkStatus = (backendStat && backendStat.benchmark_status) || configInst.benchmarkStatus || (isUnavailable ? "unavailable" : "confirmed");
        const freshnessStatus = (backendStat && backendStat.freshness_status) || (isUnavailable ? "unavailable" : (data.source && data.source.stale ? "stale" : "fresh"));
        const unavailableReason = (backendStat && backendStat.unavailable_reason) || configInst.unavailableReason || "No approved automated source configured";
        const historyStatus = (backendStat && backendStat.history_status) || "insufficient_history";
        const providerName = (backendStat && backendStat.provider) || configInst.provider || "OilPriceAPI";

        let sourceLineText = "Automated source not configured";
        if (!isUnavailable && providerSymbol) {
          const sourceLabel = providerName === "internal_excel" ? "Internal market workbook" : providerName;
          if (benchmarkStatus === "test_proxy") {
            sourceLineText = `Source: ${sourceLabel} · ${providerSymbol} · Test proxy`;
          } else {
            sourceLineText = `Source: ${sourceLabel} · ${providerSymbol}`;
          }
        }

        const decimals = Number.isFinite(kri.decimals) ? kri.decimals : 2;

        if (isUnavailable) {
          return {
            ...product,
            name: displayName,
            canonicalName: configInst.canonicalName || product.name,
            marketCode: providerSymbol || "",
            unit: (backendStat && backendStat.unit) || configInst.unit || kri.unit || "USD/bbl",
            currency: kri.commodityCurrency || "USD",
            commodityUnit: configInst.unit || kri.unit || "",
            decimals,
            history: [],
            latestValue: null,
            latestText: "Price unavailable",
            previousValue: null,
            change: null,
            percentChange: null,
            changeText: "—",
            changeClass: "change-flat",
            tone: "neutral",
            status: "Unavailable",
            freshnessStatus: "unavailable",
            benchmarkStatus: "unavailable",
            unavailableReason,
            sourceLineText,
            isUnavailable: true,
            historyStatus: "unavailable",
            mean90: null,
            sd90: null,
            zScore: null,
            windowObservationCount: 0
          };
        }

        const latestValue = backendStat ? backendStat.current_value : null;
        const previousValue = backendStat ? backendStat.previous_value : null;
        const change = backendStat ? backendStat.change : null;
        const percentChange = backendStat ? backendStat.percent_change : null;

        const hasHistory = backendStat && Array.isArray(backendStat.history) && backendStat.history.length >= 2;
        const history = hasHistory ? backendStat.history : [];
        const changeText = (change !== null && Number.isFinite(change))
          ? formatDelta(kri, change, percentChange)
          : "—";
        const changeClass = (change === null || change === 0) ? "change-flat" : (change > 0 ? "change-up" : "change-down");
        const tone = (change === null || change === 0) ? "neutral" : (change > 0 ? "negative" : "positive");

        const zScore = backendStat ? backendStat.z_score : null;
        const mean90 = backendStat ? backendStat.mean_90 : null;
        const sd90 = backendStat ? backendStat.std_dev_90 : null;
        const windowObservationCount = backendStat ? (backendStat.window_count || (latestValue !== null ? 1 : 0)) : 0;

        let status = "Active";
        if (freshnessStatus === "stale") {
          status = "Stale";
        } else if (benchmarkStatus === "test_proxy") {
          status = "Proxy";
        } else if (Number.isFinite(zScore)) {
          status = riskStatusFromZ(zScore);
        }

        return {
          ...product,
          name: displayName,
          canonicalName: configInst.canonicalName || product.name,
          marketCode: providerSymbol || "",
          unit: (backendStat && backendStat.unit) || configInst.unit || kri.unit || "USD/bbl",
          currency: kri.commodityCurrency || "USD",
          commodityUnit: configInst.unit || kri.unit || "",
          decimals,
          history,
          latestValue,
          latestText: Number.isFinite(latestValue) ? formatKriValue(kri, latestValue) : "Price unavailable",
          previousValue,
          change,
          percentChange,
          changeText,
          changeClass,
          tone,
          status,
          freshnessStatus,
          benchmarkStatus,
          unavailableReason: null,
          sourceLineText,
          isUnavailable: false,
          historyStatus,
          mean90,
          sd90,
          zScore,
          windowObservationCount
        };
      }

      const stats90 = global.OilRiskMarketCalculations.calculateInstrumentStats(
        data.marketObservations,
        product.key,
        90
      );
      const history = global.OilRiskMarketCalculations.toHistoryPoints(stats90.history);
      const latestValue = stats90.currentValue;
      const previousValue = stats90.previousValue;
      const change = stats90.change;
      const percentChange = stats90.percentChange;
      const status = riskStatusFromZ(stats90.zScore);
      const decimals = Number.isFinite(kri.decimals) ? kri.decimals : 2;

      return {
        ...product,
        name: product.name,
        canonicalName: product.name,
        marketCode: stats90.latestObservation
          ? stats90.latestObservation.providerSymbol
          : kri.providerSymbol || kri.marketDataCode || "",
        unit: kri.unit || "",
        currency: kri.commodityCurrency || "USD",
        commodityUnit: kri.commodityUnit || kri.unit || "",
        decimals,
        history,
        latestValue,
        latestText: formatKriValue(kri, latestValue),
        previousValue,
        change,
        percentChange,
        changeText: formatDelta(kri, change, percentChange),
        changeClass: change === null || change === 0 ? "change-flat" : change > 0 ? "change-up" : "change-down",
        tone: change === null || change === 0 ? "neutral" : change > 0 ? "negative" : "positive",
        status,
        freshnessStatus: "fresh",
        benchmarkStatus: "confirmed",
        unavailableReason: null,
        sourceLineText: `Source: Legacy Platts · ${kri.providerSymbol || kri.marketDataCode || ""}`,
        isUnavailable: false,
        historyStatus: "valid",
        mean90: stats90.mean90,
        sd90: stats90.sd90,
        zScore: stats90.zScore,
        windowObservationCount: stats90.windowObservationCount
      };
    });
  }

  function riskStatusFromZ(zScore) {
    if (!Number.isFinite(zScore)) {
      return "Low";
    }

    const absZ = Math.abs(zScore);

    if (absZ >= Z_SCORE_RISK_CONFIG.outlierMaxAbsZ) {
      return Z_SCORE_RISK_CONFIG.labels.extreme;
    }

    if (absZ >= Z_SCORE_RISK_CONFIG.watchMaxAbsZ) {
      return Z_SCORE_RISK_CONFIG.labels.outlier;
    }

    if (absZ >= Z_SCORE_RISK_CONFIG.normalMaxAbsZ) {
      return Z_SCORE_RISK_CONFIG.labels.watch;
    }

    return Z_SCORE_RISK_CONFIG.labels.normal;
  }

  function renderBriefing() {
    const container = document.getElementById("dailyBriefingContent");

    if (apiModeEnabled()) {
      renderVerifiedNewsActions();
      if (container) {
        container.innerHTML = renderVerifiedNews();
        decorateVerifiedNewsMetadata();
      }
      return;
    }

    renderSectionActions("briefingActions", "briefing", editModes.briefing ? `
      <button class="mini-button secondary" type="button" data-action="add-briefing-region">Add Region</button>
    ` : "");

    if (!container) {
      return;
    }

    if (editModes.briefing) {
      container.innerHTML = renderBriefingEdit();
      return;
    }

    container.innerHTML = `
      <div class="briefing-content">
        ${briefingItems.map((region) => `
          <div class="briefing-region">
            <h3>${escapeHtml(region.title)}</h3>
            ${(region.sections || []).map((section) => `
              <div class="briefing-subsection">
                <span class="category-pill ${escapeHtml(categoryClass(section.title))}">${escapeHtml(categoryLabel(section.title, region.title))}</span>
                <ul class="briefing-list">
                  ${(section.items || []).map((item) => `<li>${escapeHtml(item.headline)}</li>`).join("") || `<li class="empty-state">No items entered.</li>`}
                </ul>
              </div>
            `).join("") || `<p class="empty-state">No sections entered.</p>`}
          </div>
        `).join("")}
      </div>
    `;
  }

  function renderVerifiedNewsActions() {
    const container = document.getElementById("briefingActions");
    if (!container || !isAdmin()) {
      if (container) container.innerHTML = "";
      return;
    }
    container.innerHTML = `<button class="mini-button" type="button" data-action="refresh-news"${newsLoading ? " disabled" : ""}>${newsLoading ? "Refreshing..." : "Refresh News"}</button>`;
  }

  function renderVerifiedNews() {
    const regions = [
      ["international", "International"],
      ["africa", "Africa"],
      ["nigeria", "Nigeria"]
    ];
    const byRegion = new Map(regions.map(([key]) => [key, []]));
    newsItems.forEach((item) => {
      if (byRegion.has(item.region)) {
        byRegion.get(item.region).push(item);
      }
    });

    return `
      <div class="briefing-content verified-news-content">
        ${regions.map(([key, label]) => {
          const items = (byRegion.get(key) || [])
            .slice()
            .sort((a, b) => Date.parse(b.published_at || "") - Date.parse(a.published_at || ""))
            .slice(0, 3);
          return `
            <section class="briefing-region verified-news-region">
              <h3>${label}</h3>
              <ul class="briefing-list verified-news-list">
                ${items.length ? items.map((item) => `
                  <li>
                    <a href="${escapeAttribute(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a>
                    <span class="news-meta">${escapeHtml(item.source_name)} · ${escapeHtml(formatDate(item.published_at))}${item.topic ? ` · ${escapeHtml(item.topic.replaceAll("_", " "))}` : ""}</span>
                  </li>
                `).join("") : `<li class="empty-state">No recent verified stories</li>`}
              </ul>
            </section>
          `;
        }).join("")}
      </div>
    `;
  }

  function decorateVerifiedNewsMetadata() {
    document.querySelectorAll(".verified-news-list .news-meta").forEach((meta) => {
      const parts = meta.textContent.split(/\s+(?:Â·|·)\s+/).map((part) => part.trim()).filter(Boolean);
      const source = parts[0] || "Verified source";
      const date = parts[1] || "--";
      const topic = parts.slice(2).join(" ");

      meta.textContent = "";
      [source, "·", date].forEach((value, index) => {
        const span = document.createElement("span");
        span.textContent = value;
        if (index === 1) {
          span.setAttribute("aria-hidden", "true");
        }
        meta.appendChild(span);
      });

      if (topic) {
        const badge = document.createElement("span");
        badge.className = "news-topic";
        badge.textContent = titleCase(topic);
        meta.appendChild(badge);
      }
    });
  }

  function renderBriefingEdit() {
    return `
      <div class="edit-stack">
        ${briefingItems.map((region, regionIndex) => `
          <div class="edit-card" data-briefing-region="${regionIndex}">
            <div class="edit-row">
              <label>Region
                <input data-field="region-title" type="text" value="${escapeAttribute(region.title)}" />
              </label>
              <div class="inline-actions">
                <button class="mini-button secondary" type="button" data-action="add-briefing-section" data-region="${regionIndex}">Add Section</button>
                <button class="mini-button danger" type="button" data-action="delete-briefing-region" data-region="${regionIndex}">Delete Region</button>
              </div>
            </div>
            ${(region.sections || []).map((section, sectionIndex) => `
              <div class="edit-card compact" data-briefing-section="${sectionIndex}">
                <div class="edit-row">
                  <label>Subsection
                    <input data-field="section-title" type="text" value="${escapeAttribute(section.title)}" />
                  </label>
                  <div class="inline-actions">
                    <button class="mini-button secondary" type="button" data-action="add-briefing-item" data-region="${regionIndex}" data-section-index="${sectionIndex}">Add Item</button>
                    <button class="mini-button danger" type="button" data-action="delete-briefing-section" data-region="${regionIndex}" data-section-index="${sectionIndex}">Delete Section</button>
                  </div>
                </div>
                ${(section.items || []).map((item, itemIndex) => `
                  <div class="edit-row" data-briefing-item="${itemIndex}">
                    <label>Briefing item
                      <textarea data-field="item-headline">${escapeHtml(item.headline)}</textarea>
                    </label>
                    <div class="inline-actions">
                      <button class="mini-button danger" type="button" data-action="delete-briefing-item" data-region="${regionIndex}" data-section-index="${sectionIndex}" data-item="${itemIndex}">Delete Item</button>
                    </div>
                  </div>
                `).join("")}
              </div>
            `).join("")}
          </div>
        `).join("")}
      </div>
    `;
  }

  async function loadLatestAIAnalysis() {
    const result = await global.OilRiskAIService.getLatestDashboardAnalysis();
    aiAnalysisEnvelope = result;
    latestAIAnalysis = result && result.data && result.data.analysis ? result.data.analysis : null;
    renderAIAnalysis();
  }

  async function handleAIRefresh() {
    const button = document.getElementById("aiRefreshButton");
    const status = document.getElementById("aiAnalysisStatus");
    if (!button) {
      return;
    }

    button.disabled = true;
    button.textContent = "Analysing...";
    if (status) {
      status.classList.remove("is-error");
      status.textContent = "Building a verified dashboard context and requesting analysis...";
    }

    const result = await global.OilRiskAIService.generateDashboardAnalysis({ forceRefresh: true });
    aiAnalysisEnvelope = result;
    latestAIAnalysis = result && result.data && result.data.analysis ? result.data.analysis : null;
    renderAIAnalysis();
    button.disabled = false;
    button.textContent = "Refresh AI Analysis";
  }

  function renderAIAnalysis() {
    const content = document.getElementById("aiAnalysisContent");
    const status = document.getElementById("aiAnalysisStatus");
    const timestamp = document.getElementById("aiAnalysisGeneratedAt");
    const button = document.getElementById("aiRefreshButton");
    if (!content || !status || !timestamp) {
      return;
    }

    const response = aiAnalysisEnvelope && (aiAnalysisEnvelope.data || aiAnalysisEnvelope);
    const analysis = latestAIAnalysis;
    const isError = (response && response.status && response.status !== "completed") ||
      (aiAnalysisEnvelope && aiAnalysisEnvelope.available === false);
    status.classList.toggle("is-error", Boolean(isError));
    timestamp.textContent = response && response.generated_at
      ? `Generated ${formatDateTime(response.generated_at)}`
      : "";
    if (button) {
      button.disabled = false;
    }

    if (!analysis) {
      content.innerHTML = `<p class="empty-state">${escapeHtml(
        response && response.message
          ? response.message
          : (aiAnalysisEnvelope && aiAnalysisEnvelope.message) || "No saved AI analysis is available yet."
      )}</p>`;
      status.textContent = isError
        ? (response && response.message || aiAnalysisEnvelope.message || "AI analysis failed.")
        : "Refresh AI Analysis to generate a new interpretation.";
      return;
    }

    status.textContent = response && response.message ? response.message : "Latest completed AI analysis loaded.";
    const sections = [
      ["Daily Briefing", analysis.daily_briefing, ["key_points"]],
      ["Risk Advisor View", analysis.risk_advisor_view, ["key_risks", "watch_items"]],
      ["Trader Desk Pulse", analysis.trader_desk_pulse, ["market_signals"]],
      ["Pattern & Inference", analysis.pattern_and_inference, ["observations"]],
      ["Management Actions", analysis.management_actions, ["actions"]],
      ["Overall Position", analysis.overall_position, []]
    ];

    content.innerHTML = sections.map(([title, section, listKeys]) => {
      if (!section) {
        return "";
      }
      const heading = section.headline || section.summary || section.status || "";
      const summary = section.headline ? section.summary : "";
      const lists = listKeys.map((key) => {
        const values = Array.isArray(section[key]) ? section[key] : [];
        if (key === "actions") {
          return values.length ? `<ul>${values.map((item) => `
            <li class="priority-${escapeAttribute(item.priority || "medium")}">
              <strong>${escapeHtml(item.action || "")}</strong> ${escapeHtml(item.rationale || "")} (${escapeHtml(item.priority || "medium")})
            </li>`).join("")}</ul>` : "";
        }
        return values.length ? `<ul>${values.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : "";
      }).join("");
      return `<section class="ai-analysis-section">
        <h3>${escapeHtml(title)}${title === "Overall Position" ? `: ${escapeHtml(section.status || "")}` : ""}</h3>
        ${heading && !section.headline ? `<p>${escapeHtml(heading)}</p>` : ""}
        ${section.headline ? `<p><strong>${escapeHtml(section.headline)}</strong></p><p>${escapeHtml(summary)}</p>` : ""}
        ${lists}
      </section>`;
    }).join("");

    if (Array.isArray(analysis.data_quality_notes) && analysis.data_quality_notes.length) {
      content.innerHTML += `<section class="ai-analysis-section">
        <h3>Data Quality Notes</h3>
        <ul>${analysis.data_quality_notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul>
      </section>`;
    }
  }

  function renderRiskAdvisor() {
    const container = document.getElementById("riskAdvisorContent");

    renderSectionActions("advisorActions", "advisor");

    if (!container) {
      return;
    }

    if (editModes.advisor) {
      container.innerHTML = `
        <div class="edit-stack">
          ${riskAdvisorItems.map((item, index) => `
            <div class="edit-card" data-advisor-index="${index}">
              <div class="edit-row">
                <label>Classification
                  <select data-field="classification">
                    ${["Threat", "Opportunity", "Watch"].map((option) => `<option value="${option}"${option === item.classification ? " selected" : ""}>${option}</option>`).join("")}
                  </select>
                </label>
                <label>Confidence
                  <input data-field="confidence" type="text" value="${escapeAttribute(item.confidence)}" />
                </label>
              </div>
              <label>Commentary
                <textarea data-field="commentary">${escapeHtml(item.commentary)}</textarea>
              </label>
            </div>
          `).join("")}
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="advisor-content">
        ${riskAdvisorItems.map((item) => {
          const classification = String(item.classification || "Watch");
          return `
            <div class="advisor-call">
              <div class="advisor-call-top">
                <span class="advisor-label ${classification.toLowerCase()}">${escapeHtml(classification)}</span>
                <span class="advisor-confidence">${escapeHtml(item.confidence || "Unassigned")}</span>
              </div>
              <p>${escapeHtml(item.commentary || "No admin-entered commentary.")}</p>
            </div>
          `;
        }).join("")}
      </div>
    `;
  }

  function renderTraderDesk() {
    const container = document.getElementById("traderDeskContent");

    renderSectionActions("deskActions", "desk");

    if (!container) {
      return;
    }

    if (editModes.desk) {
      container.innerHTML = traderDeskItems.map((item, index) => `
        <article class="panel desk-card" data-desk-index="${index}">
          <label>Card title
            <input data-field="title" type="text" value="${escapeAttribute(item.title)}" />
          </label>
          <label>Commentary
            <textarea data-field="body">${escapeHtml(item.body)}</textarea>
          </label>
        </article>
      `).join("");
      return;
    }

    container.innerHTML = traderDeskItems.map((item) => `
      <article class="panel desk-card">
        <h3>${escapeHtml(item.title)}</h3>
        <p>${escapeHtml(item.body || "No admin-entered desk note.")}</p>
      </article>
    `).join("");
  }

  function renderMacroSummary() {
    const grid = document.getElementById("macroMetricGrid");
    const note = document.getElementById("macroWhyItMatters");
    const apiMacroMode = isApiMacroMode();

    renderSectionActions("macroActions", "macro");

    if (!grid || !note) {
      return;
    }

    const displaySummary = apiMacroMode
      ? mergeMacroSummaryWithApi(macroSummary, activeDashboardData)
      : normalizeMacroSummary(macroSummary);
    macroSummary = displaySummary;

    if (editModes.macro && !apiMacroMode) {
      grid.innerHTML = macroSummary.metrics.map((metric, index) => `
        <article class="panel macro-card" data-macro-index="${index}">
          <label>Metric
            <input data-field="title" type="text" value="${escapeAttribute(metric.title)}" />
          </label>
          <label>Period
            <input data-field="period" type="text" value="${escapeAttribute(metric.period)}" />
          </label>
          <label>Value
            <input data-field="value" type="text" value="${escapeAttribute(metric.value)}" />
          </label>
          <label>Note
            <input data-field="note" type="text" value="${escapeAttribute(metric.note)}" />
          </label>
        </article>
      `).join("");
      note.innerHTML = `
        <label>Why it matters
          <textarea data-macro-why>${escapeHtml(macroSummary.whyItMatters)}</textarea>
        </label>
      `;
      return;
    }

    grid.innerHTML = displaySummary.metrics.map(renderMacroCard).join("");

    if (editModes.macro && apiMacroMode) {
      note.innerHTML = `
        <label>Why it matters
          <textarea data-macro-why>${escapeHtml(displaySummary.whyItMatters)}</textarea>
        </label>
      `;
      return;
    }

    note.innerHTML = displaySummary.whyItMatters
      ? `<strong>Why it matters:</strong> ${escapeHtml(displaySummary.whyItMatters)}`
      : `<span class="empty-state">No admin-entered macro commentary.</span>`;
  }

  function renderMacroCard(metric) {
    const titleText = metric.tooltip || metric.note || "";
    const titleAttribute = titleText ? ` title="${escapeAttribute(titleText)}"` : "";
    const freshness = metric.freshnessStatus || "unavailable";

    return `
      <article class="panel macro-card"${titleAttribute}>
        <div class="macro-label">${escapeHtml(metric.title)}</div>
        <div class="macro-value">${escapeHtml(metric.value)}</div>
        <div class="macro-period">${escapeHtml(metric.period)}</div>
        <div class="macro-source">Source: ${escapeHtml(metric.sourceLabel || sourceShortName(metric.source))}</div>
        <div class="macro-freshness freshness-${escapeAttribute(freshness)}">${escapeHtml(freshnessLabel(freshness))}</div>
        ${metric.note ? `<div class="macro-note">${escapeHtml(metric.note)}</div>` : ""}
      </article>
    `;
  }

  function renderInferenceChain() {
    const container = document.getElementById("inferenceContent");

    renderSectionActions("chainActions", "chain");

    if (!container) {
      return;
    }

    if (editModes.chain) {
      container.innerHTML = `
        <div class="edit-stack">
          <div class="edit-row">
            ${inferenceChain.nodes.map((node, index) => `
              <div class="edit-card" data-chain-index="${index}">
                <label>Node label
                  <input data-field="label" type="text" value="${escapeAttribute(node.label)}" />
                </label>
                <label>Detail
                  <textarea data-field="detail">${escapeHtml(node.detail)}</textarea>
                </label>
              </div>
            `).join("")}
          </div>
          <label>Commentary
            <textarea data-chain-commentary>${escapeHtml(inferenceChain.commentary)}</textarea>
          </label>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="chain-row">
        ${inferenceChain.nodes.map((node) => `
          <div class="chain-node">
            <strong>${escapeHtml(node.label)}</strong>
            <span>${escapeHtml(node.detail || "No admin-entered detail.")}</span>
          </div>
        `).join("")}
      </div>
      <p class="chain-commentary">${escapeHtml(inferenceChain.commentary || "No admin-entered inference commentary.")}</p>
    `;
  }

  function renderGeopoliticalRisk(data) {
    const container = document.getElementById("geopoliticalCards");

    renderSectionActions("geoActions", "geo");

    if (!container) {
      return;
    }

    if (editModes.geo) {
      container.innerHTML = geopoliticalCards.map((card, index) => `
        <article class="panel geo-card" data-geo-index="${index}">
          <label>Jurisdiction
            <input data-field="jurisdiction" type="text" value="${escapeAttribute(card.jurisdiction)}" />
          </label>
          <label>Risk rating
            <select data-field="rating">
              ${RISK_SCALE.map((rating) => `<option value="${rating}"${rating === card.rating ? " selected" : ""}>${rating}</option>`).join("")}
            </select>
          </label>
          <label>Current development
            <textarea data-field="currentDevelopment">${escapeHtml(card.currentDevelopment)}</textarea>
          </label>
          <label>Business exposure / implication
            <textarea data-field="implication">${escapeHtml(card.implication)}</textarea>
          </label>
        </article>
      `).join("");
      return;
    }

    container.innerHTML = geopoliticalCards.map((card) => {
      const rating = normalizeRiskRating(card.rating) || "Moderate";
      const currentDevelopment = card.currentDevelopment || deriveGeopoliticalDevelopment(card.jurisdiction, data);

      return `
        <article class="panel geo-card">
          <div class="geo-card-top">
            <h3>${escapeHtml(card.jurisdiction)}</h3>
            <span class="rating-pill rating-${rating.toLowerCase()}">${escapeHtml(rating)}</span>
          </div>
          <div class="geo-label">Current development</div>
          <p>${escapeHtml(currentDevelopment || "No admin-entered development.")}</p>
          <div class="geo-label">Business exposure / implication</div>
          <div class="geo-impact">${escapeHtml(card.implication || "No admin-entered implication.")}</div>
        </article>
      `;
    }).join("");
  }

  function renderRiskRegister() {
    const body = document.getElementById("riskRegisterBody");

    renderSectionActions("registerActions", "register", editModes.register ? `
      <button class="mini-button secondary" type="button" data-action="add-risk-row">Add Row</button>
    ` : "");

    if (!body) {
      return;
    }

    body.innerHTML = riskRegisterRows.map((row, index) => {
      if (editModes.register) {
        return `
          <tr data-risk-row="${index}">
            <td>
              <strong>${index + 1}</strong>
              <button class="mini-button danger" type="button" data-action="delete-risk-row" data-index="${index}">Delete</button>
            </td>
            <td><input data-field="riskCategory" type="text" value="${escapeAttribute(row.riskCategory)}" /></td>
            <td>${renderSelect("materiality", row.materiality, MATERIALITY_OPTIONS)}</td>
            <td>${renderMovementSelect(row.movement)}</td>
            <td><input data-field="riskOwner" type="text" value="${escapeAttribute(row.riskOwner)}" /></td>
          </tr>
        `;
      }

      return `
        <tr>
          <td>${index + 1}</td>
          <td>${escapeHtml(row.riskCategory)}</td>
          <td><span class="materiality-badge materiality-${row.materiality.toLowerCase()}">${escapeHtml(row.materiality)}</span></td>
          <td>${renderMovement(row.movement)}</td>
          <td>${escapeHtml(row.riskOwner)}</td>
        </tr>
      `;
    }).join("");
  }

  function renderForwardCalendar() {
    const container = document.getElementById("forwardCalendarContent");

    renderSectionActions("calendarActions", "calendar", editModes.calendar ? `
      <button class="mini-button secondary" type="button" data-action="add-calendar-row" data-group="marketEvents">Add Market Row</button>
      <button class="mini-button secondary" type="button" data-action="add-calendar-row" data-group="businessEvents">Add Business Row</button>
    ` : "");

    if (!container) {
      return;
    }

    if (editModes.calendar) {
      container.innerHTML = `
        ${renderCalendarEditGroup("Market / Economic Events", "marketEvents", forwardCalendar.marketEvents)}
        ${renderCalendarEditGroup("Business / Political Events", "businessEvents", forwardCalendar.businessEvents)}
      `;
      return;
    }

    container.innerHTML = `
      ${renderCalendarGroup("Market / Economic Events", forwardCalendar.marketEvents)}
      ${renderCalendarGroup("Business / Political Events", forwardCalendar.businessEvents)}
    `;
  }

  function renderCalendarGroup(title, rows) {
    return `
      <article class="panel calendar-card">
        <h3>${escapeHtml(title)}</h3>
        ${rows.length ? rows.map((row) => `
          <div class="calendar-row">
            ${renderCalendarDate(row.date)}
            <div class="calendar-event-content">
              <p class="calendar-title">${escapeHtml(row.title || "Untitled event")}</p>
              <p class="calendar-note">${escapeHtml(row.note || "")}</p>
            </div>
          </div>
        `).join("") : `<p class="empty-state">No upcoming events</p>`}
      </article>
    `;
  }

  function renderCalendarDate(value) {
    const rawDate = String(value || "").trim();
    const match = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(rawDate);

    if (!match) {
      return `<div class="calendar-date calendar-date-tbc"><span>${escapeHtml(rawDate || "TBC")}</span></div>`;
    }

    const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
    if (Number.isNaN(date.getTime())) {
      return `<div class="calendar-date calendar-date-tbc"><span>${escapeHtml(rawDate)}</span></div>`;
    }

    const month = date.toLocaleDateString("en-GB", { month: "short", timeZone: "UTC" }).toUpperCase();
    return `
      <div class="calendar-date" aria-label="${escapeAttribute(rawDate)}">
        <span class="calendar-date-day">${date.getUTCDate()}</span>
        <span class="calendar-date-month">${month}</span>
        <span class="calendar-date-year">${date.getUTCFullYear()}</span>
      </div>
    `;
  }

  function renderCalendarEditGroup(title, group, rows) {
    return `
      <article class="panel calendar-card">
        <h3>${escapeHtml(title)}</h3>
        <div class="edit-stack">
          ${rows.map((row, index) => `
            <div class="edit-card" data-calendar-group="${group}" data-calendar-index="${index}">
              <div class="edit-row three">
                <label>Date
                  <input data-field="date" type="text" value="${escapeAttribute(row.date)}" />
                </label>
                <label>Title
                  <input data-field="title" type="text" value="${escapeAttribute(row.title)}" />
                </label>
                <label>Relevance note
                  <input data-field="note" type="text" value="${escapeAttribute(row.note)}" />
                </label>
              </div>
              <button class="mini-button danger" type="button" data-action="delete-calendar-row" data-group="${group}" data-index="${index}">Delete Row</button>
            </div>
          `).join("") || `<p class="empty-state">No rows entered.</p>`}
        </div>
      </article>
    `;
  }

  function renderManagementActions() {
    const container = document.getElementById("managementActionsContent");

    renderSectionActions("managementActionsControls", "actions", editModes.actions ? `
      <button class="mini-button secondary" type="button" data-action="add-management-item" data-list="takeaways">Add Action</button>
      <button class="mini-button secondary" type="button" data-action="add-management-item" data-list="recommendedActions">Add Recommended</button>
    ` : "");

    if (!container) {
      return;
    }

    if (editModes.actions) {
      container.innerHTML = `
        ${renderManagementEditList("Actions", "takeaways", managementActions.takeaways)}
        ${renderManagementEditList("Recommended Actions", "recommendedActions", managementActions.recommendedActions)}
      `;
      return;
    }

    container.innerHTML = `
      ${renderManagementList("Actions", managementActions.takeaways)}
      ${renderManagementList("Recommended Actions", managementActions.recommendedActions)}
    `;
  }

  function renderManagementList(title, rows) {
    return `
      <article class="management-card">
        <h3>${escapeHtml(title)}</h3>
        ${rows.length ? `<ul>${rows.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : `<p class="empty-state">No admin-entered actions.</p>`}
      </article>
    `;
  }

  function renderManagementEditList(title, listName, rows) {
    return `
      <article class="management-card" data-management-list="${listName}">
        <h3>${escapeHtml(title)}</h3>
        <div class="edit-stack">
          ${rows.map((item, index) => `
            <div class="edit-card" data-management-index="${index}">
              <label>Action
                <textarea data-field="value">${escapeHtml(item)}</textarea>
              </label>
              <button class="mini-button danger" type="button" data-action="delete-management-item" data-list="${listName}" data-index="${index}">Delete</button>
            </div>
          `).join("") || `<p class="empty-state">No rows entered.</p>`}
        </div>
      </article>
    `;
  }

  function renderOverallRisk(data, productStats) {
    const categorySummary = buildCategoryRiskSummary(data, productStats);
    const categories = Object.values(categorySummary.categories);
    const overallScore = weightedAverage(categories, (item) => RISK_SCORES[item.rating], (item) => item.weight);
    const overallRating = overallRatingFromScore(overallScore);
    const gauge = document.getElementById("overallGauge");
    const topDriver = categories.slice().sort((a, b) => RISK_SCORES[b.rating] - RISK_SCORES[a.rating])[0];

    setText("overallRiskLabel", overallRating);
    setText("overallRiskDriver", topDriver ? `Primary driver: ${topDriver.name} (${topDriver.rating})` : "");

    if (gauge) {
      gauge.dataset.rating = overallRating.toLowerCase();
      gauge.style.setProperty("--risk-angle", `${gaugeAngle(overallScore).toFixed(1)}deg`);
    }

    renderCategoryRows(categorySummary.categories);
    const hasValidCategoryData = Boolean(
      data &&
      data.riskSummary &&
      data.riskSummary.categories &&
      Object.keys(data.riskSummary.categories).length
    );
    renderTriggerStrip(hasValidCategoryData ? categorySummary.categories : {});
  }

  function buildCategoryRiskSummary(data, productStats) {
    const categories = {};

    data.categoryOrder.forEach((categoryId) => {
      const category = data.categories[categoryId];
      const calculated = data.riskSummary.categories[categoryId] || {};
      let rating = normalizeRiskRating(calculated.rating) || "Moderate";

      if (categoryId === "market") {
        const marketRating = highestRiskRating(productStats.map((stat) => stat.status));
        rating = highestRiskRating([rating, marketRating]);
      }

      if (categoryRiskOverrides[categoryId]) {
        rating = categoryRiskOverrides[categoryId];
      }

      categories[categoryId] = {
        id: categoryId,
        name: category.name,
        dotClass: category.dotClass,
        rating,
        weight: Number(category.weight || 1)
      };
    });

    return { categories };
  }

  function renderCategoryRows(categories) {
    const container = document.getElementById("categoryRiskRows");

    if (!container) {
      return;
    }

    container.innerHTML = Object.values(categories).map((category) => {
      const rating = category.rating;

      return `
        <div class="category-row">
          <span class="category-name"><span class="dot ${rating.toLowerCase()}"></span>${escapeHtml(category.name)}</span>
          ${isAdmin()
            ? `<select data-category-risk-select="${escapeAttribute(category.id)}">
                ${RISK_SCALE.map((option) => `<option value="${option}"${option === rating ? " selected" : ""}>${option}</option>`).join("")}
              </select>`
            : `<span class="rating-pill rating-${rating.toLowerCase()}">${escapeHtml(rating)}</span>`}
        </div>
      `;
    }).join("");
  }

  function renderSectionActions(containerId, section, extraHtml) {
    const container = document.getElementById(containerId);

    if (!container) {
      return;
    }

    if (!isAdmin()) {
      container.innerHTML = "";
      return;
    }

    const editing = Boolean(editModes[section]);

    container.innerHTML = editing
      ? `
        ${extraHtml || ""}
        <button class="mini-button" type="button" data-action="save-section" data-section="${section}">Save</button>
        <button class="mini-button secondary" type="button" data-action="cancel-section" data-section="${section}">Cancel</button>
      `
      : `<button class="mini-button" type="button" data-action="edit-section" data-section="${section}">Edit</button>`;
  }

  function startEdit(section) {
    if (section === "briefing" && apiModeEnabled()) {
      return;
    }
    if (section === "categories") {
      closeModal("adminPanelModal");
      scrollToSection(SECTION_TARGETS.categories);
      return;
    }

    if (!Object.prototype.hasOwnProperty.call(editModes, section)) {
      return;
    }

    editSnapshots[section] = clone(getSectionState(section));
    editModes[section] = true;
    closeModal("adminPanelModal");
    renderDashboard(activeDashboardData);
    scrollToSection(SECTION_TARGETS[section]);
  }

  function saveSection(section) {
    if (!Object.prototype.hasOwnProperty.call(editModes, section)) {
      return;
    }

    if (section === "briefing") {
      briefingItems = normalizeBriefing(readBriefingDraft());
      saveJson(STORAGE_KEYS.briefing, briefingItems);
    } else if (section === "advisor") {
      riskAdvisorItems = normalizeRiskAdvisor(readAdvisorDraft());
      saveJson(STORAGE_KEYS.riskAdvisor, riskAdvisorItems);
    } else if (section === "desk") {
      traderDeskItems = normalizeTraderDesk(readTraderDeskDraft());
      saveJson(STORAGE_KEYS.traderDesk, traderDeskItems);
    } else if (section === "macro") {
      macroSummary = normalizeMacroSummary(readMacroDraft());
      saveJson(STORAGE_KEYS.macroSummary, macroSummary);
    } else if (section === "chain") {
      inferenceChain = normalizeInferenceChain(readInferenceDraft());
      saveJson(STORAGE_KEYS.inference, inferenceChain);
    } else if (section === "geo") {
      geopoliticalCards = normalizeGeopoliticalCards(readGeoDraft());
      saveJson(STORAGE_KEYS.geopolitical, geopoliticalCards);
    } else if (section === "register") {
      riskRegisterRows = readRiskRegisterDraft();
      saveJson(STORAGE_KEYS.riskRegister, riskRegisterRows);
    } else if (section === "actions") {
      managementActions = normalizeManagementActions(readManagementDraft());
      saveJson(STORAGE_KEYS.managementActions, managementActions);
    } else if (section === "calendar") {
      forwardCalendar = normalizeForwardCalendar(readCalendarDraft());
      saveJson(STORAGE_KEYS.forwardCalendar, forwardCalendar);
    }

    editModes[section] = false;
    delete editSnapshots[section];
    renderDashboard(activeDashboardData);
  }

  function cancelSection(section) {
    if (!Object.prototype.hasOwnProperty.call(editModes, section)) {
      return;
    }

    if (editSnapshots[section]) {
      setSectionState(section, editSnapshots[section]);
    }

    editModes[section] = false;
    delete editSnapshots[section];
    renderDashboard(activeDashboardData);
  }

  function getSectionState(section) {
    return {
      briefing: briefingItems,
      advisor: riskAdvisorItems,
      desk: traderDeskItems,
      macro: macroSummary,
      chain: inferenceChain,
      geo: geopoliticalCards,
      register: riskRegisterRows,
      actions: managementActions,
      calendar: forwardCalendar
    }[section];
  }

  function setSectionState(section, value) {
    if (section === "briefing") {
      briefingItems = normalizeBriefing(value);
    } else if (section === "advisor") {
      riskAdvisorItems = normalizeRiskAdvisor(value);
    } else if (section === "desk") {
      traderDeskItems = normalizeTraderDesk(value);
    } else if (section === "macro") {
      macroSummary = normalizeMacroSummary(value);
    } else if (section === "chain") {
      inferenceChain = normalizeInferenceChain(value);
    } else if (section === "geo") {
      geopoliticalCards = normalizeGeopoliticalCards(value);
    } else if (section === "register") {
      riskRegisterRows = normalizeRiskRegisterRows(value);
    } else if (section === "actions") {
      managementActions = normalizeManagementActions(value);
    } else if (section === "calendar") {
      forwardCalendar = normalizeForwardCalendar(value);
    }
  }

  function readBriefingDraft() {
    return Array.from(document.querySelectorAll("[data-briefing-region]")).map((regionEl) => ({
      id: uniqueId("region"),
      title: valueOf(regionEl, "[data-field='region-title']"),
      sections: Array.from(regionEl.querySelectorAll("[data-briefing-section]")).map((sectionEl) => ({
        id: uniqueId("section"),
        title: valueOf(sectionEl, "[data-field='section-title']"),
        items: Array.from(sectionEl.querySelectorAll("[data-briefing-item]")).map((itemEl) => ({
          id: uniqueId("item"),
          headline: valueOf(itemEl, "[data-field='item-headline']")
        }))
      }))
    }));
  }

  function readAdvisorDraft() {
    return Array.from(document.querySelectorAll("[data-advisor-index]")).map((card) => ({
      classification: valueOf(card, "[data-field='classification']"),
      confidence: valueOf(card, "[data-field='confidence']"),
      commentary: valueOf(card, "[data-field='commentary']")
    }));
  }

  function readTraderDeskDraft() {
    return Array.from(document.querySelectorAll("[data-desk-index]")).map((card) => ({
      title: valueOf(card, "[data-field='title']"),
      body: valueOf(card, "[data-field='body']")
    }));
  }

  function readMacroDraft() {
    return {
      metrics: Array.from(document.querySelectorAll("[data-macro-index]")).map((card) => ({
        title: valueOf(card, "[data-field='title']"),
        period: valueOf(card, "[data-field='period']"),
        value: valueOf(card, "[data-field='value']"),
        note: valueOf(card, "[data-field='note']")
      })),
      whyItMatters: valueOf(document, "[data-macro-why]")
    };
  }

  function readInferenceDraft() {
    return {
      nodes: Array.from(document.querySelectorAll("[data-chain-index]")).map((card) => ({
        label: valueOf(card, "[data-field='label']"),
        detail: valueOf(card, "[data-field='detail']")
      })),
      commentary: valueOf(document, "[data-chain-commentary]")
    };
  }

  function readGeoDraft() {
    return Array.from(document.querySelectorAll("[data-geo-index]")).map((card) => ({
      jurisdiction: valueOf(card, "[data-field='jurisdiction']"),
      rating: normalizeRiskRating(valueOf(card, "[data-field='rating']")) || "Moderate",
      currentDevelopment: valueOf(card, "[data-field='currentDevelopment']"),
      implication: valueOf(card, "[data-field='implication']")
    }));
  }

  function readRiskRegisterDraft() {
    return Array.from(document.querySelectorAll("[data-risk-row]")).map((row) => normalizeRiskRegisterRow({
      riskCategory: valueOf(row, "[data-field='riskCategory']"),
      materiality: valueOf(row, "[data-field='materiality']"),
      movement: valueOf(row, "[data-field='movement']"),
      riskOwner: valueOf(row, "[data-field='riskOwner']")
    }));
  }

  function readCalendarDraft() {
    return {
      marketEvents: readCalendarGroup("marketEvents"),
      businessEvents: readCalendarGroup("businessEvents")
    };
  }

  function readCalendarGroup(group) {
    return Array.from(document.querySelectorAll(`[data-calendar-group="${group}"]`)).map((row) => ({
      date: valueOf(row, "[data-field='date']"),
      title: valueOf(row, "[data-field='title']"),
      note: valueOf(row, "[data-field='note']")
    }));
  }

  function readManagementDraft() {
    return {
      takeaways: readManagementList("takeaways"),
      recommendedActions: readManagementList("recommendedActions")
    };
  }

  function readManagementList(listName) {
    const list = document.querySelector(`[data-management-list="${listName}"]`);

    if (!list) {
      return [];
    }

    return Array.from(list.querySelectorAll("[data-management-index]"))
      .map((row) => valueOf(row, "[data-field='value']"))
      .filter((value) => value.trim() !== "");
  }

  function renderAdminPanel() {
    const list = document.getElementById("adminEditList");

    setText("adminCurrentMarketFile", lastUploadedFile ? lastUploadedFile.name : "--");
    setText("adminLastUploaded", lastUploadedFile ? formatDateTime(lastUploadedFile.uploadedAt) : "--");
    setText("adminRecordsLoaded", lastUploadedFile ? lastUploadedFile.recordsLoaded : "--");
    setText("adminKrisMapped", lastUploadedFile
      ? `${lastUploadedFile.krisMapped} KRIs, ${lastUploadedFile.marketSeriesMapped} market series`
      : "--");

    if (!list) {
      return;
    }

    list.innerHTML = EDITABLE_SECTIONS.map((section) => {
      const isNewsSection = section.id === "briefing" && apiModeEnabled();
      return `
      <div class="admin-edit-item">
        <div>
          <strong>${escapeHtml(section.label)}</strong>
          <span>${escapeHtml(section.detail)}</span>
        </div>
        <button
          class="admin-action-button"
          type="button"
          data-action="${section.id === "categories" ? "open-section" : (isNewsSection ? "refresh-news" : "edit-section")}"
          data-section="${section.id}"
          data-target="${SECTION_TARGETS[section.id] || ""}"
        >
          ${section.id === "categories" ? "Open" : (isNewsSection ? "Refresh" : "Edit")}
        </button>
      </div>
    `;
    }).join("");
  }

  function updateAdminUi() {
    document.body.classList.toggle("is-admin", isAdmin());

    const adminButton = document.getElementById("adminModeButton");

    if (adminButton) {
      adminButton.classList.toggle("is-admin", isAdmin());
      adminButton.textContent = isAdmin() ? "Admin On" : "Admin";
    }
  }

  function loadRiskRegisterRows() {
    return normalizeRiskRegisterRows(loadJson(STORAGE_KEYS.riskRegister, DEFAULT_RISK_REGISTER_ROWS));
  }

  function loadMacroSummary(data) {
    return mergeMacroSummaryWithApi(
      normalizeMacroSummary(loadJson(STORAGE_KEYS.macroSummary, DEFAULT_MACRO_SUMMARY)),
      data
    );
  }

  function loadBriefingItems() {
    return normalizeBriefing(loadJson(STORAGE_KEYS.briefing, DEFAULT_BRIEFING));
  }

  function loadRiskAdvisorItems() {
    return normalizeRiskAdvisor(loadJson(STORAGE_KEYS.riskAdvisor, DEFAULT_RISK_ADVISOR));
  }

  function loadTraderDeskItems() {
    return normalizeTraderDesk(loadJson(STORAGE_KEYS.traderDesk, DEFAULT_TRADER_DESK));
  }

  function loadInferenceChain() {
    return normalizeInferenceChain(loadJson(STORAGE_KEYS.inference, DEFAULT_INFERENCE_CHAIN));
  }

  function loadGeopoliticalCards() {
    return normalizeGeopoliticalCards(loadJson(STORAGE_KEYS.geopolitical, DEFAULT_GEOPOLITICAL_CARDS));
  }

  function loadForwardCalendar() {
    return normalizeForwardCalendar(loadJson(STORAGE_KEYS.forwardCalendar, DEFAULT_FORWARD_CALENDAR));
  }

  function loadManagementActions(data) {
    const fallback = {
      takeaways: Array.isArray(data.takeaways) ? data.takeaways : [],
      recommendedActions: Array.isArray(data.recommendedActions) ? data.recommendedActions : []
    };

    return normalizeManagementActions(loadJson(STORAGE_KEYS.managementActions, fallback));
  }

  function loadCategoryRiskOverrides() {
    const stored = loadJson(STORAGE_KEYS.categoryOverrides, {});
    const result = {};

    Object.keys(stored || {}).forEach((key) => {
      const rating = normalizeRiskRating(stored[key]);

      if (rating) {
        result[key] = rating;
      }
    });

    return result;
  }

  function normalizeRiskRegisterRows(rows) {
    return (Array.isArray(rows) && rows.length ? rows : DEFAULT_RISK_REGISTER_ROWS)
      .map(normalizeRiskRegisterRow);
  }

  function normalizeRiskRegisterRow(row) {
    const source = row || {};
    const materiality = MATERIALITY_OPTIONS.includes(source.materiality)
      ? source.materiality
      : "Moderate";
    const movement = MOVEMENT_OPTIONS.some((option) => option.value === source.movement)
      ? source.movement
      : "unchanged";

    return {
      riskCategory: String(source.riskCategory || ""),
      materiality,
      movement,
      riskOwner: String(source.riskOwner || "")
    };
  }

  function normalizeMacroSummary(source) {
    const input = source || {};
    const sourceMetrics = Array.isArray(input.metrics) ? input.metrics : [];

    return {
      metrics: DEFAULT_MACRO_SUMMARY.metrics.map((defaultMetric, index) => {
        const metric = sourceMetrics.find((candidate) => candidate && candidate.key === defaultMetric.key) ||
          sourceMetrics[index] ||
          {};

        return {
          key: textOr(metric.key, defaultMetric.key),
          title: textOr(metric.title, defaultMetric.title),
          period: textOr(metric.period, defaultMetric.period),
          value: textOr(metric.value, defaultMetric.value),
          source: textOr(metric.source, defaultMetric.source),
          sourceLabel: textOr(metric.sourceLabel, sourceShortName(metric.source || defaultMetric.source)),
          freshnessStatus: textOr(metric.freshnessStatus || metric.freshness_status, defaultMetric.freshnessStatus),
          sourceUrl: textOr(metric.sourceUrl || metric.source_url, ""),
          tooltip: textOr(metric.tooltip, ""),
          note: textOr(metric.note, defaultMetric.note)
        };
      }),
      whyItMatters: textOr(input.whyItMatters, "")
    };
  }

  function mergeMacroSummaryWithApi(summary, data) {
    const normalized = normalizeMacroSummary(summary || DEFAULT_MACRO_SUMMARY);
    const apiMetrics = macroMetricsFromDashboardData(data);

    if (!apiMetrics.length) {
      return normalized;
    }

    return {
      metrics: apiMetrics,
      whyItMatters: normalized.whyItMatters
    };
  }

  function macroMetricsFromDashboardData(data) {
    const source = data || {};
    const snapshot = source.backendSnapshot || {};
    const rawIndicators = Array.isArray(source.macroIndicators)
      ? source.macroIndicators
      : Array.isArray(source.macro_indicators)
        ? source.macro_indicators
        : Array.isArray(snapshot.macro_indicators)
          ? snapshot.macro_indicators
          : [];

    if (!rawIndicators.length) {
      return [];
    }

    const byKey = rawIndicators.reduce((result, item) => {
      if (item && item.indicator_key) {
        result[item.indicator_key] = item;
      }
      return result;
    }, {});

    return MACRO_INDICATOR_DEFINITIONS.map((definition) => {
      const raw = byKey[definition.key] || {};
      const rawValue = raw.value;
      const valueNumber = rawValue === null || rawValue === undefined || rawValue === ""
        ? null
        : Number(rawValue);
      const hasValue = Number.isFinite(valueNumber);
      const sourceName = raw.source || definition.source;
      const freshness = raw.freshness_status || raw.freshnessStatus || (hasValue ? "fresh" : "unavailable");
      const metadata = raw.metadata_json || raw.metadataJson || {};
      const isCrudeOnly = definition.key === "crude_oil_production";

      return {
        key: definition.key,
        title: raw.display_name || definition.title,
        period: raw.reporting_period || "Unavailable",
        value: hasValue ? formatMacroValue(valueNumber, raw.unit || definition.unit, definition.key) : "Data unavailable",
        source: sourceName,
        sourceLabel: sourceShortName(sourceName),
        freshnessStatus: String(freshness).toLowerCase(),
        sourceUrl: raw.source_url || "",
        note: isCrudeOnly ? "Crude only, excluding condensate" : "",
        tooltip: isCrudeOnly
          ? "Crude oil production excludes condensate. Combined crude plus condensate may be preserved only as metadata."
          : metadata.definition || ""
      };
    });
  }

  function formatMacroValue(value, unit, key) {
    if (!Number.isFinite(Number(value))) {
      return "Data unavailable";
    }

    const numeric = Number(value);
    const unitText = unit || "";

    if (unitText === "%") {
      return `${formatFixedTrimmed(numeric, 2)}%`;
    }

    if (unitText === "mbpd") {
      return `${numeric.toFixed(3)} mbpd`;
    }

    if (key === "nigeria_pmi" || unitText === "index") {
      return `${formatFixedTrimmed(numeric, 1)} index`;
    }

    return unitText ? `${formatFixedTrimmed(numeric, 2)} ${unitText}` : formatFixedTrimmed(numeric, 2);
  }

  function formatFixedTrimmed(value, decimals) {
    return Number(value).toFixed(decimals).replace(/\.?0+$/, "");
  }

  function sourceShortName(source) {
    const text = String(source || "");
    const lower = text.toLowerCase();

    if (lower.includes("national bureau of statistics")) {
      return "NBS";
    }

    if (lower.includes("nuprc") || lower.includes("upstream petroleum")) {
      return "NUPRC";
    }

    if (lower.includes("stanbic") || lower.includes("s&p")) {
      return "Stanbic IBTC / S&P Global";
    }

    return text || "Official source";
  }

  function freshnessLabel(status) {
    const normalized = String(status || "unavailable").toLowerCase();

    if (normalized === "extraction_error") {
      return "Extraction error";
    }

    return titleCase(normalized.replace(/_/g, " "));
  }

  function isApiMacroMode() {
    const hasMacroRecords = activeDashboardData && (
      Array.isArray(activeDashboardData.macroIndicators) ||
      Array.isArray(activeDashboardData.macro_indicators) ||
      (activeDashboardData.backendSnapshot && Array.isArray(activeDashboardData.backendSnapshot.macro_indicators))
    );

    return Boolean(hasMacroRecords) ||
      (global.OilRiskConfig && typeof global.OilRiskConfig.isApiMode === "function" && global.OilRiskConfig.isApiMode());
  }

  function normalizeBriefing(source) {
    const regions = Array.isArray(source) ? source : DEFAULT_BRIEFING;

    return regions.map((region, regionIndex) => ({
      id: String(region.id || `region-${regionIndex}`),
      title: textOr(region.title, `Region ${regionIndex + 1}`),
      sections: (Array.isArray(region.sections) ? region.sections : []).map((section, sectionIndex) => ({
        id: String(section.id || `section-${regionIndex}-${sectionIndex}`),
        title: textOr(section.title, "Market"),
        items: (Array.isArray(section.items) ? section.items : []).map((item, itemIndex) => ({
          id: String(item.id || `item-${regionIndex}-${sectionIndex}-${itemIndex}`),
          headline: textOr(item.headline, "")
        }))
      }))
    }));
  }

  function normalizeRiskAdvisor(source) {
    const items = Array.isArray(source) ? source : DEFAULT_RISK_ADVISOR;

    return DEFAULT_RISK_ADVISOR.map((defaultItem, index) => {
      const item = items[index] || {};
      const classification = ["Threat", "Opportunity", "Watch"].includes(item.classification)
        ? item.classification
        : defaultItem.classification;

      return {
        classification,
        confidence: textOr(item.confidence, defaultItem.confidence),
        commentary: textOr(item.commentary, "")
      };
    });
  }

  function normalizeTraderDesk(source) {
    const items = Array.isArray(source) ? source : DEFAULT_TRADER_DESK;

    return DEFAULT_TRADER_DESK.map((defaultItem, index) => {
      const item = items[index] || {};

      return {
        title: textOr(item.title, defaultItem.title),
        body: textOr(item.body, "")
      };
    });
  }

  function normalizeInferenceChain(source) {
    const input = source || {};
    const nodes = Array.isArray(input.nodes) ? input.nodes : [];

    return {
      nodes: DEFAULT_INFERENCE_CHAIN.nodes.map((defaultNode, index) => {
        const node = nodes[index] || {};

        return {
          label: textOr(node.label, defaultNode.label),
          detail: textOr(node.detail, "")
        };
      }),
      commentary: textOr(input.commentary, "")
    };
  }

  function normalizeGeopoliticalCards(source) {
    const items = Array.isArray(source) ? source : DEFAULT_GEOPOLITICAL_CARDS;

    return DEFAULT_GEOPOLITICAL_CARDS.map((defaultCard, index) => {
      const card = items[index] || {};

      return {
        jurisdiction: textOr(card.jurisdiction, defaultCard.jurisdiction),
        rating: normalizeRiskRating(card.rating) || defaultCard.rating,
        currentDevelopment: textOr(card.currentDevelopment, ""),
        implication: textOr(card.implication, "")
      };
    });
  }

  function normalizeForwardCalendar(source) {
    const input = source || {};

    return {
      marketEvents: normalizeCalendarRows(input.marketEvents),
      businessEvents: normalizeCalendarRows(input.businessEvents)
    };
  }

  function normalizeCalendarRows(rows) {
    return (Array.isArray(rows) ? rows : []).map((row) => ({
      date: textOr(row.date, ""),
      title: textOr(row.title, ""),
      note: textOr(row.note, "")
    }));
  }

  function normalizeManagementActions(source) {
    const input = source || {};

    return {
      takeaways: normalizeTextList(input.takeaways),
      recommendedActions: normalizeTextList(input.recommendedActions)
    };
  }

  function normalizeTextList(items) {
    return (Array.isArray(items) ? items : [])
      .map((item) => String(item || "").trim())
      .filter(Boolean);
  }

  function renderSelect(field, value, options) {
    return `
      <select data-field="${field}">
        ${options.map((option) => `<option value="${escapeAttribute(option)}"${option === value ? " selected" : ""}>${escapeHtml(option)}</option>`).join("")}
      </select>
    `;
  }

  function renderMovementSelect(value) {
    return `
      <select data-field="movement">
        ${MOVEMENT_OPTIONS.map((option) => `<option value="${option.value}"${option.value === value ? " selected" : ""}>${option.symbol} ${option.label}</option>`).join("")}
      </select>
    `;
  }

  function renderMovement(value) {
    const selected = MOVEMENT_OPTIONS.find((option) => option.value === value) || MOVEMENT_OPTIONS[1];

    return `
      <span class="trend-indicator trend-${selected.value}">
        ${selected.symbol} ${escapeHtml(selected.label)}
      </span>
    `;
  }

  function buildCategoryLabel(sectionTitle, regionTitle) {
    return categoryLabel(sectionTitle, regionTitle);
  }

  function categoryLabel(sectionTitle, regionTitle) {
    const normalized = String(`${sectionTitle} ${regionTitle}`).toLowerCase();

    if (normalized.includes("nigeria")) {
      return "Nigeria";
    }

    if (normalized.includes("geo") || normalized.includes("polit")) {
      return "Geopolitical";
    }

    if (normalized.includes("refin")) {
      return "Refining";
    }

    if (normalized.includes("supply") || normalized.includes("opec")) {
      return "Supply";
    }

    if (normalized.includes("fx") || normalized.includes("macro")) {
      return "FX";
    }

    return "Market";
  }

  function categoryClass(sectionTitle) {
    return categoryLabel(sectionTitle, "").toLowerCase();
  }

  function deriveGeopoliticalDevelopment(jurisdiction, data) {
    const normalized = String(jurisdiction || "").toLowerCase();

    if (normalized.includes("nigeria")) {
      return findBriefingText("Nigeria");
    }

    if (normalized.includes("africa")) {
      return findBriefingText("Africa");
    }

    if (normalized.includes("middle") || normalized.includes("route")) {
      return (data.geopoliticalWatchlist && data.geopoliticalWatchlist[0]) || "";
    }

    return findBriefingText("International");
  }

  function findBriefingText(regionTitle) {
    const region = briefingItems.find((item) => item.title.toLowerCase() === regionTitle.toLowerCase());

    if (!region) {
      return "";
    }

    for (const section of region.sections || []) {
      const item = (section.items || []).find((candidate) => candidate.headline);

      if (item) {
        return item.headline;
      }
    }

    return "";
  }

  function weightedAverage(items, getScore, getWeight) {
    let weightedScore = 0;
    let totalWeight = 0;

    items.forEach((item) => {
      const score = Number(getScore(item));
      const weight = Number(getWeight(item));

      if (!Number.isFinite(score) || !Number.isFinite(weight) || weight <= 0) {
        return;
      }

      weightedScore += score * weight;
      totalWeight += weight;
    });

    return totalWeight > 0 ? weightedScore / totalWeight : 2;
  }

  function overallRatingFromScore(score) {
    if (score >= 3.25) {
      return "Catastrophic";
    }

    if (score >= 2.5) {
      return "High";
    }

    if (score >= 1.75) {
      return "Moderate";
    }

    return "Low";
  }

  function gaugeAngle(score) {
    const clamped = Math.max(1, Math.min(4, score));
    return -78 + ((clamped - 1) / 3) * 156;
  }

  function highestRiskRating(ratings) {
    return ratings
      .map(normalizeRiskRating)
      .filter(Boolean)
      .sort((a, b) => RISK_SCORES[b] - RISK_SCORES[a])[0] || "Moderate";
  }

  function normalizeRiskRating(value) {
    const normalized = String(value || "").toLowerCase().trim();

    return RISK_SCALE.find((rating) => rating.toLowerCase() === normalized) || "";
  }

  function formatKriValue(kri, value) {
    return global.OilRiskEngine.formatValue(kri, value);
  }

  function formatDelta(kri, change, percentChange) {
    if (change === null) {
      return "N/A";
    }

    const sign = change > 0 ? "+" : change < 0 ? "-" : "";
    const absolute = Math.abs(change);
    let valueText;

    if (kri.commodityValueFormat) {
      valueText = global.OilRiskEngine.formatCommodityValue(
        absolute,
        kri.commodityCurrency || "USD",
        kri.commodityUnit || kri.unit
      );
    } else if (kri.format === "currency" || kri.format === "currency0") {
      valueText = `$${formatPlainNumber(absolute, kri.format === "currency0" ? 0 : Number(kri.decimals || 2))}`;
    } else if (kri.format === "percent") {
      valueText = `${formatPlainNumber(absolute, 1)} pt`;
    } else {
      valueText = formatPlainNumber(absolute, Number(kri.decimals || 2));
    }

    if (!Number.isFinite(percentChange)) {
      return `${sign}${valueText}`;
    }

    return `${sign}${valueText} (${sign}${Math.abs(percentChange).toFixed(1)}%)`;
  }

  function formatPlainNumber(value, decimals) {
    if (!Number.isFinite(Number(value))) {
      return "N/A";
    }

    return Number(value).toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  }

  function formatDate(value) {
    const date = value instanceof Date ? value : parseDate(value);

    if (!date) {
      return "--";
    }

    return date.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric"
    });
  }

  function formatDateTime(value) {
    const date = parseDate(value);

    if (!date) {
      return "--";
    }

    return date.toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  }

  function parseDate(value) {
    if (!value) {
      return null;
    }

    if (value instanceof Date && !Number.isNaN(value.getTime())) {
      return value;
    }

    const text = String(value);
    const date = new Date(text.length === 10 ? `${text}T00:00:00` : text);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function titleCase(value) {
    return String(value || "")
      .replace(/[-_]+/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function textOr(value, fallback) {
    return value === null || value === undefined ? fallback : String(value);
  }

  function valueOf(root, selector) {
    const element = root && root.querySelector ? root.querySelector(selector) : null;
    return element ? element.value.trim() : "";
  }

  function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
      element.textContent = value;
    }
  }

  function setDataMessage(message, isError) {
    const element = document.getElementById("dataLoadMessage");

    if (!element) {
      return;
    }

    element.textContent = message || "";
    element.classList.toggle("error", Boolean(isError));
  }

  function scrollToSection(selector) {
    const target = selector ? document.querySelector(selector) : null;

    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function loadJson(key, fallback) {
    try {
      const stored = global.localStorage.getItem(key);

      if (stored) {
        return JSON.parse(stored);
      }
    } catch (error) {
      // Local storage may be blocked; fall back to built-in content.
    }

    return clone(fallback);
  }

  function saveJson(key, value) {
    try {
      global.localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      setDataMessage("Unable to save local edits in this browser session.", true);
    }
  }

  function clone(value) {
    if (typeof structuredClone === "function") {
      return structuredClone(value);
    }

    return JSON.parse(JSON.stringify(value));
  }

  function uniqueId(prefix) {
    return `${prefix}-${Date.now()}-${Math.round(Math.random() * 100000)}`;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function escapeAttribute(value) {
    return escapeHtml(value).replace(/`/g, "&#096;");
  }

  function buildDashboardAIContext() {
    const data = global.OilRiskData.cloneDashboardData(enrichedDashboardData || activeDashboardData);
    const categorySummary = buildCategoryRiskSummary(data, currentMarketStats);
    const categories = Object.values(categorySummary.categories);
    const overallScore = weightedAverage(
      categories,
      (item) => RISK_SCORES[item.rating],
      (item) => item.weight
    );

    return global.OilRiskAIService.buildDashboardAIContext({
      dashboardData: data,
      marketStats: currentMarketStats,
      macro: macroSummary,
      geopolitical: {
        cards: geopoliticalCards,
        watchlist: data.geopoliticalWatchlist || []
      },
      companyRisk: {
        riskRegister: riskRegisterRows
      },
      overallRisk: {
        score: overallScore,
        rating: overallRatingFromScore(overallScore),
        categories: categorySummary.categories
      },
      briefing: briefingItems,
      riskAdvisor: riskAdvisorItems,
      traderDesk: traderDeskItems,
      managementActions
    });
  }

  global.OilRiskDashboard = {
    buildDashboardAIContext,
    renderDashboard,
    getData() {
      return global.OilRiskData.cloneDashboardData(enrichedDashboardData || activeDashboardData);
    }
  };
})(window);
