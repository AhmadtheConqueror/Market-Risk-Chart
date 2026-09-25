// ============================================================
// EXCEL IMPORT UI STATE
// Pure state/summary helpers for the Admin workbook workflow.
// ============================================================

(function registerExcelImportUiService(global) {
  "use strict";

  const STAGES = [
    "Uploading workbook...",
    "Validating market observations...",
    "Updating market data..."
  ];

  function loadingState(fileName, activeStage) {
    return {
      status: "loading",
      fileName: String(fileName || "Selected workbook"),
      buttonDisabled: true,
      activeStage: activeStage || 0,
      stages: STAGES.slice()
    };
  }

  function successState(fileName, summary) {
    return {
      status: "success",
      fileName: String(fileName || "Selected workbook"),
      buttonDisabled: false,
      canRetry: false,
      refreshSnapshot: true,
      summary: normalizeSummary(summary)
    };
  }

  function failureState(fileName, error) {
    return {
      status: "failure",
      fileName: String(fileName || "Selected workbook"),
      buttonDisabled: false,
      canRetry: true,
      refreshSnapshot: false,
      message: classifyError(error)
    };
  }

  function normalizeSummary(summary) {
    const value = summary || {};
    const instruments = Array.isArray(value.instruments_affected)
      ? value.instruments_affected
        .filter(Boolean)
        .map((instrument) => String(instrument))
      : [];
    const dateRange = value.date_range || {};

    return {
      rowsRead: finiteCount(value.rows_read),
      rowsValid: finiteCount(value.rows_valid),
      rowsStored: finiteCount(value.rows_stored),
      rowsUpdated: finiteCount(value.rows_updated),
      rowsRejected: finiteCount(value.rows_rejected),
      instruments,
      dateFrom: dateRange.from || null,
      dateTo: dateRange.to || null
    };
  }

  function finiteCount(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : 0;
  }

  function classifyError(error) {
    const status = Number(error && error.status);
    const code = String(error && error.code || "").toUpperCase();
    const detail = sanitizeMessage(error && error.message);

    if (code === "TIMEOUT") {
      return "The upload timed out before the workbook could be processed. Please try again.";
    }

    if (code === "NETWORK_ERROR") {
      return "The dashboard could not reach the import service. Check the connection and try again.";
    }

    if (status === 400) {
      return detail || "The workbook was rejected. Check that it is a valid .xlsx file.";
    }

    if (status === 422) {
      return detail || "The upload request was invalid. Select a workbook and try again.";
    }

    if (status >= 500) {
      return "The server could not process the workbook right now. Please try again.";
    }

    return detail || "The workbook could not be imported. Please try again.";
  }

  function sanitizeMessage(value) {
    return String(value || "")
      .replace(/\s+/g, " ")
      .replace(/(?:api[_ -]?key|password|secret|token)\s*[:=]\s*[^ ]+/gi, "[redacted]")
      .slice(0, 240)
      .trim();
  }

  global.OilRiskExcelImportUi = {
    classifyError,
    failureState,
    loadingState,
    normalizeSummary,
    successState
  };
})(typeof window !== "undefined" ? window : globalThis);
