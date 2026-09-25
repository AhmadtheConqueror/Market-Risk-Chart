// ============================================================
// STATIC CHARTS AND SPARKLINES
// Local canvas/SVG rendering. No CDN or server dependency.
// ============================================================

(function registerOilRiskCharts(global) {
  "use strict";

  let lastRenderedData = null;
  let tooltip = null;

  function configureDefaults() {
    ensureTooltip();
  }

  function renderAll(data) {
    configureDefaults();
    lastRenderedData = data;
    renderProductPriceChart(data);
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

    const width = 120;
    const height = 32;
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
    const sparklineSvg = `
      <svg
        class="sparkline ${toneClass}"
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
      const tooltipText = sparklineTooltipText(point.observation, settings);
      const left = (point.x / width) * 100;
      const top = (point.y / height) * 100;

      return `
        <button
          class="sparkline-point"
          type="button"
          style="left:${left.toFixed(2)}%;top:${top.toFixed(2)}%;"
          data-tooltip="${escapeAttribute(tooltipText)}"
          aria-label="${escapeAttribute(tooltipText)}"
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

  function observationsFromHistory(historyPoints) {
    return (historyPoints || [])
      .map((point) => ({
        date: point && (point.date || point.assessmentDate)
          ? String(point.date || point.assessmentDate).slice(0, 10)
          : "",
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

    const value = Number(rawValue);
    return Number.isFinite(value) ? value : NaN;
  }

  function rollingCalendarWindow(observations, days) {
    if (!days || !observations.length) {
      return observations;
    }

    const latest = observations[observations.length - 1];
    const latestDate = parseUtcDate(latest.date);

    if (!latestDate) {
      return observations;
    }

    const startDate = new Date(latestDate);
    startDate.setUTCDate(startDate.getUTCDate() - days);

    return observations.filter((point) => {
      const pointDate = parseUtcDate(point.date);
      return pointDate && pointDate >= startDate && pointDate <= latestDate;
    });
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
        settings.commodityCurrency || "USD",
        unit
      );
    }

    const formatted = Number(value).toLocaleString("en-US", {
      maximumFractionDigits: 2
    });

    return unit ? `${formatted} ${unit}` : formatted;
  }

  function renderProductPriceChart(data) {
    const canvas = document.getElementById("crackChart");

    if (!canvas || !data) {
      return;
    }

    let products = [];
    if (data.backendSnapshot && Array.isArray(data.backendSnapshot.product_spreads)) {
      products = data.backendSnapshot.product_spreads.map((item) => ({
        instrumentId: item.instrument_id,
        symbol: item.instrument_id.toUpperCase(),
        label: item.display_name,
        name: item.display_name,
        date: item.date,
        originalPrice: item.original_price,
        originalUnit: item.original_unit,
        barrelsPerMT: item.barrels_per_mt,
        convertedPrice: item.converted_price,
        brentPrice: item.brent_price,
        difference: item.spread,
        isComparable: item.is_comparable
      }));
    } else if (Array.isArray(data.marketObservations) && data.marketObservations.length) {
      products = global.OilRiskMarketCalculations.calculateProductSpreads(
        data.marketObservations
      );
    }

    const validProducts = products.filter((product) =>
      Number.isFinite(product.convertedPrice) && product.convertedPrice > 0 && Number.isFinite(product.brentPrice)
    );

    drawSpreadChart(canvas, validProducts);
  }

  function drawSpreadChart(canvas, products) {
    const context = setupCanvas(canvas);

    if (!context) {
      return;
    }

    const ctx = context.ctx;
    const width = context.width;
    const height = context.height;
    const margin = {
      top: 28,
      right: 26,
      bottom: 58,
      left: 58
    };
    const area = chartArea(width, height, margin);
    const numericValues = products.flatMap((product) => [
      product.convertedPrice,
      product.brentPrice
    ]).filter(Number.isFinite);

    clearCanvas(ctx, width, height);

    if (!products.length || !numericValues.length) {
      drawEmptyChart(ctx, width, height, "No refined product observations loaded");
      return;
    }

    const yMin = 0;
    const yMax = Math.ceil((Math.max(...numericValues) + 10) / 10) * 10;
    const yForValue = scaleY(yMin, yMax, area);
    const slotWidth = area.width / products.length;
    const barWidth = Math.min(72, slotWidth * 0.42);
    const brentLineY = yForValue(products.find((product) => Number.isFinite(product.brentPrice))?.brentPrice || 0);
    const hitBoxes = [];

    drawGrid(ctx, area, yMin, yMax, {
      color: "rgba(52,57,138,0.10)",
      textColor: "#5c6683",
      formatter: (value) => `$${Number(value).toFixed(0)}`
    });

    ctx.save();
    ctx.setLineDash([7, 5]);
    ctx.strokeStyle = "#ffc425";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(area.left, brentLineY);
    ctx.lineTo(area.right, brentLineY);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#6c5a10";
    ctx.font = "700 12px Segoe UI, Arial, sans-serif";
    const isApi = Boolean(global.OilRiskConfig && (global.OilRiskConfig.DATA_SOURCE_MODE === "api" || (typeof global.OilRiskConfig.isApiMode === "function" && global.OilRiskConfig.isApiMode())));
    const brentLineLabel = isApi ? "Brent Futures" : "Dated Brent";
    ctx.fillText(brentLineLabel, area.right - 92, Math.max(area.top + 13, brentLineY - 8));
    ctx.restore();

    products.forEach((product, index) => {
      const slotLeft = area.left + index * slotWidth;
      const centerX = slotLeft + slotWidth / 2;
      const value = product.convertedPrice;
      const label = product.label || "";

      if (Number.isFinite(value)) {
        const y = yForValue(value);
        const barHeight = area.bottom - y;
        const x = centerX - barWidth / 2;

        ctx.save();
        ctx.fillStyle = "#34398a";
        ctx.fillRect(x, y, barWidth, barHeight);
        ctx.fillStyle = product.difference < 0 ? "#e84b32" : "#925c00";
        ctx.font = "800 11px Segoe UI, Arial, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(formatSignedUsdPerBbl(product.difference), centerX, Math.max(14, y - 8));
        ctx.restore();

        hitBoxes.push({
          x,
          y,
          width: barWidth,
          height: barHeight,
          product
        });
      }

      ctx.save();
      ctx.fillStyle = "#5c6683";
      ctx.font = "700 11px Segoe UI, Arial, sans-serif";
      ctx.textAlign = "center";
      wrapCanvasLabel(ctx, label, centerX, area.bottom + 18, Math.min(100, slotWidth - 8), 12);
      ctx.restore();
    });

    bindBoxTooltip(canvas, hitBoxes, (box) => productTooltip(box.product));
  }

  function setupCanvas(canvas) {
    const rect = canvas.getBoundingClientRect();
    const cssWidth = Math.max(320, Math.floor(rect.width || canvas.parentElement?.clientWidth || 600));
    const cssHeight = Math.max(180, Math.floor(rect.height || canvas.parentElement?.clientHeight || 260));
    const ratio = global.devicePixelRatio || 1;

    canvas.width = Math.floor(cssWidth * ratio);
    canvas.height = Math.floor(cssHeight * ratio);
    canvas.style.width = `${cssWidth}px`;
    canvas.style.height = `${cssHeight}px`;

    const ctx = canvas.getContext("2d");

    if (!ctx) {
      return null;
    }

    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

    return {
      ctx,
      width: cssWidth,
      height: cssHeight
    };
  }

  function clearCanvas(ctx, width, height, color) {
    ctx.save();
    ctx.fillStyle = color || "#ffffff";
    ctx.fillRect(0, 0, width, height);
    ctx.restore();
  }

  function drawEmptyChart(ctx, width, height, text, color) {
    ctx.save();
    ctx.fillStyle = color || "#8993ac";
    ctx.font = "800 13px Segoe UI, Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, width / 2, height / 2);
    ctx.restore();
  }

  function chartArea(width, height, margin) {
    return {
      left: margin.left,
      top: margin.top,
      right: width - margin.right,
      bottom: height - margin.bottom,
      width: width - margin.left - margin.right,
      height: height - margin.top - margin.bottom
    };
  }

  function scaleY(min, max, area) {
    const span = max - min || 1;
    return (value) => area.bottom - ((value - min) / span) * area.height;
  }

  function drawGrid(ctx, area, min, max, options) {
    const ticks = niceTicks(min, max, 5);

    ctx.save();
    ctx.strokeStyle = options.color;
    ctx.fillStyle = options.textColor;
    ctx.font = "700 11px Segoe UI, Arial, sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";

    ticks.forEach((tick) => {
      const y = scaleY(min, max, area)(tick);
      ctx.beginPath();
      ctx.moveTo(area.left, y);
      ctx.lineTo(area.right, y);
      ctx.stroke();
      ctx.fillText(options.formatter ? options.formatter(tick) : String(tick), area.left - 8, y);
    });

    ctx.strokeStyle = "#d9dfec";
    ctx.beginPath();
    ctx.moveTo(area.left, area.top);
    ctx.lineTo(area.left, area.bottom);
    ctx.lineTo(area.right, area.bottom);
    ctx.stroke();
    ctx.restore();
  }

  function drawXAxisLabels(ctx, coordinates, options) {
    const step = Math.max(1, Math.ceil(coordinates.length / options.maxLabels));

    ctx.save();
    ctx.fillStyle = options.textColor;
    ctx.font = "700 11px Segoe UI, Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";

    coordinates.forEach((coordinate, index) => {
      if (index % step !== 0 && index !== coordinates.length - 1) {
        return;
      }

      const label = options.formatter ? options.formatter(coordinate.point) : coordinate.point.date;
      ctx.fillText(label, coordinate.x, options.area.bottom + 12);
    });

    ctx.restore();
  }

  function niceTicks(min, max, count) {
    const span = max - min || 1;
    const rawStep = span / Math.max(1, count - 1);
    const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
    const normalized = rawStep / magnitude;
    const step = normalized >= 5
      ? 5 * magnitude
      : normalized >= 2
        ? 2 * magnitude
        : magnitude;
    const first = Math.ceil(min / step) * step;
    const ticks = [];

    for (let value = first; value <= max + step * 0.5; value += step) {
      ticks.push(Number(value.toFixed(6)));
    }

    if (!ticks.length) {
      ticks.push(min, max);
    }

    return ticks.slice(0, count + 2);
  }

  function bindPointTooltip(canvas, coordinates, getText) {
    canvas.onmousemove = (event) => {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const nearest = coordinates
        .map((coordinate) => ({
          coordinate,
          distance: Math.hypot(coordinate.x - x, coordinate.y - y)
        }))
        .sort((a, b) => a.distance - b.distance)[0];

      if (!nearest || nearest.distance > 24) {
        hideTooltip();
        return;
      }

      showTooltip(event.clientX, event.clientY, getText(nearest.coordinate));
    };
    canvas.onmouseleave = hideTooltip;
  }

  function bindBoxTooltip(canvas, boxes, getText) {
    canvas.onmousemove = (event) => {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const hit = boxes.find((box) => (
        x >= box.x &&
        x <= box.x + box.width &&
        y >= box.y &&
        y <= box.y + box.height
      ));

      if (!hit) {
        hideTooltip();
        return;
      }

      showTooltip(event.clientX, event.clientY, getText(hit));
    };
    canvas.onmouseleave = hideTooltip;
  }

  function showTooltip(clientX, clientY, text) {
    const element = ensureTooltip();

    element.textContent = text;
    element.hidden = false;
    element.style.left = `${clientX + 14}px`;
    element.style.top = `${clientY + 14}px`;
  }

  function hideTooltip() {
    if (tooltip) {
      tooltip.hidden = true;
    }
  }

  function ensureTooltip() {
    if (!tooltip) {
      tooltip = document.createElement("div");
      tooltip.className = "chart-tooltip";
      tooltip.hidden = true;
      document.body.appendChild(tooltip);
    }

    const fullscreenElement = document.fullscreenElement;

    if (fullscreenElement && !fullscreenElement.contains(tooltip)) {
      fullscreenElement.appendChild(tooltip);
    } else if (!fullscreenElement && tooltip.parentElement !== document.body) {
      document.body.appendChild(tooltip);
    }

    return tooltip;
  }

  function productTooltip(product) {
    if (!product) {
      return "";
    }

    if (!product.isComparable) {
      return [
        product.label,
        "Conversion unavailable",
        `Original price: ${formatOriginalProductPrice(product)}`
      ].join("\n");
    }

    return [
      product.label,
      `Assessment date: ${formatTooltipDate(product.date)}`,
      `Original price: ${formatOriginalProductPrice(product)}`,
      Number.isFinite(product.barrelsPerMT)
        ? `Conversion: ${product.barrelsPerMT.toFixed(2)} bbl/mt`
        : "Conversion: workbook USD/bbl value",
      `Converted price: ${formatUsdPerBbl(product.convertedPrice)}`,
      `${(global.OilRiskConfig && (global.OilRiskConfig.DATA_SOURCE_MODE === "api" || (typeof global.OilRiskConfig.isApiMode === "function" && global.OilRiskConfig.isApiMode()))) ? "Brent Futures" : "Dated Brent"}: ${formatUsdPerBbl(product.brentPrice)}`,
      `Difference: ${formatSignedUsdPerBbl(product.difference)}`
    ].join("\n");
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
      return "N/A";
    }

    const prefix = value >= 0 ? "+" : "-";
    return `${prefix}${formatUsdPerBbl(Math.abs(value))}`;
  }

  function wrapCanvasLabel(ctx, text, x, y, maxWidth, lineHeight) {
    const words = String(text || "").split(/\s+/);
    let line = "";
    let currentY = y;

    words.forEach((word, index) => {
      const testLine = line ? `${line} ${word}` : word;

      if (ctx.measureText(testLine).width > maxWidth && line) {
        ctx.fillText(line, x, currentY);
        line = word;
        currentY += lineHeight;
      } else {
        line = testLine;
      }

      if (index === words.length - 1) {
        ctx.fillText(line, x, currentY);
      }
    });
  }

  function parseUtcDate(dateValue) {
    const date = new Date(`${String(dateValue).slice(0, 10)}T00:00:00Z`);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function formatTooltipDate(dateValue) {
    const date = parseUtcDate(dateValue);

    if (!date) {
      return String(dateValue || "");
    }

    return date.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      timeZone: "UTC"
    });
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

  let resizeTimer = null;

  global.addEventListener("resize", () => {
    if (!lastRenderedData) {
      return;
    }

    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => renderAll(lastRenderedData), 120);
  });
  global.addEventListener("beforeprint", () => {
    if (lastRenderedData) {
      renderAll(lastRenderedData);
    }
  });
  global.addEventListener("afterprint", () => {
    if (lastRenderedData) {
      renderAll(lastRenderedData);
    }
  });

  global.OilRiskCharts = {
    configureDefaults,
    createSparkline,
    renderAll
  };
})(window);
