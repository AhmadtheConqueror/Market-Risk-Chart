// ============================================================
// DASHBOARD RENDERING
// DOM rendering and user controls only. Data arrives as dashboardData.
// ============================================================

(function registerOilRiskDashboard(global) {
  "use strict";

  const AUTO_REFRESH_INTERVAL = 15 * 60 * 1000;
  const TABLE_IDS = {
    market: "marketRiskTable",
    macro: "macroRiskTable"
  };
  const RISK_RATINGS = ["Low", "Moderate", "High"];
  const RATING_SCORES = {
    Low: 1,
    Moderate: 2,
    High: 3
  };
  const RISK_REGISTER_STORAGE_KEY = "daily-oil-trading-risk-register";
  const MACRO_SUMMARY_STORAGE_KEY = "daily-oil-trading-macro-summary";
  const TRENDING_NEWS_STORAGE_KEY = "daily-oil-trading-trending-news";
  const MANAGEMENT_ACTIONS_STORAGE_KEY = "daily-oil-trading-management-actions";
  const WORKBOOK_HANDLE_DB_NAME = "daily-oil-trading-workbook";
  const WORKBOOK_HANDLE_STORE_NAME = "handles";
  const WORKBOOK_HANDLE_KEY = "activeWorkbook";
  const MATERIALITY_OPTIONS = ["Low", "Moderate", "Major", "Catastrophic"];
  const MOVEMENT_OPTIONS = [
    { value: "increased", label: "Increased", symbol: "\u2191" },
    { value: "unchanged", label: "Unchanged", symbol: "\u2194" },
    { value: "reduced", label: "Reduced", symbol: "\u2193" }
  ];
  const DEFAULT_RISK_REGISTER_ROWS = [
    {
      riskCategory: "Capital Adequacy Risk",
      riskEvent: "Capital ratios could weaken under stress or rapid balance-sheet growth.",
      mitigant: "Maintain capital buffers and monitor internal limits monthly.",
      materiality: "Major",
      movement: "unchanged",
      riskOwner: "CFO"
    },
    {
      riskCategory: "Legal and Contract Management Risk",
      riskEvent: "Contract disputes or weak terms may create loss, delay or unenforceable obligations.",
      mitigant: "Use approved templates, legal review and a central contract register.",
      materiality: "Moderate",
      movement: "unchanged",
      riskOwner: "General Counsel"
    },
    {
      riskCategory: "Counterparty Default Risk",
      riskEvent: "A customer or trading counterparty may default and create receivable losses.",
      mitigant: "Apply counterparty limits, collateral requirements and enhanced monitoring.",
      materiality: "Major",
      movement: "increased",
      riskOwner: "Chief Risk Officer"
    },
    {
      riskCategory: "Project Selection and Planning Risk",
      riskEvent: "Poor project selection or planning may increase cost and delay delivery.",
      mitigant: "Use stage-gate approval, feasibility checks and milestone reviews.",
      materiality: "Moderate",
      movement: "unchanged",
      riskOwner: "COO"
    },
    {
      riskCategory: "Market Opportunity Risk",
      riskEvent: "Missed or mispriced opportunities may reduce earnings and market share.",
      mitigant: "Use market intelligence, approval thresholds and scenario review.",
      materiality: "Moderate",
      movement: "reduced",
      riskOwner: "Commercial Director"
    }
  ];
  const DEFAULT_MACRO_SUMMARY = {
    sectionTitle: "PRICES, GROWTH & REAL ECONOMY",
    metrics: [
      {
        iconClass: "fa-solid fa-cart-shopping",
        title: "Headline Inflation",
        period: "Mar 2026",
        value: "15.38%"
      },
      {
        iconClass: "fa-solid fa-bowl-food",
        title: "Food Inflation",
        period: "Mar 2026",
        value: "14.31%"
      },
      {
        iconClass: "fa-solid fa-bullseye",
        title: "Core Inflation",
        period: "Mar 2026",
        value: "16.21%"
      },
      {
        iconClass: "fa-solid fa-chart-line",
        title: "Real GDP Growth",
        period: "Q4 2025",
        value: "4.07%"
      },
      {
        iconClass: "fa-solid fa-chart-column",
        title: "Real GDP Growth",
        period: "FY 2025",
        value: "3.87%"
      },
      {
        iconClass: "fa-solid fa-industry",
        title: "PMI",
        period: "Mar 2026",
        value: "51.9"
      },
      {
        iconClass: "fa-solid fa-oil-well",
        title: "Oil Production",
        period: "Mar 2026",
        value: "1.546 mbpd"
      }
    ]
  };
  const DEFAULT_TRENDING_NEWS = [
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

  let activeDashboardData = global.OilRiskData.cloneDashboardData(global.dashboardData);
  let enrichedDashboardData = null;
  let lastUploadedFile = null;
  let currentWorkbookHandle = null;
  let pendingWorkbookSelectionMode = "";
  let openCategoryRiskId = "";
  let riskRegisterRows = [];
  let riskRegisterEditing = false;
  let macroSummary = null;
  let macroSummaryEditing = false;
  let trendingNewsItems = [];
  let trendingNewsOriginalItems = [];
  let trendingNewsEditing = false;
  let managementActions = null;
  let managementActionsOriginal = null;
  let managementActionsEditing = false;
  let adminState = {
    authenticated: false,
    role: ""
  };
  let serverModeAvailable = global.location && /^https?:$/.test(global.location.protocol);
  const categoryRiskOverrides = {};

  document.addEventListener("DOMContentLoaded", initialiseDashboard);

  async function initialiseDashboard() {
    riskRegisterRows = loadRiskRegisterRows();
    macroSummary = loadMacroSummary();
    trendingNewsItems = loadTrendingNews();
    managementActions = loadManagementActions(activeDashboardData);
    bindControls();

    if (serverModeAvailable) {
      await refreshAdminStatus();
      await loadServerEditableContent();
      const serverData = await fetchServerMarketData();
      renderDashboard(serverData || activeDashboardData);
    } else {
      renderDashboard(activeDashboardData);
    }

    updateAdminUi();

    setInterval(() => {
      refreshData({ isAutomatic: true });
    }, AUTO_REFRESH_INTERVAL);
  }

  function bindControls() {
    const uploadInput = document.getElementById("excelUpload");
    const uploadTrigger = document.querySelector('label[for="excelUpload"]');
    const refreshButton = document.getElementById("refreshDataButton");
    const sampleButton = document.getElementById("downloadSampleWorkbookButton");
    const riskRegisterEditButton = document.getElementById("riskRegisterEditButton");
    const riskRegisterAddButton = document.getElementById("riskRegisterAddButton");
    const macroSummaryEditButton = document.getElementById("macroSummaryEditButton");
    const macroSummarySaveButton = document.getElementById("macroSummarySaveButton");
    const macroSummaryCancelButton = document.getElementById("macroSummaryCancelButton");
    const trendingNewsEditButton = document.getElementById("trendingNewsEditButton");
    const trendingNewsSaveButton = document.getElementById("trendingNewsSaveButton");
    const trendingNewsCancelButton = document.getElementById("trendingNewsCancelButton");
    const trendingNewsAddRegionButton = document.getElementById("trendingNewsAddRegionButton");
    const managementActionsEditButton = document.getElementById("managementActionsEditButton");
    const managementActionsSaveButton = document.getElementById("managementActionsSaveButton");
    const managementActionsCancelButton = document.getElementById("managementActionsCancelButton");
    const managementActionsAddButton = document.getElementById("managementActionsAddButton");
    const recommendedActionsAddButton = document.getElementById("recommendedActionsAddButton");
    const adminButton = document.getElementById("adminModeButton");
    const adminLoginSubmit = document.getElementById("adminLoginSubmit");
    const adminLoginClose = document.getElementById("adminLoginClose");
    const adminPanelClose = document.getElementById("adminPanelClose");
    const adminLogoutButton = document.getElementById("adminLogoutButton");

    if (uploadInput) {
      uploadInput.addEventListener("change", handleExcelUpload);
    }

    if (uploadTrigger) {
      uploadTrigger.addEventListener("click", handleWorkbookPickerClick);
    }

    if (refreshButton) {
      refreshButton.addEventListener("click", () => {
        refreshData({ isAutomatic: false });
      });
    }

    if (sampleButton) {
      sampleButton.addEventListener("click", handleSampleWorkbookDownload);
    }

    if (riskRegisterEditButton) {
      riskRegisterEditButton.addEventListener("click", handleRiskRegisterEdit);
    }

    if (riskRegisterAddButton) {
      riskRegisterAddButton.addEventListener("click", addRiskRegisterRow);
    }

    if (macroSummaryEditButton) {
      macroSummaryEditButton.addEventListener("click", handleMacroSummaryEdit);
    }

    if (macroSummarySaveButton) {
      macroSummarySaveButton.addEventListener("click", saveMacroSummary);
    }

    if (macroSummaryCancelButton) {
      macroSummaryCancelButton.addEventListener("click", cancelMacroSummary);
    }

    if (trendingNewsEditButton) {
      trendingNewsEditButton.addEventListener("click", handleTrendingNewsEdit);
    }

    if (trendingNewsSaveButton) {
      trendingNewsSaveButton.addEventListener("click", saveTrendingNews);
    }

    if (trendingNewsCancelButton) {
      trendingNewsCancelButton.addEventListener("click", cancelTrendingNews);
    }

    if (trendingNewsAddRegionButton) {
      trendingNewsAddRegionButton.addEventListener("click", addTrendingNewsRegion);
    }

    if (managementActionsEditButton) {
      managementActionsEditButton.addEventListener("click", handleManagementActionsEdit);
    }

    if (managementActionsSaveButton) {
      managementActionsSaveButton.addEventListener("click", saveManagementActions);
    }

    if (managementActionsCancelButton) {
      managementActionsCancelButton.addEventListener("click", cancelManagementActions);
    }

    if (managementActionsAddButton) {
      managementActionsAddButton.addEventListener("click", addManagementAction);
    }

    if (recommendedActionsAddButton) {
      recommendedActionsAddButton.addEventListener("click", addRecommendedAction);
    }

    if (adminButton) {
      adminButton.addEventListener("click", handleAdminButtonClick);
    }

    if (adminLoginSubmit) {
      adminLoginSubmit.addEventListener("click", handleAdminLogin);
    }

    if (adminLoginClose) {
      adminLoginClose.addEventListener("click", () => closeModal("adminLoginModal"));
    }

    if (adminPanelClose) {
      adminPanelClose.addEventListener("click", () => closeModal("adminPanelModal"));
    }

    if (adminLogoutButton) {
      adminLogoutButton.addEventListener("click", handleAdminLogout);
    }

    document.querySelectorAll("[data-admin-scroll-target]").forEach((button) => {
      button.addEventListener("click", () => {
        const target = document.querySelector(button.dataset.adminScrollTarget);

        closeModal("adminPanelModal");

        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    });

    document.addEventListener("click", handleCategoryRiskControlClick);
    document.addEventListener("click", handleRiskRegisterRowAction);
    document.addEventListener("click", handleTrendingNewsAction);
    document.addEventListener("click", handleManagementActionsAction);
  }

  function isAdmin() {
    return Boolean(adminState && adminState.authenticated && adminState.role === "admin");
  }

  async function apiRequest(endpoint, options) {
    const settings = options || {};
    const response = await fetch(endpoint, {
      credentials: "same-origin",
      headers: {
        ...(settings.body && !(settings.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...(settings.headers || {})
      },
      ...settings
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(payload.error || "Request failed.");
    }

    return payload;
  }

  async function refreshAdminStatus() {
    try {
      adminState = await apiRequest("/api/auth/status");
    } catch (error) {
      serverModeAvailable = false;
      adminState = {
        authenticated: false,
        role: ""
      };
    }
  }

  async function fetchServerMarketData() {
    try {
      return await apiRequest("/api/market-data");
    } catch (error) {
      setDataMessage("Unable to load server market data. Showing local sample.", true);
      return null;
    }
  }

  async function loadServerEditableContent() {
    try {
      const [
        macroData,
        newsData,
        riskRegisterData,
        managementData,
        categoryData
      ] = await Promise.all([
        apiRequest("/api/macro-metrics"),
        apiRequest("/api/news"),
        apiRequest("/api/risk-register"),
        apiRequest("/api/management-actions"),
        apiRequest("/api/risk-categories")
      ]);

      macroSummary = normalizeMacroSummary(macroData);
      trendingNewsItems = normalizeTrendingNews(newsData);
      riskRegisterRows = Array.isArray(riskRegisterData)
        ? riskRegisterData.map(normalizeRiskRegisterRow)
        : riskRegisterRows;
      managementActions = normalizeManagementActions(managementData);

      if (Array.isArray(categoryData)) {
        categoryData.forEach((item) => {
          const rating = normalizeManualRating(item.rating);

          if (item.category && rating) {
            categoryRiskOverrides[item.category] = rating;
          }
        });
      }
    } catch (error) {
      // Local-storage defaults remain active if the backend is unavailable.
    }
  }

  function updateAdminUi() {
    const admin = isAdmin();
    const adminButton = document.getElementById("adminModeButton");

    if (document.body) {
      document.body.classList.toggle("is-admin", admin);
    }

    if (!admin) {
      const wasEditingMacroSummary = macroSummaryEditing;
      const wasEditingTrendingNews = trendingNewsEditing;
      const wasEditingRiskRegister = riskRegisterEditing;
      const wasEditingManagementActions = managementActionsEditing;

      macroSummaryEditing = false;
      trendingNewsEditing = false;
      riskRegisterEditing = false;
      managementActionsEditing = false;

      if (wasEditingMacroSummary) {
        renderMacroSummary();
      }

      if (wasEditingTrendingNews) {
        renderTrendingNews();
      }

      if (wasEditingRiskRegister) {
        renderRiskRegister();
      }

      if (wasEditingManagementActions) {
        renderManagementActions(enrichedDashboardData || activeDashboardData);
      }
    }

    document.querySelectorAll("[data-admin-only]").forEach((element) => {
      element.hidden = !admin;
    });

    if (adminButton) {
      adminButton.classList.toggle("is-admin", admin);
      adminButton.title = admin ? "Admin controls" : "Admin login";
      adminButton.setAttribute("aria-label", admin ? "Open admin controls" : "Admin login");
    }

    updateMacroSummaryControls();
    updateTrendingNewsControls();
    updateRiskRegisterControls();
    updateManagementActionsControls();
  }

  function handleAdminButtonClick() {
    if (isAdmin()) {
      openAdminPanel();
      return;
    }

    openModal("adminLoginModal");
  }

  async function handleAdminLogin() {
    const username = document.getElementById("adminUsername");
    const password = document.getElementById("adminPassword");
    const message = document.getElementById("adminLoginMessage");

    if (message) {
      message.textContent = "";
    }

    if (!serverModeAvailable) {
      if (message) {
        message.textContent = global.location && global.location.protocol === "file:"
          ? "Admin login works from http://localhost:3000, not the file path."
          : "Admin login requires the local dashboard server.";
      }

      return;
    }

    try {
      adminState = await apiRequest("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username: username ? username.value.trim() : "",
          password: password ? password.value : ""
        })
      });
      closeModal("adminLoginModal");
      updateAdminUi();
      await refreshAdminPanelStatus();
      openModal("adminPanelModal");
    } catch (error) {
      if (message) {
        message.textContent = error.message === "Failed to fetch"
          ? "Could not reach the dashboard server. Open http://localhost:3000."
          : error.message || "Invalid username or password.";
      }
    }
  }

  async function handleAdminLogout() {
    try {
      await apiRequest("/api/auth/logout", { method: "POST" });
    } catch (error) {
      // Still clear the local state if the session is already gone.
    }

    adminState = {
      authenticated: false,
      role: ""
    };
    closeModal("adminPanelModal");
    updateAdminUi();
  }

  async function openAdminPanel() {
    await refreshAdminPanelStatus();
    openModal("adminPanelModal");
  }

  async function refreshAdminPanelStatus() {
    if (!isAdmin()) {
      return;
    }

    try {
      const status = await apiRequest("/api/admin/market-data-status");
      const upload = status.activeUpload || {};

      setText("adminCurrentMarketFile", upload.original_filename || "--");
      setText("adminLastUploaded", upload.uploaded_at ? formatDateTime(upload.uploaded_at) : "--");
      setText("adminRecordsLoaded", upload.record_count ?? "--");
      setText("adminKrisMapped", upload.total_kri_count
        ? `${upload.mapped_kri_count} / ${upload.total_kri_count}`
        : "--");
    } catch (error) {
      setText("adminCurrentMarketFile", "--");
      setText("adminLastUploaded", "--");
      setText("adminRecordsLoaded", "--");
      setText("adminKrisMapped", "--");
    }
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

    if (!file) {
      return;
    }

    if (!isAdmin()) {
      setDataMessage("Admin login is required to replace market data.", true);
      event.target.value = "";
      return;
    }

    if (serverModeAvailable) {
      await uploadMarketDataWorkbook(file);
      event.target.value = "";
      return;
    }

    currentWorkbookHandle = null;
    setLoading(true);
    setDataMessage(pendingWorkbookSelectionMode === "refresh"
      ? "Refreshing workbook..."
      : "Loading workbook...");

    try {
      await loadWorkbookFile(file, {
        successPrefix: pendingWorkbookSelectionMode === "refresh" ? "Refreshed" : "Loaded"
      });
    } catch (error) {
      setDataMessage(friendlyWorkbookError(error, "Unable to load workbook."), true);
    } finally {
      pendingWorkbookSelectionMode = "";
      setLoading(false);
      event.target.value = "";
    }
  }

  async function handleWorkbookPickerClick(event) {
    if (!isAdmin()) {
      event.preventDefault();
      setDataMessage("Admin login is required to select a workbook.", true);
      return;
    }

    if (serverModeAvailable) {
      return;
    }

    if (!canUseWorkbookPicker()) {
      return;
    }

    event.preventDefault();
    await chooseWorkbookWithPicker({
      loadingMessage: "Loading workbook...",
      successPrefix: "Loaded"
    });
  }

  function canUseWorkbookPicker() {
    return typeof global.showOpenFilePicker === "function";
  }

  function openWorkbookHandleDb() {
    return new Promise((resolve, reject) => {
      if (!global.indexedDB) {
        resolve(null);
        return;
      }

      const request = global.indexedDB.open(WORKBOOK_HANDLE_DB_NAME, 1);

      request.onupgradeneeded = () => {
        const db = request.result;

        if (!db.objectStoreNames.contains(WORKBOOK_HANDLE_STORE_NAME)) {
          db.createObjectStore(WORKBOOK_HANDLE_STORE_NAME);
        }
      };

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      request.onblocked = () => resolve(null);
    });
  }

  async function rememberWorkbookHandle(handle) {
    try {
      const db = await openWorkbookHandleDb();

      if (!db) {
        return;
      }

      await new Promise((resolve, reject) => {
        const transaction = db.transaction(WORKBOOK_HANDLE_STORE_NAME, "readwrite");
        transaction.objectStore(WORKBOOK_HANDLE_STORE_NAME).put(handle, WORKBOOK_HANDLE_KEY);
        transaction.oncomplete = resolve;
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error);
      });
      db.close();
    } catch (error) {
      // Some browsers do not allow FileSystemHandle storage. Refresh still works for the current tab.
    }
  }

  async function readRememberedWorkbookHandle() {
    try {
      const db = await openWorkbookHandleDb();

      if (!db) {
        return null;
      }

      const handle = await new Promise((resolve, reject) => {
        const transaction = db.transaction(WORKBOOK_HANDLE_STORE_NAME, "readonly");
        const request = transaction.objectStore(WORKBOOK_HANDLE_STORE_NAME).get(WORKBOOK_HANDLE_KEY);
        request.onsuccess = () => resolve(request.result || null);
        request.onerror = () => reject(request.error);
      });
      db.close();

      return handle;
    } catch (error) {
      return null;
    }
  }

  async function chooseWorkbookWithPicker(options) {
    const settings = options || {};
    setLoading(true);
    setDataMessage(settings.loadingMessage || "Loading workbook...");

    try {
      const handles = await global.showOpenFilePicker({
        multiple: false,
        types: [{
          description: "Excel Workbook",
          accept: {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
            "application/vnd.ms-excel": [".xls"]
          }
        }]
      });
      const handle = handles && handles[0];

      if (!handle) {
        setDataMessage("");
        return;
      }

      const file = await handle.getFile();
      currentWorkbookHandle = handle;
      await rememberWorkbookHandle(handle);
      await loadWorkbookFile(file, { successPrefix: settings.successPrefix || "Loaded" });
      return true;
    } catch (error) {
      if (isUserAbort(error)) {
        setDataMessage("");
        return false;
      }

      currentWorkbookHandle = null;
      setDataMessage(friendlyWorkbookError(error, settings.errorMessage || "Unable to load workbook."), true);
      return false;
    } finally {
      pendingWorkbookSelectionMode = "";
      setLoading(false);
    }
  }

  async function loadWorkbookFile(file, options) {
    const settings = options || {};
    const workbookData = await global.OilRiskExcel.readWorkbookData(file);
    const normalizedData = global.OilRiskExcel.normalizeWorkbookRecords(workbookData.records, {
      sourceName: file.name,
      plattsMarketData: workbookData.plattsMarketData,
      coreExportData: workbookData.coreExportData
    });

    lastUploadedFile = file;
    activeDashboardData = normalizedData;
    renderDashboard(activeDashboardData);

    const info = normalizedData.importInfo;
    const totalKris = Object.keys(normalizedData.kris || {}).length;
    const prefix = settings.successPrefix || "Loaded";
    setDataMessage(`${prefix} ${info.recordsRead} rows; mapped ${info.mappedKris} of ${totalKris} KRIs.`);
  }

  async function refreshData(options) {
    const settings = options || {};

    setLoading(true);

    try {
      if (serverModeAvailable) {
        if (!settings.isAutomatic && isAdmin()) {
          const response = await apiRequest("/api/admin/reprocess-market-data", {
            method: "POST"
          });

          renderDashboard(response.data);
          setDataMessage(response.message || "Market data reprocessed.");
          await refreshAdminPanelStatus();
          return;
        }

        const data = await fetchServerMarketData();

        if (data) {
          renderDashboard(data);

          if (!settings.isAutomatic) {
            setDataMessage("Data refreshed.");
          }
        }

        return;
      }

      if (activeDashboardData.source.type === "live") {
        activeDashboardData = await global.OilRiskExcel.fetchDashboardDataFromApi(
          activeDashboardData.source.refreshEndpoint
        );
      } else if (currentWorkbookHandle) {
        const file = await getFileFromWorkbookHandle(settings);
        await loadWorkbookFile(file, { successPrefix: "Refreshed" });

        return;
      } else if (lastUploadedFile) {
        if (!settings.isAutomatic) {
          await promptForWorkbookReselection();
        }

        return;
      } else {
        const storedHandle = !settings.isAutomatic ? await readRememberedWorkbookHandle() : null;

        if (storedHandle) {
          currentWorkbookHandle = storedHandle;
          const file = await getFileFromWorkbookHandle(settings);
          await loadWorkbookFile(file, { successPrefix: "Refreshed" });

          return;
        }

        activeDashboardData = global.OilRiskData.cloneDashboardData(global.dashboardData);
        activeDashboardData.source.lastRefreshed = new Date().toISOString();
      }

      renderDashboard(activeDashboardData);

      if (!settings.isAutomatic) {
        setDataMessage("Data refreshed.");
      }
    } catch (error) {
      if (!settings.isAutomatic) {
        if (isFileAccessError(error)) {
          await promptForWorkbookReselection();
          return;
        }

        setDataMessage(friendlyWorkbookError(error, "Unable to refresh data."), true);
      }
    } finally {
      setLoading(false);
    }
  }

  async function uploadMarketDataWorkbook(file) {
    const formData = new FormData();
    formData.append("workbook", file);
    setLoading(true);
    setDataMessage("Uploading workbook...");

    try {
      const response = await apiRequest("/api/admin/upload-market-data", {
        method: "POST",
        body: formData
      });

      if (response.data) {
        renderDashboard(response.data);
      }

      setDataMessage(response.message || "Workbook uploaded successfully.");
      await refreshAdminPanelStatus();
    } catch (error) {
      setDataMessage(error.message || "Unable to upload workbook. Please try again.", true);
    } finally {
      setLoading(false);
    }
  }

  async function getFileFromWorkbookHandle(settings) {
    const permissionOptions = { mode: "read" };
    const handle = currentWorkbookHandle;

    if (!handle) {
      throw new Error("No workbook handle is available.");
    }

    if (typeof handle.queryPermission === "function") {
      let permission = await handle.queryPermission(permissionOptions);

      if (permission !== "granted" && !settings.isAutomatic && typeof handle.requestPermission === "function") {
        permission = await handle.requestPermission(permissionOptions);
      }

      if (permission !== "granted") {
        throw new Error("Access to the Excel file is required. Please select the workbook again.");
      }
    }

    return handle.getFile();
  }

  async function promptForWorkbookReselection() {
    pendingWorkbookSelectionMode = "refresh";

    if (canUseWorkbookPicker()) {
      await chooseWorkbookWithPicker({
        loadingMessage: "Refreshing workbook...",
        successPrefix: "Refreshed",
        errorMessage: "Unable to refresh workbook."
      });
      return;
    }

    setDataMessage("Please select the Excel workbook again to refresh the dashboard.");

    const uploadInput = document.getElementById("excelUpload");

    if (uploadInput && typeof uploadInput.click === "function") {
      uploadInput.click();
    }
  }

  function friendlyWorkbookError(error, fallbackMessage) {
    if (isUserAbort(error)) {
      return "";
    }

    if (isFileAccessError(error)) {
      return "The Excel file could not be reopened. Please select the workbook again.";
    }

    return error && error.message ? error.message : fallbackMessage;
  }

  function isUserAbort(error) {
    return error && error.name === "AbortError";
  }

  function isFileAccessError(error) {
    const message = String(error && error.message || "").toLowerCase();
    const name = String(error && error.name || "").toLowerCase();

    return name.includes("notreadable") ||
      name.includes("security") ||
      name.includes("notallowed") ||
      message.includes("permission") ||
      message.includes("could not be read") ||
      message.includes("could not be reopened") ||
      message.includes("access to the excel file is required");
  }

  function handleSampleWorkbookDownload() {
    try {
      global.OilRiskExcel.downloadSampleWorkbook();
      setDataMessage("Sample workbook created.");
    } catch (error) {
      setDataMessage(error.message || "Unable to create sample workbook.", true);
    }
  }

  function renderDashboard(rawData) {
    activeDashboardData = global.OilRiskData.cloneDashboardData(rawData);
    enrichedDashboardData = global.OilRiskEngine.enrichDashboardData(activeDashboardData);

    renderMetadata(enrichedDashboardData);
    renderRiskTables(enrichedDashboardData);
    renderTrendingNews();
    renderManagementActions(enrichedDashboardData);
    renderMacroSummary();
    renderRiskRegister();
    renderOverallRisk(enrichedDashboardData);
    global.OilRiskCharts.renderAll(enrichedDashboardData);
  }

  function renderMetadata(data) {
    updateDashboardDate();
    setText("dataSourceLabel", data.source.label || titleCase(data.source.type));
    setText("dataSourceDetail", data.source.name || "Dashboard data");
    setText("lastRefreshed", formatDateTime(data.source.lastRefreshed));

    const sourceDot = document.getElementById("dataSourceDot");

    if (sourceDot) {
      sourceDot.className = `source-dot source-${data.source.type || "demo"}`;
    }
  }

  function updateDashboardDate() {
    const now = new Date();
    const formatted = now.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric"
    }).replace("Sept", "Sep");

    setText("dashboardDate", formatted);
  }

  function renderRiskTables(data) {
    data.categoryOrder.forEach((categoryId) => {
      const tableId = TABLE_IDS[categoryId];

      if (!tableId) {
        return;
      }

      const table = document.getElementById(tableId);

      if (!table) {
        return;
      }

      const category = data.categories[categoryId];
      const kris = category.kriCodes
        .map((code) => data.kris[code])
        .filter(Boolean);

      table.innerHTML = kris.map((kri) => (
        categoryId === "company"
          ? renderCompanyRow(kri)
          : renderStandardRow(kri, categoryId)
      )).join("");
    });
  }

  function renderStandardRow(kri, categoryId) {
    const trendDays = categoryId === "market" ? 30 : null;

    return `
      <tr>
        <td>${renderKriIdentity(kri)}</td>
        <td>
          <span class="latest-value">${escapeHtml(kri.metrics.valueText)}</span>
        </td>
        <td class="${getDeltaClass(kri.metrics.tone)}">
          ${escapeHtml(kri.metrics.deltaText)}
        </td>
        <td>
          ${global.OilRiskCharts.createSparkline(kri.history, kri.metrics.tone, {
            days: trendDays,
            wide: categoryId === "market",
            interactiveTooltip: categoryId === "market",
            tooltipTitle: kri.name,
            commodityCurrency: kri.commodityCurrency,
            commodityUnit: kri.commodityUnit || kri.unit,
            unit: kri.unit
          })}
        </td>
      </tr>
    `;
  }

  function renderCompanyRow(kri) {
    return `
      <tr>
        <td>${renderKriIdentity(kri)}</td>
        <td>${escapeHtml(kri.exposure || "--")}</td>
        <td>
          <span class="latest-value">${escapeHtml(kri.metrics.valueText)}</span>
        </td>
        <td class="${getDeltaClass(kri.metrics.tone)}">
          ${escapeHtml(kri.metrics.deltaText)}
        </td>
        <td>
          ${global.OilRiskCharts.createSparkline(kri.history, kri.metrics.tone)}
        </td>
      </tr>
    `;
  }

  function renderKriIdentity(kri) {
    return `
      <span class="kri-name">${escapeHtml(kri.name)}</span>
      <span class="kri-unit">(${escapeHtml(kri.unit || "No unit")})</span>
    `;
  }

  function renderStatusBadge(status) {
    const normalizedStatus = String(status || "Moderate").toLowerCase();

    return `
      <span class="badge ${normalizedStatus}">
        ${escapeHtml(status || "Moderate")}
      </span>
    `;
  }

  function renderTrendingNews() {
    const list = document.getElementById("trendingNewsItems");

    if (!list) {
      return;
    }

    list.innerHTML = trendingNewsEditing
      ? trendingNewsItems.map((region, regionIndex) => `
          <section class="trending-news-region-edit" data-trending-news-region-index="${regionIndex}">
            <div class="trending-news-region-toolbar">
              <input
                class="trending-news-region-input"
                data-trending-news-region-field="title"
                type="text"
                value="${escapeHtml(region.title)}"
                aria-label="Region heading"
              />
              <button
                class="trending-news-delete"
                type="button"
                data-trending-news-delete-region="${regionIndex}"
                aria-label="Delete ${escapeHtml(region.title || `region ${regionIndex + 1}`)} region"
                title="Delete region"
              >
                <i class="fa-solid fa-trash-can"></i>
              </button>
            </div>

            <div class="trending-news-subsections">
              ${region.sections.map((section, sectionIndex) => `
                <div class="trending-news-subsection-edit" data-trending-news-section-index="${sectionIndex}">
                  <div class="trending-news-subsection-toolbar">
                    <input
                      class="trending-news-subsection-input"
                      data-trending-news-section-field="title"
                      type="text"
                      value="${escapeHtml(section.title)}"
                      aria-label="Subsection label"
                    />
                    <button
                      class="trending-news-delete"
                      type="button"
                      data-trending-news-delete-section="${regionIndex}:${sectionIndex}"
                      aria-label="Delete subsection ${sectionIndex + 1}"
                      title="Delete subsection"
                    >
                      <i class="fa-solid fa-trash-can"></i>
                    </button>
                  </div>

                  <div class="trending-news-edit-items">
                    ${section.items.map((item, itemIndex) => `
                      <div class="trending-news-edit-item" data-trending-news-item-index="${itemIndex}">
                        <span class="trending-news-bullet" aria-hidden="true">&bull;</span>
                        <textarea
                          class="trending-news-input"
                          data-trending-news-field="headline"
                          rows="2"
                          aria-label="News item"
                        >${escapeHtml(item.headline)}</textarea>
                        <button
                          class="trending-news-delete"
                          type="button"
                          data-trending-news-delete-item="${regionIndex}:${sectionIndex}:${itemIndex}"
                          aria-label="Delete news item ${itemIndex + 1}"
                          title="Delete news item"
                        >
                          <i class="fa-solid fa-trash-can"></i>
                        </button>
                      </div>
                    `).join("")}
                  </div>

                  <button
                    class="trending-news-add-control"
                    type="button"
                    data-trending-news-add-item="${regionIndex}:${sectionIndex}"
                  >
                    <i class="fa-solid fa-plus"></i>
                    Add News Item
                  </button>
                </div>
              `).join("")}
            </div>

            <button
              class="trending-news-add-control"
              type="button"
              data-trending-news-add-section="${regionIndex}"
            >
              <i class="fa-solid fa-plus"></i>
              Add Subsection
            </button>
          </section>
        `).join("")
      : trendingNewsItems.map((region) => `
          <section class="trending-news-region">
            <h4>${escapeHtml(region.title)}</h4>
            ${region.sections.map((section) => `
              <div class="trending-news-subsection">
                <h5>${escapeHtml(section.title)}</h5>
                <ul>
                  ${section.items.map((item) => `<li>${escapeHtml(item.headline)}</li>`).join("")}
                </ul>
              </div>
            `).join("")}
          </section>
        `).join("");

    bindTrendingNewsTextareas();
    updateTrendingNewsControls();
  }

  function bindTrendingNewsTextareas() {
    const list = document.getElementById("trendingNewsItems");

    if (!list || !trendingNewsEditing) {
      return;
    }

    list.querySelectorAll(".trending-news-input").forEach((textarea) => {
      const resizeTextarea = () => {
        textarea.style.height = "auto";
        textarea.style.height = `${textarea.scrollHeight}px`;
      };

      textarea.addEventListener("input", resizeTextarea);
      resizeTextarea();
    });
  }

  function handleTrendingNewsEdit() {
    if (!isAdmin()) {
      return;
    }

    trendingNewsOriginalItems = cloneTrendingNewsItems(trendingNewsItems);
    trendingNewsEditing = true;
    renderTrendingNews();
  }

  async function saveTrendingNews() {
    if (!isAdmin()) {
      return;
    }

    trendingNewsItems = readTrendingNewsDraft();

    if (serverModeAvailable) {
      try {
        trendingNewsItems = normalizeTrendingNews(await apiRequest("/api/admin/news", {
          method: "PUT",
          body: JSON.stringify({ items: trendingNewsItems })
        }));
      } catch (error) {
        setDataMessage(error.message || "Unable to save Trending News. Please try again.", true);
        return;
      }
    } else {
      try {
        global.localStorage.setItem(
          TRENDING_NEWS_STORAGE_KEY,
          JSON.stringify(trendingNewsItems)
        );
      } catch (error) {
        // The panel remains usable if browser storage is unavailable.
      }
    }

    trendingNewsEditing = false;
    trendingNewsOriginalItems = [];
    renderTrendingNews();
  }

  function cancelTrendingNews() {
    trendingNewsItems = cloneTrendingNewsItems(trendingNewsOriginalItems);
    trendingNewsOriginalItems = [];
    trendingNewsEditing = false;
    renderTrendingNews();
  }

  function handleTrendingNewsAction(event) {
    if (!isAdmin() || !trendingNewsEditing) {
      return;
    }

    const deleteItemButton = event.target.closest("[data-trending-news-delete-item]");

    if (deleteItemButton) {
      const [regionIndex, sectionIndex, itemIndex] = deleteItemButton.dataset.trendingNewsDeleteItem
        .split(":")
        .map(Number);
      trendingNewsItems = readTrendingNewsDraft();
      trendingNewsItems[regionIndex].sections[sectionIndex].items.splice(itemIndex, 1);
      renderTrendingNews();
      return;
    }

    const deleteSectionButton = event.target.closest("[data-trending-news-delete-section]");

    if (deleteSectionButton) {
      const [regionIndex, sectionIndex] = deleteSectionButton.dataset.trendingNewsDeleteSection
        .split(":")
        .map(Number);
      trendingNewsItems = readTrendingNewsDraft();
      trendingNewsItems[regionIndex].sections.splice(sectionIndex, 1);
      renderTrendingNews();
      return;
    }

    const deleteRegionButton = event.target.closest("[data-trending-news-delete-region]");

    if (deleteRegionButton) {
      const regionIndex = Number(deleteRegionButton.dataset.trendingNewsDeleteRegion);
      trendingNewsItems = readTrendingNewsDraft();
      trendingNewsItems.splice(regionIndex, 1);
      renderTrendingNews();
      return;
    }

    const addItemButton = event.target.closest("[data-trending-news-add-item]");

    if (addItemButton) {
      const [regionIndex, sectionIndex] = addItemButton.dataset.trendingNewsAddItem
        .split(":")
        .map(Number);
      trendingNewsItems = readTrendingNewsDraft();
      trendingNewsItems[regionIndex].sections[sectionIndex].items.push({
        id: createTrendingNewsId("item"),
        headline: ""
      });
      renderTrendingNews();
      return;
    }

    const addSectionButton = event.target.closest("[data-trending-news-add-section]");

    if (addSectionButton) {
      const regionIndex = Number(addSectionButton.dataset.trendingNewsAddSection);
      trendingNewsItems = readTrendingNewsDraft();
      trendingNewsItems[regionIndex].sections.push({
        id: createTrendingNewsId("section"),
        title: "New Subsection",
        items: [{
          id: createTrendingNewsId("item"),
          headline: ""
        }]
      });
      renderTrendingNews();
      return;
    }

    const addRegionButton = event.target.closest("[data-trending-news-add-region]");

    if (addRegionButton) {
      addTrendingNewsRegion();
    }
  }

  function addTrendingNewsRegion() {
    if (!isAdmin()) {
      return;
    }

    trendingNewsItems = readTrendingNewsDraft();
    trendingNewsItems.push({
      id: createTrendingNewsId("region"),
      title: "New Region",
      sections: [{
        id: createTrendingNewsId("section"),
        title: "Oil & Gas",
        items: [{
          id: createTrendingNewsId("item"),
          headline: ""
        }]
      }]
    });
    trendingNewsEditing = true;
    renderTrendingNews();
  }

  function readTrendingNewsDraft() {
    const list = document.getElementById("trendingNewsItems");

    if (!list) {
      return trendingNewsItems;
    }

    return Array.from(list.querySelectorAll("[data-trending-news-region-index]")).map((regionElement, regionIndex) => {
      const originalRegion = trendingNewsItems[regionIndex] || {};
      const titleElement = regionElement.querySelector("[data-trending-news-region-field=\"title\"]");

      return {
        id: originalRegion.id || createTrendingNewsId("region"),
        title: titleElement ? titleElement.value.trim() : String(originalRegion.title || ""),
        sections: Array.from(regionElement.querySelectorAll("[data-trending-news-section-index]")).map((sectionElement, sectionIndex) => {
          const originalSection = originalRegion.sections && originalRegion.sections[sectionIndex]
            ? originalRegion.sections[sectionIndex]
            : {};
          const sectionTitleElement = sectionElement.querySelector("[data-trending-news-section-field=\"title\"]");

          return {
            id: originalSection.id || createTrendingNewsId("section"),
            title: sectionTitleElement
              ? sectionTitleElement.value.trim()
              : String(originalSection.title || ""),
            items: Array.from(sectionElement.querySelectorAll("[data-trending-news-item-index]")).map((itemElement, itemIndex) => {
              const originalItem = originalSection.items && originalSection.items[itemIndex]
                ? originalSection.items[itemIndex]
                : {};
              const headlineElement = itemElement.querySelector("[data-trending-news-field=\"headline\"]");

              return {
                id: originalItem.id || createTrendingNewsId("item"),
                headline: headlineElement ? headlineElement.value.trim() : String(originalItem.headline || "")
              };
            })
          };
        })
      };
    });
  }

  function createTrendingNewsId(type) {
    return `news-${type}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  }

  function cloneTrendingNewsItems(items) {
    return (items || []).map((region) => ({
      ...region,
      sections: (region.sections || []).map((section) => ({
        ...section,
        items: (section.items || []).map((item) => ({ ...item }))
      }))
    }));
  }

  function loadTrendingNews() {
    try {
      const storedItems = global.localStorage.getItem(TRENDING_NEWS_STORAGE_KEY);

      if (storedItems) {
        const parsedItems = JSON.parse(storedItems);

        if (Array.isArray(parsedItems)) {
          if (parsedItems.some((item) => item && Array.isArray(item.sections))) {
            return parsedItems.map(normalizeTrendingNewsRegion);
          }

          const migratedItems = normalizeTrendingNews(DEFAULT_TRENDING_NEWS);
          const legacyItems = parsedItems
            .map((item, index) => normalizeTrendingNewsItem(item, index))
            .filter((item) => item.headline);
          const nigeria = migratedItems.find((region) => region.id === "nigeria");

          if (nigeria && legacyItems.length) {
            nigeria.sections[0].items = legacyItems;
          }

          return migratedItems;
        }
      }
    } catch (error) {
      // Use the structured sample when browser storage is unavailable or invalid.
    }

    return normalizeTrendingNews(DEFAULT_TRENDING_NEWS);
  }

  function normalizeTrendingNews(items) {
    return (Array.isArray(items) ? items : []).map(normalizeTrendingNewsRegion);
  }

  function normalizeTrendingNewsRegion(region, regionIndex) {
    const source = region || {};
    const sections = Array.isArray(source.sections) ? source.sections : [];

    return {
      id: String(source.id || `region-${regionIndex + 1}`),
      title: String(source.title ?? ""),
      sections: sections.map((section, sectionIndex) => normalizeTrendingNewsSection(section, regionIndex, sectionIndex))
    };
  }

  function normalizeTrendingNewsSection(section, regionIndex, sectionIndex) {
    const source = section || {};
    const items = Array.isArray(source.items) ? source.items : [];

    return {
      id: String(source.id || `section-${regionIndex + 1}-${sectionIndex + 1}`),
      title: String(source.title ?? ""),
      items: items.map((item, itemIndex) => normalizeTrendingNewsItem(item, itemIndex, regionIndex, sectionIndex))
    };
  }

  function normalizeTrendingNewsItem(item, itemIndex, regionIndex = 0, sectionIndex = 0) {
    const source = item || {};

    return {
      id: String(source.id || `item-${regionIndex + 1}-${sectionIndex + 1}-${itemIndex + 1}`),
      headline: String(source.headline ?? "")
    };
  }

  function updateTrendingNewsControls() {
    const editButton = document.getElementById("trendingNewsEditButton");
    const saveButton = document.getElementById("trendingNewsSaveButton");
    const cancelButton = document.getElementById("trendingNewsCancelButton");
    const addRegionButton = document.getElementById("trendingNewsAddRegionButton");

    if (editButton) {
      editButton.hidden = !isAdmin() || trendingNewsEditing;
    }

    if (saveButton) {
      saveButton.hidden = !isAdmin() || !trendingNewsEditing;
    }

    if (cancelButton) {
      cancelButton.hidden = !isAdmin() || !trendingNewsEditing;
    }

    if (addRegionButton) {
      addRegionButton.hidden = !isAdmin() || !trendingNewsEditing;
    }
  }

  function renderManagementActions(data) {
    const source = managementActions || loadManagementActions(data);

    managementActions = normalizeManagementActions(source, data);
    renderTakeaways(managementActions);
    renderRecommendedActions(managementActions);
    bindManagementActionsTextareas();
    updateManagementActionsControls();
  }

  function renderTakeaways(actions) {
    const list = document.getElementById("takeawayList");

    if (!list) {
      return;
    }

    if (managementActionsEditing) {
      list.innerHTML = (actions.takeaways || []).map((item, index) => `
        <div class="takeaway-item" data-management-action-index="${index}">
          <span>${index + 1}</span>
          <div class="management-actions-edit-row">
            <textarea
              class="management-actions-input"
              data-management-actions-field="takeaway"
              aria-label="Management action ${index + 1}"
            >${escapeHtml(item)}</textarea>
            <button
              class="management-actions-delete"
              type="button"
              data-management-actions-delete-takeaway="${index}"
              aria-label="Delete management action ${index + 1}"
              title="Delete action"
            >
              <i class="fa-solid fa-trash"></i>
            </button>
          </div>
        </div>
      `).join("");
      return;
    }

    list.innerHTML = (actions.takeaways || []).map((item, index) => `
      <div class="takeaway-item">
        <span>${index + 1}</span>
        ${escapeHtml(item)}
      </div>
    `).join("");
  }

  function renderRecommendedActions(actions) {
    const list = document.getElementById("recommendedActions");

    if (!list) {
      return;
    }

    list.classList.toggle("recommended-actions-edit-list", managementActionsEditing);

    if (managementActionsEditing) {
      list.innerHTML = (actions.recommendedActions || []).map((item, index) => `
        <li data-recommended-action-index="${index}">
          <div class="recommended-actions-edit-row">
            <textarea
              class="management-actions-input"
              data-management-actions-field="recommended"
              aria-label="Recommended action ${index + 1}"
            >${escapeHtml(item)}</textarea>
            <button
              class="management-actions-delete"
              type="button"
              data-management-actions-delete-recommended="${index}"
              aria-label="Delete recommended action ${index + 1}"
              title="Delete recommended action"
            >
              <i class="fa-solid fa-trash"></i>
            </button>
          </div>
        </li>
      `).join("");
      return;
    }

    list.innerHTML = (actions.recommendedActions || [])
      .map((item) => `<li>${escapeHtml(item)}</li>`)
      .join("");
  }

  function bindManagementActionsTextareas() {
    if (!managementActionsEditing) {
      return;
    }

    document.querySelectorAll(".management-actions-input").forEach((textarea) => {
      const resizeTextarea = () => {
        textarea.style.height = "auto";
        textarea.style.height = `${textarea.scrollHeight}px`;
      };

      textarea.addEventListener("input", resizeTextarea);
      resizeTextarea();
    });
  }

  function handleManagementActionsEdit() {
    if (!isAdmin()) {
      return;
    }

    managementActionsOriginal = cloneManagementActions(managementActions);
    managementActions = cloneManagementActions(managementActions);
    managementActionsEditing = true;
    renderManagementActions(enrichedDashboardData || activeDashboardData);
  }

  async function saveManagementActions() {
    if (!isAdmin()) {
      return;
    }

    managementActions = normalizeManagementActions(readManagementActionsDraft());

    if (serverModeAvailable) {
      try {
        managementActions = normalizeManagementActions(await apiRequest("/api/admin/management-actions", {
          method: "PUT",
          body: JSON.stringify(managementActions)
        }));
      } catch (error) {
        setDataMessage(error.message || "Unable to save Management Actions. Please try again.", true);
        return;
      }
    } else {
      try {
        global.localStorage.setItem(
          MANAGEMENT_ACTIONS_STORAGE_KEY,
          JSON.stringify(managementActions)
        );
      } catch (error) {
        // The card remains editable if browser storage is unavailable.
      }
    }

    managementActionsOriginal = null;
    managementActionsEditing = false;
    renderManagementActions(enrichedDashboardData || activeDashboardData);
  }

  function cancelManagementActions() {
    managementActions = cloneManagementActions(managementActionsOriginal);
    managementActionsOriginal = null;
    managementActionsEditing = false;
    renderManagementActions(enrichedDashboardData || activeDashboardData);
  }

  function addManagementAction() {
    if (!isAdmin()) {
      return;
    }

    managementActions = readManagementActionsDraft();
    managementActions.takeaways.push("");
    managementActionsEditing = true;
    renderManagementActions(enrichedDashboardData || activeDashboardData);
  }

  function addRecommendedAction() {
    if (!isAdmin()) {
      return;
    }

    managementActions = readManagementActionsDraft();
    managementActions.recommendedActions.push("");
    managementActionsEditing = true;
    renderManagementActions(enrichedDashboardData || activeDashboardData);
  }

  function handleManagementActionsAction(event) {
    if (!isAdmin() || !managementActionsEditing) {
      return;
    }

    const takeawayDeleteButton = event.target.closest("[data-management-actions-delete-takeaway]");

    if (takeawayDeleteButton) {
      const index = Number(takeawayDeleteButton.dataset.managementActionsDeleteTakeaway);
      managementActions = readManagementActionsDraft();
      managementActions.takeaways.splice(index, 1);
      renderManagementActions(enrichedDashboardData || activeDashboardData);
      return;
    }

    const recommendedDeleteButton = event.target.closest("[data-management-actions-delete-recommended]");

    if (recommendedDeleteButton) {
      const index = Number(recommendedDeleteButton.dataset.managementActionsDeleteRecommended);
      managementActions = readManagementActionsDraft();
      managementActions.recommendedActions.splice(index, 1);
      renderManagementActions(enrichedDashboardData || activeDashboardData);
    }
  }

  function readManagementActionsDraft() {
    const takeaways = Array.from(document.querySelectorAll("[data-management-actions-field=\"takeaway\"]"))
      .map((field) => field.value.trim())
      .filter(Boolean);
    const recommendedActions = Array.from(document.querySelectorAll("[data-management-actions-field=\"recommended\"]"))
      .map((field) => field.value.trim())
      .filter(Boolean);

    return normalizeManagementActions({
      takeaways,
      recommendedActions
    });
  }

  function loadManagementActions(data) {
    try {
      const storedActions = global.localStorage.getItem(MANAGEMENT_ACTIONS_STORAGE_KEY);

      if (storedActions) {
        return normalizeManagementActions(JSON.parse(storedActions), data);
      }
    } catch (error) {
      // Use dashboard defaults when browser storage is unavailable or invalid.
    }

    return normalizeManagementActions(data || global.dashboardData);
  }

  function normalizeManagementActions(source, fallback) {
    const sourceActions = source || {};
    const fallbackActions = fallback || global.dashboardData || {};

    return {
      takeaways: normalizeTextList(sourceActions.takeaways, fallbackActions.takeaways),
      recommendedActions: normalizeTextList(sourceActions.recommendedActions, fallbackActions.recommendedActions)
    };
  }

  function normalizeTextList(items, fallbackItems) {
    const sourceItems = Array.isArray(items) ? items : fallbackItems;

    return (Array.isArray(sourceItems) ? sourceItems : [])
      .map((item) => String(item || "").trim())
      .filter(Boolean);
  }

  function cloneManagementActions(actions) {
    return normalizeManagementActions(actions || managementActions || global.dashboardData);
  }

  function updateManagementActionsControls() {
    const editButton = document.getElementById("managementActionsEditButton");
    const saveButton = document.getElementById("managementActionsSaveButton");
    const cancelButton = document.getElementById("managementActionsCancelButton");
    const addButton = document.getElementById("managementActionsAddButton");
    const addRecommendedButton = document.getElementById("recommendedActionsAddButton");

    if (editButton) {
      editButton.hidden = !isAdmin() || managementActionsEditing;
    }

    if (saveButton) {
      saveButton.hidden = !isAdmin() || !managementActionsEditing;
    }

    if (cancelButton) {
      cancelButton.hidden = !isAdmin() || !managementActionsEditing;
    }

    if (addButton) {
      addButton.hidden = !isAdmin() || !managementActionsEditing;
    }

    if (addRecommendedButton) {
      addRecommendedButton.hidden = !isAdmin() || !managementActionsEditing;
    }
  }

  function renderMacroSummary() {
    const title = document.getElementById("macroSummarySectionTitle");
    const tiles = document.getElementById("macroSummaryTiles");

    if (!title || !tiles || !macroSummary) {
      return;
    }

    title.innerHTML = macroSummaryEditing
      ? `<input
          class="macro-summary-title-input"
          data-macro-section-title
          type="text"
          value="${escapeHtml(macroSummary.sectionTitle)}"
        />`
      : escapeHtml(macroSummary.sectionTitle);

    tiles.innerHTML = macroSummary.metrics.map((metric, index) => `
      <div class="macro-summary-tile" data-macro-index="${index}">
        <div class="macro-summary-icon" aria-hidden="true">
          <i class="${escapeHtml(metric.iconClass)}"></i>
        </div>
        ${macroSummaryEditing
          ? `<input
              class="macro-summary-input macro-summary-metric-title"
              data-macro-field="title"
              type="text"
              value="${escapeHtml(metric.title)}"
            />
            <input
              class="macro-summary-input macro-summary-period"
              data-macro-field="period"
              type="text"
              value="${escapeHtml(metric.period)}"
            />
            <input
              class="macro-summary-input macro-summary-value"
              data-macro-field="value"
              type="text"
              value="${escapeHtml(metric.value)}"
            />`
          : `<div class="macro-summary-metric-title">${escapeHtml(metric.title)}</div>
            <div class="macro-summary-period">(${escapeHtml(metric.period)})</div>
            <strong class="macro-summary-value">${escapeHtml(metric.value)}</strong>`}
      </div>
    `).join("");

    updateMacroSummaryControls();
  }

  function handleMacroSummaryEdit() {
    if (!isAdmin()) {
      return;
    }

    macroSummaryEditing = true;
    renderMacroSummary();
  }

  async function saveMacroSummary() {
    if (!isAdmin()) {
      return;
    }

    macroSummary = readMacroSummaryDraft();

    if (serverModeAvailable) {
      try {
        macroSummary = normalizeMacroSummary(await apiRequest("/api/admin/macro-metrics", {
          method: "PUT",
          body: JSON.stringify(macroSummary)
        }));
      } catch (error) {
        setDataMessage(error.message || "Unable to save Macro Metrics. Please try again.", true);
        return;
      }
    } else {
      try {
        global.localStorage.setItem(
          MACRO_SUMMARY_STORAGE_KEY,
          JSON.stringify(macroSummary)
        );
      } catch (error) {
        // The panel remains usable if browser storage is unavailable.
      }
    }

    macroSummaryEditing = false;
    renderMacroSummary();
  }

  function cancelMacroSummary() {
    macroSummaryEditing = false;
    renderMacroSummary();
  }

  function readMacroSummaryDraft() {
    const tiles = document.getElementById("macroSummaryTiles");
    const sectionTitle = document.querySelector("[data-macro-section-title]");

    if (!tiles) {
      return macroSummary;
    }

    return {
      sectionTitle: sectionTitle ? sectionTitle.value.trim() : macroSummary.sectionTitle,
      metrics: Array.from(tiles.querySelectorAll("[data-macro-index]")).map((tile, index) => {
        const getValue = (field) => {
          const element = tile.querySelector(`[data-macro-field="${field}"]`);
          return element ? element.value.trim() : macroSummary.metrics[index][field];
        };

        return {
          id: macroSummary.metrics[index].id,
          key: macroSummary.metrics[index].key,
          iconClass: macroSummary.metrics[index].iconClass,
          title: getValue("title"),
          period: getValue("period"),
          value: getValue("value")
        };
      })
    };
  }

  function loadMacroSummary() {
    try {
      const storedSummary = global.localStorage.getItem(MACRO_SUMMARY_STORAGE_KEY);

      if (storedSummary) {
        return normalizeMacroSummary(JSON.parse(storedSummary));
      }
    } catch (error) {
      // Use the sample strip when browser storage is unavailable or invalid.
    }

    return normalizeMacroSummary(DEFAULT_MACRO_SUMMARY);
  }

  function normalizeMacroSummary(source) {
    const input = source || {};
    const metrics = Array.isArray(input.metrics) ? input.metrics : [];

    return {
      sectionTitle: macroSummaryText(input.sectionTitle, DEFAULT_MACRO_SUMMARY.sectionTitle),
      metrics: DEFAULT_MACRO_SUMMARY.metrics.map((defaultMetric, index) => {
        const metric = metrics[index] || {};

        return {
          id: metric.id,
          key: metric.key,
          iconClass: metric.iconClass || defaultMetric.iconClass,
          title: macroSummaryText(metric.title, defaultMetric.title),
          period: macroSummaryText(metric.period, defaultMetric.period),
          value: macroSummaryText(metric.value, defaultMetric.value)
        };
      })
    };
  }

  function macroSummaryText(value, fallback) {
    return value === null || value === undefined
      ? fallback
      : String(value);
  }

  function updateMacroSummaryControls() {
    const editButton = document.getElementById("macroSummaryEditButton");
    const saveButton = document.getElementById("macroSummarySaveButton");
    const cancelButton = document.getElementById("macroSummaryCancelButton");

    if (editButton) {
      editButton.hidden = !isAdmin() || macroSummaryEditing;
    }

    if (saveButton) {
      saveButton.hidden = !isAdmin() || !macroSummaryEditing;
    }

    if (cancelButton) {
      cancelButton.hidden = !isAdmin() || !macroSummaryEditing;
    }
  }

  function renderRiskRegister() {
    const body = document.getElementById("riskRegisterBody");

    if (!body) {
      return;
    }

    body.innerHTML = riskRegisterRows.map((row, index) => `
      <tr>
        <td class="risk-register-number-cell">
          <span>${index + 1}</span>
          ${riskRegisterEditing ? `
            <button
              class="risk-register-delete"
              type="button"
              data-risk-register-delete="${index}"
              aria-label="Delete risk row ${index + 1}"
              title="Delete row"
            >
              <i class="fa-solid fa-trash-can"></i>
            </button>
          ` : ""}
        </td>
        ${renderRiskRegisterTextCell(row, "riskCategory")}
        ${renderRiskRegisterTextCell(row, "riskEvent")}
        ${renderRiskRegisterTextCell(row, "mitigant")}
        <td class="materiality-cell">
          ${riskRegisterEditing
            ? `<div class="materiality-edit">
                ${renderRiskRegisterSelect("materiality", row.materiality, MATERIALITY_OPTIONS)}
                ${renderRiskRegisterSelect("movement", row.movement, MOVEMENT_OPTIONS)}
              </div>`
            : `<div class="materiality-display">
                <span class="materiality-badge ${row.materiality.toLowerCase()}">${escapeHtml(row.materiality)}</span>
                ${renderMovementIndicator(row.movement)}
              </div>`}
        </td>
        ${renderRiskRegisterTextCell(row, "riskOwner", "risk-owner-cell")}
      </tr>
    `).join("");

    updateRiskRegisterControls();
  }

  function renderRiskRegisterTextCell(row, field, cellClass) {
    const classAttribute = cellClass ? ` class="${cellClass}"` : "";

    return `
      <td${classAttribute}>
        ${riskRegisterEditing
          ? `<input
              class="risk-register-input"
              type="text"
              data-risk-register-field="${field}"
              value="${escapeHtml(row[field])}"
            />`
          : `<span>${escapeHtml(row[field])}</span>`}
      </td>
    `;
  }

  function renderRiskRegisterSelect(field, value, options) {
    const optionMarkup = options.map((option) => {
      const optionValue = typeof option === "string" ? option : option.value;
      const optionLabel = typeof option === "string"
        ? option
        : `${option.symbol} ${option.label}`;

      return `
        <option value="${escapeHtml(optionValue)}"${optionValue === value ? " selected" : ""}>
          ${escapeHtml(optionLabel)}
        </option>
      `;
    }).join("");

    return `<select class="risk-register-select" data-risk-register-field="${field}">${optionMarkup}</select>`;
  }

  function renderMovementIndicator(movement) {
    const selectedMovement = MOVEMENT_OPTIONS.find((option) => option.value === movement)
      || MOVEMENT_OPTIONS[1];

    return `
      <span class="movement-indicator ${selectedMovement.value}">
        <span class="movement-arrow" aria-hidden="true">${selectedMovement.symbol}</span>
        ${selectedMovement.label}
      </span>
    `;
  }

  function handleRiskRegisterEdit() {
    if (!isAdmin()) {
      return;
    }

    if (riskRegisterEditing) {
      saveRiskRegister();
      return;
    }

    riskRegisterEditing = true;
    renderRiskRegister();
  }

  function addRiskRegisterRow() {
    if (!isAdmin()) {
      return;
    }

    riskRegisterRows = readRiskRegisterDraft();
    riskRegisterRows.push({
      riskCategory: "",
      riskEvent: "",
      mitigant: "",
      materiality: "Moderate",
      movement: "unchanged",
      riskOwner: ""
    });
    riskRegisterEditing = true;
    renderRiskRegister();
  }

  function handleRiskRegisterRowAction(event) {
    if (!isAdmin()) {
      return;
    }

    const deleteButton = event.target.closest("[data-risk-register-delete]");

    if (!deleteButton || !riskRegisterEditing) {
      return;
    }

    const rowIndex = Number(deleteButton.dataset.riskRegisterDelete);

    if (!Number.isInteger(rowIndex)) {
      return;
    }

    riskRegisterRows = readRiskRegisterDraft();
    riskRegisterRows.splice(rowIndex, 1);
    renderRiskRegister();
  }

  async function saveRiskRegister() {
    if (!isAdmin()) {
      return;
    }

    riskRegisterRows = readRiskRegisterDraft();

    if (serverModeAvailable) {
      try {
        riskRegisterRows = (await apiRequest("/api/admin/risk-register", {
          method: "PUT",
          body: JSON.stringify({ rows: riskRegisterRows })
        })).map(normalizeRiskRegisterRow);
      } catch (error) {
        setDataMessage(error.message || "Unable to save Risk Register entry. Please try again.", true);
        return;
      }
    } else {
      try {
        global.localStorage.setItem(
          RISK_REGISTER_STORAGE_KEY,
          JSON.stringify(riskRegisterRows)
        );
      } catch (error) {
        // The table remains usable if browser storage is unavailable.
      }
    }

    riskRegisterEditing = false;
    renderRiskRegister();
  }

  function readRiskRegisterDraft() {
    const body = document.getElementById("riskRegisterBody");

    if (!body) {
      return riskRegisterRows;
    }

    return Array.from(body.querySelectorAll("tr")).map((row) => {
      const getValue = (field) => {
        const fieldElement = row.querySelector(`[data-risk-register-field="${field}"]`);
        return fieldElement ? fieldElement.value : "";
      };

      return normalizeRiskRegisterRow({
        riskCategory: getValue("riskCategory"),
        riskEvent: getValue("riskEvent"),
        mitigant: getValue("mitigant"),
        materiality: getValue("materiality"),
        movement: getValue("movement") || "unchanged",
        riskOwner: getValue("riskOwner")
      });
    });
  }

  function loadRiskRegisterRows() {
    try {
      const storedRows = global.localStorage.getItem(RISK_REGISTER_STORAGE_KEY);

      if (storedRows) {
        const parsedRows = JSON.parse(storedRows);

        if (Array.isArray(parsedRows)) {
          return parsedRows.map(normalizeRiskRegisterRow);
        }
      }
    } catch (error) {
      // Use the sample rows when browser storage is unavailable or invalid.
    }

    return DEFAULT_RISK_REGISTER_ROWS.map(normalizeRiskRegisterRow);
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
      riskEvent: String(source.riskEvent || ""),
      mitigant: String(source.mitigant || ""),
      materiality,
      movement,
      riskOwner: String(source.riskOwner || "")
    };
  }

  function updateRiskRegisterControls() {
    const editButton = document.getElementById("riskRegisterEditButton");
    const addButton = document.getElementById("riskRegisterAddButton");

    if (editButton) {
      editButton.hidden = !isAdmin();
      editButton.innerHTML = riskRegisterEditing
        ? `<i class="fa-solid fa-floppy-disk"></i> Save`
        : `<i class="fa-solid fa-pen-to-square"></i> Edit`;
      editButton.setAttribute("aria-label", riskRegisterEditing ? "Save risk register" : "Edit risk register");
    }

    if (addButton) {
      addButton.hidden = !isAdmin() || !riskRegisterEditing;
    }
  }

  function renderOverallRisk(data) {
    const manualSummary = buildManualOverallSummary(data);
    const overall = manualSummary.overall;
    const gauge = document.getElementById("overallGauge");

    setText("overallRiskLabel", overall.rating.toUpperCase());

    if (gauge) {
      gauge.style.setProperty("--risk-angle", `${overall.gaugeAngle.toFixed(1)}deg`);
      gauge.dataset.rating = overall.rating.toLowerCase();
    }

    renderCategoryRiskRows(data, manualSummary.categories);
  }

  function renderCategoryRiskRows(data, manualCategories) {
    const container = document.getElementById("categoryRiskRows");

    if (!container) {
      return;
    }

    container.innerHTML = data.categoryOrder.map((categoryId) => {
      const summary = manualCategories[categoryId];
      const isOpen = openCategoryRiskId === categoryId;
      const optionButtons = !isAdmin() ? "" : RISK_RATINGS.map((rating) => {
        const normalizedRating = rating.toLowerCase();
        const isSelected = summary.rating === rating;

        return `
          <button
            class="risk-option ${normalizedRating}${isSelected ? " is-selected" : ""}"
            type="button"
            data-category-risk-option="${escapeHtml(categoryId)}"
            data-risk-rating="${escapeHtml(rating)}"
            aria-pressed="${isSelected ? "true" : "false"}"
          >
            ${escapeHtml(rating)}
          </button>
        `;
      }).join("");

      return `
        <div class="category-risk-control${isOpen ? " is-open" : ""}">
          <button
            class="category-row"
            type="button"
            data-category-risk-toggle="${escapeHtml(categoryId)}"
            aria-expanded="${isOpen ? "true" : "false"}"
          >
            <span>
            <span class="category-dot ${summary.dotClass}"></span>
            ${escapeHtml(summary.name)}
            </span>

            ${renderStatusBadge(summary.rating)}
          </button>

          <div class="risk-options">
            ${optionButtons}
          </div>
        </div>
      `;
    }).join("");
  }

  async function handleCategoryRiskControlClick(event) {
    const option = event.target.closest("[data-category-risk-option]");

    if (option) {
      if (!isAdmin()) {
        return;
      }

      const categoryId = option.dataset.categoryRiskOption;
      const rating = normalizeManualRating(option.dataset.riskRating);

      if (categoryId && rating) {
        categoryRiskOverrides[categoryId] = rating;

        if (serverModeAvailable) {
          try {
            await apiRequest(`/api/admin/risk-categories/${encodeURIComponent(categoryId)}`, {
              method: "PUT",
              body: JSON.stringify({ rating })
            });
          } catch (error) {
            setDataMessage(error.message || "Unable to save Risk by Category. Please try again.", true);
          }
        }

        openCategoryRiskId = "";
        rerenderOverallRiskOnly();
      }

      return;
    }

    const toggle = event.target.closest("[data-category-risk-toggle]");

    if (!toggle) {
      return;
    }

    if (!isAdmin()) {
      return;
    }

    const categoryId = toggle.dataset.categoryRiskToggle;
    openCategoryRiskId = openCategoryRiskId === categoryId ? "" : categoryId;
    rerenderOverallRiskOnly();
  }

  function rerenderOverallRiskOnly() {
    if (enrichedDashboardData) {
      renderOverallRisk(enrichedDashboardData);
    }
  }

  function buildManualOverallSummary(data) {
    const categories = {};
    const categoryItems = data.categoryOrder.map((categoryId) => {
      const calculatedSummary = data.riskSummary.categories[categoryId];
      const rating = categoryRiskOverrides[categoryId] || calculatedSummary.rating;
      const score = RATING_SCORES[rating] || calculatedSummary.score || RATING_SCORES.Moderate;
      const weight = Number(data.categories[categoryId].weight || 1);

      categories[categoryId] = {
        ...calculatedSummary,
        rating,
        score
      };

      return {
        score,
        weight
      };
    });
    const overallScore = weightedAverage(
      categoryItems,
      (item) => item.score,
      (item) => item.weight
    );

    return {
      categories,
      overall: {
        score: overallScore,
        rating: gaugeRatingFromScore(overallScore),
        gaugeAngle: gaugeAngle(overallScore)
      }
    };
  }

  function normalizeManualRating(value) {
    const normalized = String(value || "").toLowerCase();

    return RISK_RATINGS.find((rating) => rating.toLowerCase() === normalized) || "";
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

  function ratingFromScore(score) {
    if (score >= 2.34) {
      return "High";
    }

    if (score >= 1.67) {
      return "Moderate";
    }

    return "Low";
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

  function getDeltaClass(tone) {
    if (tone === "positive") {
      return "delta-positive";
    }

    if (tone === "negative") {
      return "delta-negative";
    }

    return "delta-neutral";
  }

  function setLoading(isLoading) {
    const refreshButton = document.getElementById("refreshDataButton");

    if (refreshButton) {
      refreshButton.disabled = isLoading;
      refreshButton.classList.toggle("is-loading", isLoading);
    }
  }

  function setDataMessage(message, isError) {
    const messageEl = document.getElementById("dataLoadMessage");

    if (!messageEl) {
      return;
    }

    messageEl.textContent = message || "";
    messageEl.classList.toggle("error", Boolean(isError));
  }

  function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
      element.textContent = value;
    }
  }

  function formatDate(value) {
    const date = parseDate(value);

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

    const date = new Date(String(value).length === 10 ? `${value}T00:00:00` : value);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function titleCase(value) {
    return String(value || "")
      .replace(/[-_]+/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  global.OilRiskDashboard = {
    refreshData,
    renderDashboard,
    setDashboardData(data) {
      activeDashboardData = global.OilRiskData.cloneDashboardData(data);
      renderDashboard(activeDashboardData);
    },
    getData() {
      return global.OilRiskData.cloneDashboardData(enrichedDashboardData || activeDashboardData);
    }
  };
})(window);
