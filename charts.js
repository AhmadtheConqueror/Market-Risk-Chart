// ============================================================
// CHARTS AND SPARKLINES
// Chart.js setup plus small inline SVG sparklines.
// ============================================================

(function registerOilRiskCharts(global) {
  "use strict";

  const chartInstances = {};
  const CORE_EXPORT_START_DATE = "2026-01-01";
  const CORE_EXPORT_RANGE_MONTHS = {
    "1M": 1,
    "3M": 3,
    "6M": 6,
    "9M": 9
  };
  const BBL_PER_MT = {
    // Product-specific bbl/MT factors from standard industry density approximations.
    // Replace here if a workbook-supplied CI.Results_UOM conversion becomes available.
    PAAAM00: 8.9,  // Naphtha
    AAVJI00: 7.45, // Gasoil
    PGABM00: 8.53, // Gasoline
    PJAAV00: 7.88  // Jet
  };
  const DAY_IN_MILLISECONDS = 24 * 60 * 60 * 1000;
  let coreExportRows = [];
  let coreExportRange = "6M";
  let coreExportControlsBound = false;
  let crudeSupplyRiskChart = null;

  function configureDefaults() {
    if (!global.Chart) {
      return;
    }

    global.Chart.defaults.font.family = "Arial, Helvetica, sans-serif";
    global.Chart.defaults.color = "#252B72";

    if (global.ChartZoom && global.Chart.register) {
      try {
        global.Chart.register(global.ChartZoom);
      } catch (error) {
        // The plugin may already be registered by the CDN bundle.
      }
    }
  }

  function valuesFromHistory(kri) {
    return observationsFromHistory(kri.history)
      .map((point) => point.value);
  }

  function labelsFromHistory(kri) {
    return observationsFromHistory(kri.history)
      .map((point) => formatDateLabel(point.date));
  }

  function observationsFromHistory(historyPoints) {
    return (historyPoints || [])
      .map((point) => ({
        date: point.date || "",
        value: numericHistoryValue(point)
      }))
      .filter((point) => point.date && Number.isFinite(point.value))
      .sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
  }

  function numericHistoryValue(point) {
    const rawValue = point && typeof point === "object" ? point.value : point;

    if (rawValue === "" || rawValue === null || rawValue === undefined) {
      return NaN;
    }

    if (typeof rawValue === "string" && rawValue.trim() === "") {
      return NaN;
    }

    const value = Number(rawValue);
    return Number.isFinite(value) ? value : NaN;
  }

  function rollingCalendarWindow(observations, days) {
    if (!days || !observations.length) {
      return observations;
    }

    const latest = observations[observations.length - 1];
    const latestDate = new Date(`${latest.date}T00:00:00`);

    if (Number.isNaN(latestDate.getTime())) {
      return observations;
    }

    const startDate = new Date(latestDate);
    startDate.setDate(startDate.getDate() - (days - 1));

    return observations.filter((point) => {
      const pointDate = new Date(`${point.date}T00:00:00`);
      return pointDate >= startDate && pointDate <= latestDate;
    });
  }

  function formatDateLabel(dateValue) {
    if (!dateValue) {
      return "";
    }

    const date = new Date(`${dateValue}T00:00:00`);

    if (Number.isNaN(date.getTime())) {
      return String(dateValue);
    }

    return date.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short"
    });
  }

  function formatTooltipDate(dateValue) {
    if (!dateValue) {
      return "";
    }

    const date = new Date(`${dateValue}T00:00:00Z`);

    if (Number.isNaN(date.getTime())) {
      return String(dateValue);
    }

    const months = [
      "Jan",
      "Feb",
      "Mar",
      "Apr",
      "May",
      "Jun",
      "Jul",
      "Aug",
      "Sep",
      "Oct",
      "Nov",
      "Dec"
    ];
    const day = String(date.getUTCDate()).padStart(2, "0");
    const month = months[date.getUTCMonth()];
    const year = date.getUTCFullYear();

    return `${day} ${month} ${year}`;
  }

  function destroyChart(canvasId) {
    if (chartInstances[canvasId]) {
      chartInstances[canvasId].destroy();
      delete chartInstances[canvasId];
    }

    if (canvasId === "geoChart") {
      crudeSupplyRiskChart = null;
    }
  }

  function createSparkline(historyPoints, tone, options) {
    const settings = options || {};
    const observations = rollingCalendarWindow(
      observationsFromHistory(historyPoints),
      settings.days
    );
    const values = observations.map((point) => point.value);

    if (values.length < 2) {
      return `<span class="sparkline-empty">--</span>`;
    }

    const width = 75;
    const height = 27;
    const padding = 2;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;

    const pointCoordinates = values.map((value, index) => {
      const x = padding + (index / (values.length - 1)) * (width - padding * 2);
      const y = height - padding - ((value - min) / range) * (height - padding * 2);
      return {
        x,
        y,
        observation: observations[index]
      };
    });
    const points = pointCoordinates
      .map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`)
      .join(" ");

    const toneClass = tone === "negative"
      ? "sparkline-negative"
      : tone === "positive"
        ? "sparkline-positive"
        : "sparkline-neutral";
    const sparklineClass = `sparkline ${toneClass}${settings.wide ? " sparkline-wide" : ""}`;

    const sparklineSvg = `
      <svg
        class="${sparklineClass}"
        viewBox="0 0 ${width} ${height}"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <polyline points="${points}"></polyline>
      </svg>
    `;

    if (!settings.interactiveTooltip) {
      return sparklineSvg;
    }

    const pointButtons = pointCoordinates.map((point) => {
      const tooltip = sparklineTooltipText(point.observation, settings);
      const left = (point.x / width) * 100;
      const top = (point.y / height) * 100;

      return `
        <button
          class="sparkline-point"
          type="button"
          style="left: ${left.toFixed(2)}%; top: ${top.toFixed(2)}%;"
          data-tooltip="${escapeAttribute(tooltip)}"
          aria-label="${escapeAttribute(tooltip)}"
        ></button>
      `;
    }).join("");

    return `
      <div class="sparkline-interactive">
        ${sparklineSvg}
        ${pointButtons}
      </div>
    `;
  }

  function sparklineTooltipText(point, settings) {
    return [
      settings.tooltipTitle || "30D Trend",
      formatTooltipDate(point.date),
      formatSparklineValue(point.value, settings)
    ].join("\n");
  }

  function formatSparklineValue(value, settings) {
    const unit = settings.commodityUnit || settings.unit || "";

    if (
      settings.commodityCurrency ||
      settings.commodityUnit ||
      /usd|bbl|barrel|mt|metric|tonne/i.test(unit)
    ) {
      return global.OilRiskEngine.formatCommodityValue(
        value,
        settings.commodityCurrency,
        unit
      );
    }

    const formatted = Number(value).toLocaleString("en-US", {
      maximumFractionDigits: 2
    });

    return unit ? `${formatted} ${unit}` : formatted;
  }

  function escapeSvgText(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function escapeAttribute(value) {
    return escapeSvgText(value)
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function average(values) {
    if (!values.length) {
      return 0;
    }

    return values.reduce((sum, value) => sum + value, 0) / values.length;
  }

  function averageValidValues(values) {
    const valid = values
      .filter((value) => (
        value !== null &&
        value !== undefined &&
        String(value).trim() !== "" &&
        Number.isFinite(Number(value))
      ))
      .map(Number);

    if (!valid.length) {
      return null;
    }

    return valid.reduce((sum, value) => sum + value, 0) / valid.length;
  }

  function recentAverage(kri, count) {
    const values = valuesFromHistory(kri);

    if (values.length <= 1) {
      return Number(kri.currentValue) || 0;
    }

    const historicalWindow = values.slice(Math.max(0, values.length - count - 1), -1);
    return average(historicalWindow);
  }

  function renderBrentChart(data) {
    const kri = data.kris.MR_BRENT;
    const brentHistory = Array.isArray(data.plattsBrentHistory) && data.plattsBrentHistory.length
      ? data.plattsBrentHistory
      : kri.history;
    const history = monthlyAverageHistory(
      yearToDateHistory(observationsFromHistory(brentHistory))
    );

    renderLineChart({
      canvasId: "brentChart",
      kri,
      history,
      yearToDate: true,
      monthlyAverage: true,
      datasetLabel: "Dated Brent",
      commodityTooltip: true,
      commodityCurrency: kri.commodityCurrency,
      commodityUnit: kri.commodityUnit || kri.unit,
      borderColor: "#34398A",
      backgroundColor: "rgba(52,57,138,0.12)",
      yPadding: 4
    });
  }

  function yearToDateHistory(observations) {
    if (!observations.length) {
      return observations;
    }

    const latestDate = observations[observations.length - 1].date;
    const latestYear = String(latestDate).slice(0, 4);
    const startDate = `${latestYear}-01-01`;

    return observations.filter((point) => (
      point.date >= startDate && point.date <= latestDate
    ));
  }

  function monthlyAverageHistory(observations) {
    const monthlyGroups = new Map();

    observations.forEach((observation) => {
      const monthKey = String(observation.date).slice(0, 7);
      const group = monthlyGroups.get(monthKey) || {
        date: observation.date,
        monthKey,
        values: []
      };

      group.date = observation.date;
      group.values.push(observation.value);
      monthlyGroups.set(monthKey, group);
    });

    return Array.from(monthlyGroups.values()).map((group) => {
      const averageValue = averageValidValues(group.values);

      if (averageValue === null) {
        return null;
      }

      const monthDate = new Date(`${group.monthKey}-01T00:00:00Z`);

      return {
        date: group.date,
        value: averageValue,
        monthLabel: monthDate.toLocaleDateString("en-US", {
          month: "short",
          timeZone: "UTC"
        }),
        monthTitle: monthDate.toLocaleDateString("en-US", {
          month: "long",
          year: "numeric",
          timeZone: "UTC"
        })
      };
    }).filter(Boolean);
  }

  function renderCoreExportChart(data) {
    bindCoreExportControls();
    coreExportRows = getCoreExportRows(data);
    renderCoreExportChartRange();
  }

  function getCoreExportRows(data) {
    if (Array.isArray(data.coreExportData)) {
      return data.coreExportData
        .map(normalizeCoreExportRow)
        .filter(Boolean);
    }

    return buildDemoCoreExportRows(data);
  }

  function normalizeCoreExportRow(row) {
    const date = String(row && row.date || "").slice(0, 10);
    const dateTime = Date.parse(`${date}T00:00:00Z`);
    const crudeSupplyRisk = numericOrNull(row && row.crudeSupplyRisk);
    const datedBrent = numericOrNull(row && row.datedBrent);

    if (
      !/^\d{4}-\d{2}-\d{2}$/.test(date) ||
      !Number.isFinite(dateTime) ||
      date < CORE_EXPORT_START_DATE ||
      (crudeSupplyRisk === null && datedBrent === null)
    ) {
      return null;
    }

    return {
      date,
      crudeSupplyRisk,
      datedBrent
    };
  }

  function numericOrNull(value) {
    if (value === "" || value === null || value === undefined) {
      return null;
    }

    const numericValue = Number(value);
    return Number.isFinite(numericValue) ? numericValue : null;
  }

  function buildDemoCoreExportRows(data) {
    const brentObservations = observationsFromHistory(data.kris.MR_BRENT.history);
    const riskObservations = observationsFromHistory(data.kris.MG_GEO_TENSION.history);
    const riskByDate = new Map(riskObservations.map((point) => [point.date, point.value]));

    return brentObservations.map((point) => {
      const riskValue = riskByDate.get(point.date);

      return {
        date: point.date,
        datedBrent: point.value,
        crudeSupplyRisk: Number.isFinite(riskValue)
          ? Number(((riskValue - 50) / 1000).toFixed(3))
          : null
      };
    });
  }

  function renderCoreExportChartRange() {
    const canvas = document.getElementById("geoChart");

    if (!canvas) {
      return;
    }

    updateCoreExportRangeButtons();
    destroyChart("geoChart");

    const range = getCoreExportRange(coreExportRows, coreExportRange);

    if (!range.rows.length || !global.Chart) {
      return;
    }

    const chartRows = range.rows;
    const xMin = dateToTimestamp(range.startDate);
    const latestTimestamp = dateToTimestamp(range.latestDate);
    const xMax = Math.max(latestTimestamp, xMin + DAY_IN_MILLISECONDS);
    const datedBrentPoints = chartRows.map((row) => ({
      x: dateToTimestamp(row.date),
      y: row.datedBrent
    }));
    const crudeSupplyRiskPoints = chartRows
      .filter((row) => Number.isFinite(row.crudeSupplyRisk))
      .map((row) => ({
        x: dateToTimestamp(row.date),
        y: row.crudeSupplyRisk
      }));

    crudeSupplyRiskChart = new global.Chart(canvas, {
      type: "line",
      data: {
        datasets: [
          {
            label: "Dated Brent \u2014 PCAAS00 \u2014 Left axis ($/bbl)",
            data: datedBrentPoints,
            yAxisID: "y",
            borderColor: "#F9A51A",
            backgroundColor: "#F9A51A",
            borderWidth: 2.5,
            pointRadius: 1.5,
            pointHoverRadius: 4,
            fill: false,
            spanGaps: false,
            tension: 0.2
          },
          {
            label: "Crude Supply Risk \u2014 ZNR734 \u2014 Right axis",
            data: crudeSupplyRiskPoints,
            yAxisID: "y1",
            borderColor: "#61A7DF",
            backgroundColor: "rgba(97,167,223,0.24)",
            borderWidth: 2.5,
            pointRadius: 1.5,
            pointHoverRadius: 4,
            fill: "origin",
            spanGaps: false,
            tension: 0.2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 350
        },
        interaction: {
          mode: "index",
          intersect: false
        },
        plugins: {
          legend: {
            display: true,
            position: "top",
            align: "start",
            labels: {
              color: "#e8edf2",
              boxWidth: 10,
              boxHeight: 10,
              padding: 10,
              font: {
                size: 9
              }
            }
          },
          tooltip: {
            mode: "index",
            intersect: false,
            callbacks: {
              title(items) {
                const item = items[0];
                return item ? formatCoreExportDate(item.parsed.x) : "";
              },
              label(context) {
                if (context.datasetIndex === 0) {
                  if (!Number.isFinite(context.parsed.y)) {
                    return "Dated Brent: No value reported";
                  }

                  return `Dated Brent: ${global.OilRiskEngine.formatCommodityValue(
                    context.parsed.y,
                    "USD",
                    "BBL"
                  )}`;
                }

                if (!Number.isFinite(context.parsed.y)) {
                  return "Crude Supply Risk: No value reported";
                }

                return `Crude Supply Risk: ${formatCrudeSupplyRisk(context.parsed.y)}`;
              }
            }
          },
          zoom: {
            limits: {
              x: {
                min: xMin,
                max: xMax,
                minRange: DAY_IN_MILLISECONDS
              },
              y: {
                min: "original",
                max: "original"
              },
              y1: {
                min: "original",
                max: "original"
              }
            },
            pan: {
              enabled: true,
              mode: "x"
            },
            zoom: {
              mode: "x",
              wheel: {
                enabled: true
              },
              pinch: {
                enabled: true
              },
              drag: {
                enabled: false
              }
            }
          }
        },
        scales: {
          x: {
            type: "linear",
            min: xMin,
            max: xMax,
            grid: {
              color: "rgba(220,230,238,0.10)"
            },
            ticks: {
              maxTicksLimit: 8,
              color: "#bfcbd5",
              font: {
                size: 9
              },
              callback(value) {
                return formatCoreExportDate(value);
              }
            }
          },
          y: {
            position: "left",
            grid: {
              color: "rgba(220,230,238,0.10)"
            },
            ticks: {
              color: "#F9A51A",
              font: {
                size: 9
              },
              callback(value) {
                return `$${Number(value).toFixed(0)}`;
              }
            },
            title: {
              display: true,
              text: "USD/bbl",
              color: "#F9A51A",
              font: {
                size: 9
              }
            }
          },
          y1: {
            position: "right",
            grid: {
              drawOnChartArea: false
            },
            ticks: {
              color: "#61A7DF",
              font: {
                size: 9
              },
              callback(value) {
                return formatCrudeSupplyRisk(value);
              }
            },
            title: {
              display: true,
              text: "ZNR734",
              color: "#61A7DF",
              font: {
                size: 9
              }
            }
          }
        }
      }
    });
    chartInstances.geoChart = crudeSupplyRiskChart;
  }

  function getCoreExportRange(rows, rangeName) {
    if (!rows.length) {
      return {
        rows: [],
        startDate: CORE_EXPORT_START_DATE,
        latestDate: CORE_EXPORT_START_DATE
      };
    }

    const latestDate = rows.reduce((latest, row) => (
      row.date > latest ? row.date : latest
    ), CORE_EXPORT_START_DATE);
    let startDate = CORE_EXPORT_START_DATE;
    const months = CORE_EXPORT_RANGE_MONTHS[rangeName];

    if (months) {
      const rangeStart = new Date(`${latestDate}T00:00:00Z`);
      rangeStart.setUTCMonth(rangeStart.getUTCMonth() - months);
      startDate = toIsoDate(rangeStart);
      startDate = startDate < CORE_EXPORT_START_DATE
        ? CORE_EXPORT_START_DATE
        : startDate;
    }

    return {
      rows: rows.filter((row) => row.date >= startDate && row.date <= latestDate),
      startDate,
      latestDate
    };
  }

  function dateToTimestamp(dateValue) {
    const parts = String(dateValue).slice(0, 10).split("-").map(Number);

    if (parts.length !== 3 || parts.some((part) => !Number.isInteger(part))) {
      return NaN;
    }

    return Date.UTC(parts[0], parts[1] - 1, parts[2]);
  }

  function toIsoDate(date) {
    return [
      String(date.getUTCFullYear()).padStart(4, "0"),
      String(date.getUTCMonth() + 1).padStart(2, "0"),
      String(date.getUTCDate()).padStart(2, "0")
    ].join("-");
  }

  function formatCoreExportDate(value) {
    const timestamp = typeof value === "number" ? value : dateToTimestamp(value);
    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
      return "";
    }

    return date.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      timeZone: "UTC"
    });
  }

  function formatCrudeSupplyRisk(value) {
    return Number(value).toLocaleString("en-US", {
      minimumFractionDigits: 3,
      maximumFractionDigits: 3
    });
  }

  function bindCoreExportControls() {
    if (coreExportControlsBound) {
      return;
    }

    const rangeControls = document.getElementById("coreExportRangeControls");
    const resetButton = document.getElementById("coreExportResetZoom");
    const fullscreenButton = document.getElementById("coreExportFullscreen");

    if (rangeControls && typeof rangeControls.addEventListener === "function") {
      rangeControls.addEventListener("click", (event) => {
        const button = event.target.closest("[data-core-export-range]");

        if (!button) {
          return;
        }

        coreExportRange = button.dataset.coreExportRange;
        renderCoreExportChartRange();
      });
    }

    if (resetButton && typeof resetButton.addEventListener === "function") {
      resetButton.addEventListener("click", resetCoreExportZoom);
    }

    if (fullscreenButton && typeof fullscreenButton.addEventListener === "function") {
      fullscreenButton.addEventListener("click", toggleCoreExportFullscreen);
    }

    updateFullscreenButton(
      document.fullscreenElement === document.getElementById("crudeSupplyRiskPanel")
    );

    if (typeof document.addEventListener === "function") {
      document.addEventListener("fullscreenchange", handleCoreExportFullscreenChange);
    }

    coreExportControlsBound = true;
  }

  function updateCoreExportRangeButtons() {
    const activeButton = document.querySelector(`[data-core-export-range="${coreExportRange}"]`);

    document.querySelectorAll("[data-core-export-range]").forEach((button) => {
      const isActive = button === activeButton;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
  }

  function resetCoreExportZoom() {
    const chart = crudeSupplyRiskChart;

    if (chart && typeof chart.resetZoom === "function") {
      chart.resetZoom();
    }
  }

  async function toggleCoreExportFullscreen() {
    const panel = document.getElementById("crudeSupplyRiskPanel");

    if (!panel) {
      return;
    }

    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else if (panel.requestFullscreen) {
        await panel.requestFullscreen();
      }
    } catch (error) {
      // Fullscreen can be denied by browser permissions or file context.
    }
  }

  function updateFullscreenButton(isFullscreen) {
    const button = document.getElementById("coreExportFullscreen");

    if (!button) {
      return;
    }

    const icon = button.querySelector("i");

    if (icon) {
      icon.className = isFullscreen
        ? "fa-solid fa-compress"
        : "fa-solid fa-expand";
    }

    button.title = isFullscreen ? "Restore chart" : "Maximize chart";
    button.setAttribute("aria-label", isFullscreen ? "Restore chart" : "Maximize chart");
  }

  function handleCoreExportFullscreenChange() {
    const isFullscreen = (
      document.fullscreenElement === document.getElementById("crudeSupplyRiskPanel")
    );

    updateFullscreenButton(isFullscreen);
    document.body.style.overflow = document.fullscreenElement ? "hidden" : "";

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (!isFullscreen) {
          resetCoreExportCanvasSizing();
          renderCoreExportChartRange();
        } else if (crudeSupplyRiskChart) {
          crudeSupplyRiskChart.resize();
        }
      });
    });
  }

  function resetCoreExportCanvasSizing() {
    const canvas = document.getElementById("geoChart");
    const container = document.querySelector("#crudeSupplyRiskPanel .crude-risk-chart-container");

    if (container) {
      container.style.removeProperty("height");
      container.style.removeProperty("min-height");
      container.style.removeProperty("flex");
    }

    if (canvas) {
      canvas.style.removeProperty("width");
      canvas.style.removeProperty("height");
      canvas.removeAttribute("width");
      canvas.removeAttribute("height");
    }
  }

  function renderLineChart(config) {
    if (!global.Chart || !config.kri) {
      return;
    }

    const canvas = document.getElementById(config.canvasId);

    if (!canvas) {
      return;
    }

    const observations = config.history || observationsFromHistory(config.kri.history);
    const values = observations.map((point) => point.value);
    const labels = observations.map((point) => (
      config.monthlyAverage ? point.monthLabel : formatDateLabel(point.date)
    ));

    if (values.length < 2) {
      destroyChart(config.canvasId);
      return;
    }

    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const yPadding = Number(config.yPadding || 0);
    const yMin = Number.isFinite(config.yMin)
      ? config.yMin
      : Math.floor(minValue - yPadding);
    const yMax = Number.isFinite(config.yMax)
      ? config.yMax
      : Math.ceil(maxValue + yPadding);

    destroyChart(config.canvasId);

    chartInstances[config.canvasId] = new global.Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: config.datasetLabel,
            data: values,
            borderColor: config.borderColor,
            backgroundColor: config.backgroundColor,
            borderWidth: 2.5,
            pointRadius: Number.isFinite(config.pointRadius) ? config.pointRadius : 3,
            pointHoverRadius: 5,
            fill: true,
            tension: 0.25
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 350
        },
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            callbacks: {
              title(items) {
                if (!items.length) {
                  return "";
                }

                const observation = observations[items[0].dataIndex];

                if (config.monthlyAverage) {
                  return observation ? observation.monthTitle : "";
                }

                if (!config.commodityTooltip) {
                  return items.length ? items[0].label : "";
                }

                return formatTooltipDate(observation && observation.date);
              },
              label(context) {
                if (config.monthlyAverage) {
                  return `Average Dated Brent: ${global.OilRiskEngine.formatCommodityValue(
                    context.raw,
                    config.commodityCurrency,
                    config.commodityUnit
                  )}`;
                }

                if (config.commodityTooltip) {
                  return global.OilRiskEngine.formatCommodityValue(
                    context.raw,
                    config.commodityCurrency,
                    config.commodityUnit
                  );
                }

                const valueText = global.OilRiskEngine.formatValue(config.kri, context.raw);
                return `${config.datasetLabel}: ${valueText}${config.tooltipSuffix || ""}`;
              }
            }
          }
        },
        scales: {
          x: {
            grid: {
              display: false
            },
            ticks: {
              autoSkip: !config.yearToDate,
              maxTicksLimit: config.yearToDate ? 12 : 7,
              callback(value, index) {
                if (config.monthlyAverage) {
                  return labels[index] || "";
                }

                if (!config.yearToDate) {
                  return this.getLabelForValue(value);
                }

                const observation = observations[index];
                const previousObservation = observations[index - 1];

                if (
                  !observation ||
                  !previousObservation ||
                  observation.date.slice(0, 7) !== previousObservation.date.slice(0, 7)
                ) {
                  return observation ? formatDateLabel(observation.date) : "";
                }

                return index === 0 ? formatDateLabel(observation.date) : "";
              },
              font: {
                size: 9
              }
            }
          },
          y: {
            min: yMin,
            max: yMax,
            ticks: {
              font: {
                size: 9
              }
            },
            grid: {
              color: "rgba(52,57,138,0.10)"
            }
          }
        }
      }
    });
  }

  function renderProductPriceChart(data) {
    if (!global.Chart) {
      return;
    }

    const canvas = document.getElementById("crackChart");

    if (!canvas) {
      return;
    }

    const productOrder = ["naphtha", "gasoil", "gasoline", "jet"];
    const brentHistory = Array.isArray(data.plattsBrentHistory) && data.plattsBrentHistory.length
      ? data.plattsBrentHistory
      : data.kris.MR_BRENT && data.kris.MR_BRENT.history;
    const brent = latestValidObservation(brentHistory);
    const brentPrice = brent ? brent.value : NaN;
    const products = productOrder
      .map((key) => data.marketProductPrices && data.marketProductPrices[key])
      .filter(Boolean)
      .map((product) => productBrentComparison(product, brentPrice))
      .filter((product) => product);

    const labels = products.map((product) => product.label);
    const convertedValues = products.map((product) => (
      Number.isFinite(product.convertedPrice) ? product.convertedPrice : null
    ));
    const referenceValues = products.map(() => (
      Number.isFinite(brentPrice) ? brentPrice : null
    ));
    const numericValues = [
      ...convertedValues.filter(Number.isFinite),
      ...referenceValues.filter(Number.isFinite)
    ];
    const maxValue = Math.max(...numericValues, 10);

    destroyChart("crackChart");

    chartInstances.crackChart = new global.Chart(canvas, {
      type: "bar",
      plugins: [productSpreadLabelPlugin()],
      data: {
        labels,
        datasets: [
          {
            label: "Product $/bbl",
            data: convertedValues,
            backgroundColor: "#34398A",
            borderRadius: 2
          },
          {
            type: "line",
            label: "Dated Brent",
            data: referenceValues,
            borderColor: "#FFC425",
            backgroundColor: "#FFC425",
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 3,
            borderDash: [6, 4],
            fill: false,
            tension: 0
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 350
        },
        plugins: {
          legend: {
            position: "top",
            align: "end",
            labels: {
              boxWidth: 8,
              boxHeight: 8,
              font: {
                size: 9
              }
            }
          },
          tooltip: {
            callbacks: {
              title(items) {
                const product = products[items[0] && items[0].dataIndex];
                return product ? product.label : "";
              },
              label(context) {
                const product = products[context.dataIndex];

                if (!product) {
                  return "";
                }

                if (context.datasetIndex === 1) {
                  return `Dated Brent: ${formatUsdPerBbl(product.brentPrice)}`;
                }

                if (!product.isComparable) {
                  return [
                    "Conversion unavailable",
                    `Original price: ${formatOriginalProductPrice(product)}`
                  ];
                }

                const conversionLine = Number.isFinite(product.barrelsPerMT)
                  ? `Conversion: ${product.barrelsPerMT.toFixed(4)} bbl/mt`
                  : "Conversion: workbook USD/bbl value";

                return [
                  `Assessment date: ${formatTooltipDate(product.date)}`,
                  `Original price: ${formatOriginalProductPrice(product)}`,
                  conversionLine,
                  `Converted price: ${formatUsdPerBbl(product.convertedPrice)}`,
                  `Dated Brent: ${formatUsdPerBbl(product.brentPrice)}`,
                  `Difference: ${formatSignedUsdPerBbl(product.difference)}`
                ];
              }
            }
          },
          productSpreadLabels: {
            products
          }
        },
        scales: {
          x: {
            grid: {
              display: false
            },
            ticks: {
              font: {
                size: 9
              }
            }
          },
          y: {
            beginAtZero: true,
            max: Math.ceil((maxValue + 8) / 5) * 5,
            ticks: {
              maxTicksLimit: 6,
              font: {
                size: 9
              },
              callback: (value) => `$${Number(value).toFixed(0)}`
            },
            grid: {
              color: "rgba(52,57,138,0.10)"
            }
          }
        }
      }
    });
  }

  function latestValidObservation(history) {
    const observations = observationsFromHistory(history);
    return observations[observations.length - 1] || null;
  }

  function latestConversionObservation(history, targetDate) {
    const observations = (history || [])
      .map((point) => ({
        date: point.date || "",
        convertedValue: numericOptionalValue(point.convertedValue),
        barrelsPerMT: numericOptionalValue(point.barrelsPerMT)
      }))
      .filter((point) => (
        point.date &&
        (Number.isFinite(point.convertedValue) || Number.isFinite(point.barrelsPerMT))
      ))
      .sort((a, b) => Date.parse(a.date) - Date.parse(b.date));

    if (!observations.length) {
      return null;
    }

    if (targetDate) {
      const exactMatch = observations.find((point) => point.date === targetDate);

      if (exactMatch) {
        return exactMatch;
      }

      const earlierMatches = observations.filter((point) => (
        Date.parse(point.date) <= Date.parse(targetDate)
      ));

      if (earlierMatches.length) {
        return earlierMatches[earlierMatches.length - 1];
      }
    }

    return observations[observations.length - 1];
  }

  function numericOptionalValue(value) {
    if (value === null || value === undefined || value === "") {
      return NaN;
    }

    const numericValue = Number(value);
    return Number.isFinite(numericValue) ? numericValue : NaN;
  }

  function productBrentComparison(product, brentPrice) {
    const latest = latestValidObservation(product.history);
    const symbol = product.code || "";
    const conversion = latestConversionObservation(product.conversionHistory, latest && latest.date);
    const workbookFactor = conversion ? conversion.barrelsPerMT : NaN;
    const configuredFactor = numericOptionalValue(product.conversionFactor);
    const barrelsPerMT = Number.isFinite(workbookFactor) && workbookFactor > 0
      ? workbookFactor
      : Number.isFinite(configuredFactor) && configuredFactor > 0
        ? configuredFactor
        : BBL_PER_MT[symbol];
    const originalPrice = latest ? latest.value : NaN;
    const workbookConvertedPrice = conversion ? conversion.convertedValue : NaN;
    const fallbackConvertedPrice = (
      Number.isFinite(originalPrice) &&
      Number.isFinite(barrelsPerMT) &&
      barrelsPerMT > 0
    )
      ? originalPrice / barrelsPerMT
      : NaN;
    const convertedPrice = Number.isFinite(workbookConvertedPrice)
      ? workbookConvertedPrice
      : fallbackConvertedPrice;
    const isComparable = Number.isFinite(convertedPrice) && Number.isFinite(brentPrice);
    const difference = isComparable ? convertedPrice - brentPrice : NaN;

    return {
      symbol,
      label: product.shortName || product.name,
      name: product.name,
      date: conversion && conversion.date ? conversion.date : latest ? latest.date : "",
      originalPrice,
      originalUnit: product.unit || "USD/MT",
      barrelsPerMT,
      convertedPrice,
      convertedUnit: "USD/BBL",
      brentPrice,
      difference,
      isComparable
    };
  }

  function productSpreadLabelPlugin() {
    return {
      id: "productSpreadLabels",
      afterDatasetsDraw(chart, _args, options) {
        const ctx = chart.ctx;
        const meta = chart.getDatasetMeta(0);
        const products = options.products || [];

        ctx.save();
        ctx.textAlign = "center";
        ctx.textBaseline = "bottom";
        ctx.font = "700 10px Arial, Helvetica, sans-serif";

        meta.data.forEach((bar, index) => {
          const product = products[index];

          if (!product || !product.isComparable || !bar) {
            return;
          }

          const position = bar.tooltipPosition();
          const label = formatSignedUsdPerBbl(product.difference);
          const y = Math.max(position.y - 8, 12);

          ctx.fillStyle = product.difference < 0 ? "#E84B32" : "#9b5c00";
          ctx.fillText(label, position.x, y);
        });

        ctx.restore();
      }
    };
  }

  function formatUsdPerBbl(value) {
    return global.OilRiskEngine.formatCommodityValue(value, "USD", "BBL");
  }

  function formatOriginalProductPrice(product) {
    return global.OilRiskEngine.formatCommodityValue(
      product.originalPrice,
      "USD",
      "MT"
    );
  }

  function formatSignedUsdPerBbl(value) {
    if (!Number.isFinite(value)) {
      return "Conversion unavailable";
    }

    const prefix = value >= 0 ? "+" : "-";
    return `${prefix}${formatUsdPerBbl(Math.abs(value))}`;
  }

  function renderAll(data) {
    configureDefaults();
    renderBrentChart(data);
    renderProductPriceChart(data);
    renderCoreExportChart(data);
  }

  function resizeChartsForPrint() {
    Object.values(chartInstances).forEach((chart) => {
      if (chart && typeof chart.resize === "function") {
        chart.resize();
      }
    });
  }

  if (typeof global.addEventListener === "function") {
    global.addEventListener("beforeprint", resizeChartsForPrint);
    global.addEventListener("afterprint", resizeChartsForPrint);
  }

  global.OilRiskCharts = {
    configureDefaults,
    createSparkline,
    renderAll
  };
})(window);
