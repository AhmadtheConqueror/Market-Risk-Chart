// ============================================================
// EXCEL AND FUTURE DATA ADAPTERS
// Converts workbook/API records into the dashboardData contract.
// ============================================================

(function registerExcelAdapter(global) {
  "use strict";

  const DEFAULT_COLUMN_MAP = {
    code: ["KRI_Code", "KRI Code", "KRICode", "KRI_ID", "Code", "Metric Code"],
    name: ["KRI_Name", "KRI Name", "KRI", "Name", "Metric", "Indicator"],
    category: ["Category", "Risk Category", "Risk_Category"],
    currentValue: ["Current_Value", "Current Value", "Current", "Latest", "Value"],
    previousValue: ["Previous_Value", "Previous Value", "Previous", "Prior", "Prior Value"],
    unit: ["Unit", "Units", "UOM"],
    status: ["Status", "Risk Status", "Rating", "Risk Rating"],
    exposure: ["Exposure", "Exposure Description", "Book", "Portfolio"],
    comment: ["Comment", "Comments", "Qualitative Comment", "Management Comment"],
    asOfDate: ["As_Of_Date", "As Of Date", "AsOfDate", "Date", "Observation Date"]
  };

  const CORE_EXPORT_SHEET_NAME = "Core_Export_Data";
  const CORE_EXPORT_START_DATE = "2026-01-01";

  const PRODUCTS = {
    brent: "PCAAS00",
    naphtha: "PAAAM00",
    gasoil: "AAVJI00",
    gasoline: "PGABM00",
    forcados: "PCABC00",
    wti: "PCACG00",
    jet: "PJAAV00"
  };

  const PRODUCT_KRI_CODES = {
    brent: "MR_BRENT",
    naphtha: "MR_NAPHTHA",
    gasoil: "MR_GASOIL",
    gasoline: "MR_GASOLINE",
    forcados: "MR_FORCADOS",
    wti: "MR_WTI",
    jet: "MR_JET"
  };

  const REFINED_PRODUCT_KEYS = [
    "naphtha",
    "gasoil",
    "gasoline",
    "jet"
  ];

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

  const PRODUCT_DETAILS = {
    brent: {
      name: "Dated Brent",
      currency: "USD",
      commodityUnit: "BBL",
      unit: "USD/BBL"
    },
    naphtha: {
      name: "Naphtha FOB Rdam Barge $/mt",
      shortName: "Naphtha",
      currency: "USD",
      commodityUnit: "MT",
      unit: "USD/MT"
    },
    gasoil: {
      name: "Gasoil 0.1%S FOB Med Cargo (NextGen MOC)",
      shortName: "Gasoil",
      currency: "USD",
      commodityUnit: "MT",
      unit: "USD/MT"
    },
    gasoline: {
      name: "Gasoline Prem Unleaded 10ppmS FOB AR Barge",
      shortName: "Gasoline",
      currency: "USD",
      commodityUnit: "MT",
      unit: "USD/MT"
    },
    forcados: {
      name: "Forcados FOB Nigeria",
      currency: "USD",
      commodityUnit: "BBL",
      unit: "USD/BBL"
    },
    wti: {
      name: "WTI Cushing Mo01",
      currency: "USD",
      commodityUnit: "BBL",
      unit: "USD/BBL"
    },
    jet: {
      name: "Jet FOB NWE Cargo",
      shortName: "Jet",
      currency: "USD",
      commodityUnit: "MT",
      unit: "USD/MT"
    }
  };

  const COMMODITY_UNIT_FALLBACKS = {
    PCAAS00: {
      currency: "USD",
      commodityUnit: "BBL"
    },
    PAAAM00: {
      currency: "USD",
      commodityUnit: "MT"
    },
    AAVJI00: {
      currency: "USD",
      commodityUnit: "MT"
    },
    PGABM00: {
      currency: "USD",
      commodityUnit: "MT"
    },
    PCABC00: {
      currency: "USD",
      commodityUnit: "BBL"
    },
    PCACG00: {
      currency: "USD",
      commodityUnit: "BBL"
    },
    PJAAV00: {
      currency: "USD",
      commodityUnit: "MT"
    }
  };

  const KRI_ALIASES = {
    PCAAS00: "MR_BRENT",
    BRENT: "MR_BRENT",
    "DATED BRENT": "MR_BRENT",
    "BRENT CRUDE": "MR_BRENT",
    "BRENT CRUDE PRICE": "MR_BRENT",
    PAAAM00: "MR_NAPHTHA",
    NAPHTHA: "MR_NAPHTHA",
    "NAPHTHA FOB RDAM BARGE": "MR_NAPHTHA",
    "NAPHTHA FOB RDAM BARGE MT": "MR_NAPHTHA",
    AAVJI00: "MR_GASOIL",
    GASOIL: "MR_GASOIL",
    "GASOIL 0 1 S FOB MED CARGO": "MR_GASOIL",
    "GASOIL 0 1 S FOB MED CARGO NEXTGEN MOC": "MR_GASOIL",
    "GASOIL 0 1S FOB MED CARGO NEXTGEN MOC": "MR_GASOIL",
    PGABM00: "MR_GASOLINE",
    GASOLINE: "MR_GASOLINE",
    "GASOLINE PREM UNLEADED 10PPMS FOB AR BARGE": "MR_GASOLINE",
    PCABC00: "MR_FORCADOS",
    FORCADOS: "MR_FORCADOS",
    "FORCADOS FOB NIGERIA": "MR_FORCADOS",
    PCACG00: "MR_WTI",
    WTI: "MR_WTI",
    "WTI CUSHING MO01": "MR_WTI",
    "WTI CUSHING MO 01": "MR_WTI",
    "WTI CRUDE": "MR_WTI",
    "WTI CRUDE PRICE": "MR_WTI",
    PJAAV00: "MR_JET",
    JET: "MR_JET",
    "JET FUEL": "MR_JET",
    "JET FOB NWE CARGO": "MR_JET",
    "GLOBAL SUPPLY DISRUPTION": "MG_SUPPLY_DISRUPTION",
    "GLOBAL SUPPLY DISRUPTION RISK": "MG_SUPPLY_DISRUPTION",
    "OPEC COMPLIANCE": "MG_OPEC_COMPLIANCE",
    "OPEC+ COMPLIANCE": "MG_OPEC_COMPLIANCE",
    DXY: "MG_DXY",
    "US DOLLAR INDEX": "MG_DXY",
    "US DOLLAR INDEX DXY": "MG_DXY",
    "GEOPOLITICAL TENSION": "MG_GEO_TENSION",
    "GEOPOLITICAL TENSION INDEX": "MG_GEO_TENSION",
    "COUNTERPARTY CREDIT": "CE_COUNTERPARTY_CREDIT",
    "COUNTERPARTY CREDIT RISK": "CE_COUNTERPARTY_CREDIT",
    "CUSTOMER OFFTAKE": "CE_CUSTOMER_OFFTAKE",
    "CUSTOMER OFFTAKE RISK": "CE_CUSTOMER_OFFTAKE",
    "CUSTOMER / OFFTAKE RISK": "CE_CUSTOMER_OFFTAKE",
    INVENTORY: "CE_INVENTORY_STOCK",
    "INVENTORY STOCK": "CE_INVENTORY_STOCK",
    "INVENTORY STOCK LEVEL": "CE_INVENTORY_STOCK",
    "INVENTORY / STOCK LEVEL": "CE_INVENTORY_STOCK",
    VLCC: "CE_VLCC_FREIGHT",
    FREIGHT: "CE_VLCC_FREIGHT",
    "VLCC FREIGHT": "CE_VLCC_FREIGHT",
    "VLCC FREIGHT RATE": "CE_VLCC_FREIGHT"
  };

  const QUALITATIVE_ALIASES = {
    QUAL_OPERATIONAL_RISK: "operational-risk",
    "OPERATIONAL RISK": "operational-risk",
    OPERATIONS: "operational-risk",
    QUAL_REGULATORY_ESG: "regulatory-esg",
    "REGULATORY ESG": "regulatory-esg",
    "REGULATORY / ESG": "regulatory-esg",
    ESG: "regulatory-esg"
  };

  function ensureSheetJs() {
    if (!global.XLSX) {
      throw new Error("SheetJS is not available. Check the xlsx script include in index.html.");
    }
  }

  function readWorkbook(file) {
    ensureSheetJs();

    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = (event) => {
        try {
          const workbook = global.XLSX.read(event.target.result, {
            type: "array",
            cellDates: true
          });

          resolve(workbookToRecords(workbook));
        } catch (error) {
          reject(error);
        }
      };

      reader.onerror = () => reject(reader.error);
      reader.readAsArrayBuffer(file);
    });
  }

  function readWorkbookData(file) {
    ensureSheetJs();

    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = (event) => {
        try {
          const workbook = global.XLSX.read(event.target.result, {
            type: "array",
            cellDates: false
          });

          resolve({
            records: workbookToRecords(workbook),
            plattsMarketData: extractPlattsMarketData(workbook),
            coreExportData: parseCoreExportSheet(workbook)
          });
        } catch (error) {
          reject(error);
        }
      };

      reader.onerror = () => reject(reader.error);
      reader.readAsArrayBuffer(file);
    });
  }

  function workbookToRecords(workbook) {
    const firstSheetName = workbook.SheetNames[0];

    if (!firstSheetName) {
      return [];
    }

    const worksheet = workbook.Sheets[firstSheetName];

    return global.XLSX.utils.sheet_to_json(worksheet, {
      defval: "",
      raw: false
    });
  }

  function parseCoreExportSheet(workbook) {
    const exactSheetName = (workbook.SheetNames || []).find((name) => (
      normalizeColumnName(name) === normalizeColumnName(CORE_EXPORT_SHEET_NAME)
    ));
    const sheetNames = exactSheetName
      ? [exactSheetName].concat((workbook.SheetNames || []).filter((name) => name !== exactSheetName))
      : (workbook.SheetNames || []);

    for (const sheetName of sheetNames) {
      const parsedRows = parseCoreExportWorksheet(workbook.Sheets[sheetName]);

      if (parsedRows.length) {
        return parsedRows;
      }
    }

    return [];
  }

  function parseCoreExportWorksheet(worksheet) {
    if (!worksheet) {
      return [];
    }

    const rows = global.XLSX.utils.sheet_to_json(worksheet, {
      header: 1,
      defval: "",
      raw: true
    });
    const headerRowIndex = rows.findIndex((row) => (
      findCoreExportColumn(row, "timestamp") >= 0 &&
      findCoreExportColumn(row, "znr734", "volume") >= 0 &&
      findCoreExportColumn(row, "pcaas00", "close") >= 0
    ));

    if (headerRowIndex < 0) {
      return [];
    }

    const headers = rows[headerRowIndex] || [];
    const timestampColumn = findCoreExportColumn(headers, "timestamp");
    const crudeRiskColumn = findCoreExportColumn(headers, "znr734", "volume");
    const datedBrentColumn = findCoreExportColumn(headers, "pcaas00", "close");

    const rowsByTimestamp = new Map();

    rows.slice(headerRowIndex + 1).forEach((row) => {
      const date = parseCoreExportDate(row[timestampColumn]);

      if (!date || date < CORE_EXPORT_START_DATE) {
        return;
      }

      const crudeSupplyRisk = parseNullableNumber(row[crudeRiskColumn]);
      const datedBrent = parseNullableNumber(row[datedBrentColumn]);
      const point = rowsByTimestamp.get(date) || {
        date,
        crudeSupplyRisk: null,
        datedBrent: null
      };

      if (crudeSupplyRisk !== null) {
        point.crudeSupplyRisk = crudeSupplyRisk;
      }

      if (datedBrent !== null) {
        point.datedBrent = datedBrent;
      }

      rowsByTimestamp.set(date, point);
    });

    return Array.from(rowsByTimestamp.values())
      .filter((point) => point.crudeSupplyRisk !== null || point.datedBrent !== null)
      .sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
  }

  function parseCoreExportDate(value) {
    if (typeof value === "number" && Number.isFinite(value)) {
      const parsed = global.XLSX.SSF.parse_date_code(value);

      return parsed
        ? formatCalendarDate(parsed.y, parsed.m, parsed.d)
        : "";
    }

    if (value instanceof Date && !Number.isNaN(value.getTime())) {
      return formatCalendarDate(
        value.getFullYear(),
        value.getMonth() + 1,
        value.getDate()
      );
    }

    const text = String(value || "").trim();
    const isoMatch = text.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})/);

    if (isoMatch) {
      return formatCalendarDate(
        Number(isoMatch[1]),
        Number(isoMatch[2]),
        Number(isoMatch[3])
      );
    }

    const dayFirstMatch = text.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})/);

    if (dayFirstMatch) {
      const year = dayFirstMatch[3].length === 2
        ? Number(`20${dayFirstMatch[3]}`)
        : Number(dayFirstMatch[3]);

      return formatCalendarDate(
        year,
        Number(dayFirstMatch[2]),
        Number(dayFirstMatch[1])
      );
    }

    return "";
  }

  function formatCalendarDate(year, month, day) {
    if (
      !Number.isInteger(year) ||
      !Number.isInteger(month) ||
      !Number.isInteger(day) ||
      year < 1900 ||
      year > 2100 ||
      month < 1 ||
      month > 12 ||
      day < 1 ||
      day > 31
    ) {
      return "";
    }

    const calendarDate = new Date(Date.UTC(year, month - 1, day));

    if (
      calendarDate.getUTCFullYear() !== year ||
      calendarDate.getUTCMonth() !== month - 1 ||
      calendarDate.getUTCDate() !== day
    ) {
      return "";
    }

    return [
      String(year).padStart(4, "0"),
      String(month).padStart(2, "0"),
      String(day).padStart(2, "0")
    ].join("-");
  }

  function findCoreExportColumn(headers, code, descriptor) {
    const normalizedCode = normalizeSymbolCell(code);
    const normalizedDescriptor = normalizeSymbolCell(descriptor);

    return (headers || []).findIndex((header) => {
      const normalizedHeader = normalizeSymbolCell(header);

      return normalizedHeader.includes(normalizedCode) && (
        !normalizedDescriptor || normalizedHeader.includes(normalizedDescriptor)
      );
    });
  }

  function extractPlattsMarketData(workbook) {
    const result = Object.keys(PRODUCTS).reduce((series, key) => {
      series[key] = {
        code: PRODUCTS[key],
        ...PRODUCT_DETAILS[key],
        history: []
      };

      return series;
    }, {});

    workbook.SheetNames.forEach((sheetName) => {
      if (normalizeColumnName(sheetName) === normalizeColumnName(CORE_EXPORT_SHEET_NAME)) {
        return;
      }

      const worksheet = workbook.Sheets[sheetName];
      const rows = global.XLSX.utils.sheet_to_json(worksheet, {
        header: 1,
        defval: "",
        raw: true
      });
      const symbolRows = findPlattsSymbolRows(rows);

      if (!symbolRows.length) {
        return;
      }

      symbolRows.forEach((symbolRow) => {
        const dateColumn = findAssessmentDateColumn(rows, symbolRow.rowIndex, symbolRow.columns);

        if (dateColumn < 0) {
          return;
        }

        Object.keys(PRODUCTS).forEach((productKey) => {
          const columnIndex = symbolRow.columns[productKey];

          if (!Number.isInteger(columnIndex)) {
            return;
          }

          const metadata = readSeriesMetadata(
            rows,
            symbolRow.rowIndex,
            columnIndex,
            productKey
          );
          const history = collectPlattsObservations(
            rows,
            symbolRow.rowIndex + 1,
            dateColumn,
            columnIndex
          );

          if (productKey === "brent") {
            if (isPreferredSeriesHistory(history, result[productKey].history)) {
              result[productKey] = {
                ...result[productKey],
                ...metadata,
                history
              };
            }
          } else if (isPreferredSeriesHistory(history, result[productKey].history)) {
            result[productKey] = {
              ...result[productKey],
              ...metadata,
              history
            };
          }
        });
      });
    });

    applyProductConversionSheets(result, workbook);

    return result;
  }

  function applyProductConversionSheets(result, workbook) {
    workbook.SheetNames.forEach((sheetName) => {
      const worksheet = workbook.Sheets[sheetName];
      const rows = global.XLSX.utils.sheet_to_json(worksheet, {
        header: 1,
        defval: "",
        raw: true
      });

      Object.keys(PRODUCTS).forEach((productKey) => {
        if (productKey === "brent") {
          return;
        }

        const conversionColumns = findProductConversionColumns(rows, productKey);

        if (!conversionColumns) {
          return;
        }

        const conversionHistory = collectProductConversionObservations(
          rows,
          conversionColumns.headerRowIndex + 1,
          conversionColumns.dateColumn,
          conversionColumns.convertedColumn,
          conversionColumns.factorColumn
        );

        if (!conversionHistory.length) {
          return;
        }

        result[productKey].conversionHistory = mergeProductConversionHistory(
          result[productKey].conversionHistory,
          conversionHistory
        );
      });
    });
  }

  function findProductConversionColumns(rows, productKey) {
    const symbol = normalizeColumnName(PRODUCTS[productKey]);

    for (let rowIndex = 0; rowIndex < rows.length; rowIndex += 1) {
      const row = rows[rowIndex] || [];
      const dateColumn = row.findIndex((cell) => {
        const header = normalizeColumnName(cell);
        return header === "date" ||
          header === "assessdate" ||
          header === "assessmentdate";
      });
      const convertedColumn = row.findIndex((cell) => {
        const header = normalizeColumnName(cell);
        return header.includes(symbol) &&
          header.includes("usd") &&
          header.includes("bbl") &&
          !header.includes("pcaas00") &&
          !header.includes("mt");
      });
      const factorColumn = row.findIndex((cell) => {
        const header = normalizeColumnName(cell);
        return header.includes("conversionfactor") &&
          header.includes("bbl") &&
          header.includes("mt");
      });

      if (dateColumn >= 0 && convertedColumn >= 0 && factorColumn >= 0) {
        return {
          headerRowIndex: rowIndex,
          dateColumn,
          convertedColumn,
          factorColumn
        };
      }
    }

    return null;
  }

  function collectProductConversionObservations(rows, startRowIndex, dateColumn, convertedColumn, factorColumn) {
    const observationsByDate = new Map();

    for (let rowIndex = startRowIndex; rowIndex < rows.length; rowIndex += 1) {
      const row = rows[rowIndex] || [];
      const date = parseAssessmentDate(row[dateColumn]);
      const convertedValue = parseNullableNumber(row[convertedColumn]);
      const barrelsPerMT = parseNullableNumber(row[factorColumn]);

      if (!date || (convertedValue === null && barrelsPerMT === null)) {
        continue;
      }

      observationsByDate.set(date, {
        date,
        convertedValue,
        barrelsPerMT
      });
    }

    return Array.from(observationsByDate.values())
      .sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
  }

  function mergeProductConversionHistory(existingHistory, additionalHistory) {
    const observations = new Map();

    [...(existingHistory || []), ...(additionalHistory || [])].forEach((point) => {
      if (!point || !point.date) {
        return;
      }

      observations.set(point.date, {
        date: point.date,
        convertedValue: Number.isFinite(Number(point.convertedValue))
          ? Number(point.convertedValue)
          : null,
        barrelsPerMT: Number.isFinite(Number(point.barrelsPerMT))
          ? Number(point.barrelsPerMT)
          : null
      });
    });

    return Array.from(observations.values())
      .sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
  }

  function findPlattsSymbolRows(rows) {
    const matches = [];

    rows.forEach((row, rowIndex) => {
      const columns = {};
      const columnScores = {};

      row.forEach((cell, columnIndex) => {
        Object.keys(PRODUCTS).forEach((productKey) => {
          const score = scorePlattsProductColumn(cell, productKey);

          if (score > 0 && score > (columnScores[productKey] || 0)) {
            columns[productKey] = columnIndex;
            columnScores[productKey] = score;
          }
        });
      });

      const matchCount = Object.keys(columns).length;

      if (matchCount) {
        matches.push({
          rowIndex,
          columns,
          matchCount
        });
      }
    });

    return matches.sort((a, b) => b.matchCount - a.matchCount);
  }

  function scorePlattsProductColumn(value, productKey) {
    const cellText = normalizeSymbolCell(value);

    if (!cellText.includes(PRODUCTS[productKey])) {
      return 0;
    }

    const header = normalizeColumnName(value);
    let score = 10;

    if (productKey === "brent") {
      if (header.includes("bbl")) {
        score += 5;
      }
    } else {
      if (header.includes("mt")) {
        score += 10;
      }

      if (header.includes("bbl")) {
        score -= 4;
      }

      if (header.includes("crack") || header.includes("spread")) {
        score -= 8;
      }
    }

    return score;
  }

  function mergeHistory(existingHistory, additionalHistory) {
    const observations = new Map();

    [...(existingHistory || []), ...(additionalHistory || [])].forEach((point) => {
      if (point && point.date && Number.isFinite(Number(point.value))) {
        observations.set(point.date, {
          date: point.date,
          value: Number(point.value)
        });
      }
    });

    return Array.from(observations.values())
      .sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
  }

  function isPreferredSeriesHistory(candidateHistory, currentHistory) {
    if (!candidateHistory.length) {
      return false;
    }

    if (!currentHistory.length) {
      return true;
    }

    const candidateLatest = candidateHistory[candidateHistory.length - 1].date;
    const currentLatest = currentHistory[currentHistory.length - 1].date;
    const candidateTime = Date.parse(candidateLatest);
    const currentTime = Date.parse(currentLatest);

    if (candidateTime > currentTime) {
      return true;
    }

    if (candidateTime < currentTime) {
      return false;
    }

    return candidateHistory.length > currentHistory.length;
  }

  function readSeriesMetadata(rows, symbolRowIndex, valueColumn, productKey) {
    const symbol = PRODUCTS[productKey];
    const fallback = {
      ...COMMODITY_UNIT_FALLBACKS[symbol],
      ...PRODUCT_DETAILS[productKey]
    };
    const description = findMetadataValue(rows, symbolRowIndex, valueColumn, [
      "description",
      "descr",
      "commodity",
      "assessment"
    ]) || findNearbyDescription(rows, symbolRowIndex, valueColumn) || fallback.name;
    const rawCurrency = findMetadataValue(rows, symbolRowIndex, valueColumn, [
      "currency",
      "curr"
    ]);
    const rawUnit = findMetadataValue(rows, symbolRowIndex, valueColumn, [
      "unit",
      "uom",
      "measure"
    ]);
    const detectedCurrency = normalizeCommodityCurrency(
      rawCurrency || rawUnit || description || fallback.currency || fallback.unit
    );
    const currency = fallback.currency || detectedCurrency || "USD";
    const commodityUnit = normalizeCommodityUnit(
      rawUnit || description || fallback.commodityUnit || fallback.unit
    );

    return {
      name: description,
      shortName: fallback.shortName,
      currency,
      commodityUnit: commodityUnit || fallback.commodityUnit || "",
      unit: formatCommodityUnitLabel(
        currency || fallback.currency || "USD",
        commodityUnit || fallback.commodityUnit || ""
      )
    };
  }

  function findMetadataValue(rows, symbolRowIndex, valueColumn, keywords) {
    const startIndex = Math.max(0, symbolRowIndex - 8);
    const endIndex = Math.min(rows.length - 1, symbolRowIndex + 8);

    for (let rowIndex = startIndex; rowIndex <= endIndex; rowIndex += 1) {
      if (rowIndex === symbolRowIndex) {
        continue;
      }

      const row = rows[rowIndex] || [];
      const rowLabel = row
        .filter((_, columnIndex) => columnIndex !== valueColumn)
        .map((cell) => String(cell || "").toLowerCase())
        .join(" ");
      const hasLabel = keywords.some((keyword) => rowLabel.includes(keyword));

      if (!hasLabel) {
        continue;
      }

      const value = row[valueColumn];

      if (value !== undefined && value !== null && value !== "") {
        return String(value).trim();
      }
    }

    return "";
  }

  function findNearbyDescription(rows, symbolRowIndex, valueColumn) {
    const candidateRowIndexes = [];

    for (let offset = 1; offset <= 5; offset += 1) {
      if (symbolRowIndex + offset < rows.length) {
        candidateRowIndexes.push(symbolRowIndex + offset);
      }

      if (symbolRowIndex - offset >= 0) {
        candidateRowIndexes.push(symbolRowIndex - offset);
      }
    }

    for (const rowIndex of candidateRowIndexes) {
      const value = String((rows[rowIndex] || [])[valueColumn] || "").trim();

      if (
        value &&
        /[A-Za-z]/.test(value) &&
        !normalizeSymbolCell(value).includes(normalizeSymbolCell((rows[symbolRowIndex] || [])[valueColumn])) &&
        !isMetadataOnlyValue(value)
      ) {
        return value;
      }
    }

    return "";
  }

  function isMetadataOnlyValue(value) {
    const compact = String(value || "")
      .trim()
      .toUpperCase()
      .replace(/\s+/g, "");

    return [
      "USD",
      "$",
      "USDO",
      "USDBBL",
      "USD/BBL",
      "$/BBL",
      "BBL",
      "USDMT",
      "USD/MT",
      "$/MT",
      "MT"
    ].includes(compact);
  }

  function normalizeCommodityCurrency(value) {
    const text = String(value || "").trim().toUpperCase();

    if (text.includes("USD") || text.includes("$") || text.includes("US DOLLAR")) {
      return "USD";
    }

    const currencyCode = text.match(/\b[A-Z]{3}\b/);

    if (currencyCode && KNOWN_CURRENCY_CODES.has(currencyCode[0])) {
      return currencyCode[0];
    }

    const cleaned = text.replace(/[^A-Z]/g, "");

    if (["BBL", "BARREL", "MT", "METRIC", "TONNE"].includes(cleaned)) {
      return "";
    }

    return KNOWN_CURRENCY_CODES.has(cleaned) ? cleaned : "";
  }

  function normalizeCommodityUnit(value) {
    const text = String(value || "").trim().toUpperCase();

    if (text.includes("BBL") || text.includes("BARREL")) {
      return "BBL";
    }

    if (text.includes("MT") || text.includes("METRIC") || text.includes("TONNE")) {
      return "MT";
    }

    return "";
  }

  function formatCommodityUnitLabel(currency, unit) {
    const normalizedCurrency = normalizeCommodityCurrency(currency) || "USD";
    const normalizedUnit = normalizeCommodityUnit(unit);

    return normalizedUnit
      ? `${normalizedCurrency}/${normalizedUnit.toLowerCase()}`
      : normalizedCurrency;
  }

  function normalizeSymbolCell(value) {
    return String(value || "")
      .toUpperCase()
      .replace(/[^A-Z0-9]/g, "");
  }

  function findAssessmentDateColumn(rows, symbolRowIndex, productColumns) {
    const maxColumns = rows.reduce((max, row) => Math.max(max, row.length), 0);
    const blockedColumns = new Set(Object.values(productColumns));
    let bestColumn = -1;
    let bestScore = 0;

    for (let columnIndex = 0; columnIndex < maxColumns; columnIndex += 1) {
      if (blockedColumns.has(columnIndex)) {
        continue;
      }

      let dateCount = 0;

      for (let rowIndex = symbolRowIndex + 1; rowIndex < rows.length; rowIndex += 1) {
        if (parseAssessmentDate(rows[rowIndex][columnIndex])) {
          dateCount += 1;
        }
      }

      if (dateCount > bestScore) {
        bestScore = dateCount;
        bestColumn = columnIndex;
      }
    }

    return bestScore > 0 ? bestColumn : -1;
  }

  function collectPlattsObservations(rows, startRowIndex, dateColumn, valueColumn) {
    const observationsByDate = new Map();

    for (let rowIndex = startRowIndex; rowIndex < rows.length; rowIndex += 1) {
      const date = parseAssessmentDate(rows[rowIndex][dateColumn]);
      const value = parseNumber(rows[rowIndex][valueColumn]);

      if (!date || value === null) {
        continue;
      }

      observationsByDate.set(date, {
        date,
        value
      });
    }

    return Array.from(observationsByDate.values())
      .sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
  }

  function parseAssessmentDate(value) {
    const date = parseDateValue(value);

    if (!date) {
      return "";
    }

    const year = Number(date.slice(0, 4));

    if (year < 1990 || year > 2100) {
      return "";
    }

    return date;
  }

  function normalizeColumnName(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "");
  }

  function readField(row, logicalField, columnMap) {
    const aliases = (columnMap || DEFAULT_COLUMN_MAP)[logicalField] || [];
    const normalizedRow = {};

    Object.keys(row).forEach((key) => {
      normalizedRow[normalizeColumnName(key)] = row[key];
    });

    for (const alias of aliases) {
      const exactValue = row[alias];

      if (exactValue !== undefined && exactValue !== null && exactValue !== "") {
        return exactValue;
      }

      const normalizedValue = normalizedRow[normalizeColumnName(alias)];

      if (normalizedValue !== undefined && normalizedValue !== null && normalizedValue !== "") {
        return normalizedValue;
      }
    }

    return "";
  }

  function parseNumber(value) {
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }

    if (value === null || value === undefined || value === "") {
      return null;
    }

    const text = String(value).trim();

    if (!text) {
      return null;
    }

    const isNegativeParentheses = /^\(.*\)$/.test(text);
    const cleaned = text
      .replace(/[,$%]/g, "")
      .replace(/[()]/g, "")
      .replace(/[^0-9.-]/g, "");

    if (!cleaned || cleaned === "-" || cleaned === "." || cleaned === "-.") {
      return null;
    }

    const parsed = Number(cleaned);

    if (!Number.isFinite(parsed)) {
      return null;
    }

    return isNegativeParentheses ? -parsed : parsed;
  }

  function parseNullableNumber(value) {
    if (
      value === null ||
      value === undefined ||
      String(value).trim() === ""
    ) {
      return null;
    }

    return parseNumber(value);
  }

  function parseDateValue(value) {
    if (!value) {
      return "";
    }

    if (value instanceof Date && !Number.isNaN(value.getTime())) {
      return value.toISOString().slice(0, 10);
    }

    if (typeof value === "number" && Number.isFinite(value)) {
      const excelEpoch = Date.UTC(1899, 11, 30);
      const parsedDate = new Date(excelEpoch + value * 86400000);
      return parsedDate.toISOString().slice(0, 10);
    }

    const text = String(value).trim();
    const isoMatch = text.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);

    if (isoMatch) {
      return [
        isoMatch[1],
        isoMatch[2].padStart(2, "0"),
        isoMatch[3].padStart(2, "0")
      ].join("-");
    }

    const dayFirstMatch = text.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})$/);

    if (dayFirstMatch) {
      const year = dayFirstMatch[3].length === 2
        ? `20${dayFirstMatch[3]}`
        : dayFirstMatch[3];
      const day = dayFirstMatch[1].padStart(2, "0");
      const month = dayFirstMatch[2].padStart(2, "0");
      return `${year}-${month}-${day}`;
    }

    const parsedDate = new Date(text);

    if (Number.isNaN(parsedDate.getTime())) {
      return "";
    }

    return parsedDate.toISOString().slice(0, 10);
  }

  function normalizeRecord(row, columnMap) {
    return {
      code: cleanCode(readField(row, "code", columnMap)),
      name: String(readField(row, "name", columnMap) || "").trim(),
      category: String(readField(row, "category", columnMap) || "").trim(),
      currentValue: parseNumber(readField(row, "currentValue", columnMap)),
      previousValue: parseNumber(readField(row, "previousValue", columnMap)),
      unit: String(readField(row, "unit", columnMap) || "").trim(),
      externalStatus: String(readField(row, "status", columnMap) || "").trim(),
      exposure: String(readField(row, "exposure", columnMap) || "").trim(),
      comment: String(readField(row, "comment", columnMap) || "").trim(),
      asOfDate: parseDateValue(readField(row, "asOfDate", columnMap))
    };
  }

  function cleanCode(value) {
    return String(value || "")
      .trim()
      .toUpperCase()
      .replace(/[\s-]+/g, "_")
      .replace(/[^A-Z0-9_]/g, "");
  }

  function aliasKey(value) {
    return String(value || "")
      .toUpperCase()
      .replace(/[^A-Z0-9+]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function resolveKriCode(record, data) {
    if (record.code && data.kris[record.code]) {
      return record.code;
    }

    const codeAlias = KRI_ALIASES[aliasKey(record.code)];

    if (codeAlias) {
      return codeAlias;
    }

    const nameAlias = KRI_ALIASES[aliasKey(record.name)];

    if (nameAlias) {
      return nameAlias;
    }

    return global.OilRiskData.findKriCodeByName(record.name);
  }

  function resolveQualitativeId(record, data) {
    const codeKey = aliasKey(record.code);
    const nameKey = aliasKey(record.name);

    if (QUALITATIVE_ALIASES[codeKey]) {
      return QUALITATIVE_ALIASES[codeKey];
    }

    if (QUALITATIVE_ALIASES[nameKey]) {
      return QUALITATIVE_ALIASES[nameKey];
    }

    const matchingComment = data.qualitativeComments.find((item) => (
      item.sourceCode === record.code || aliasKey(item.title) === nameKey
    ));

    return matchingComment ? matchingComment.id : "";
  }

  function splitComments(text) {
    return String(text || "")
      .split(/\r?\n|\s+\|\|\s+/)
      .map((comment) => comment.trim())
      .filter(Boolean);
  }

  function sortRecordsByDate(records) {
    return records.slice().sort((a, b) => {
      const aTime = Date.parse(a.asOfDate || "1900-01-01");
      const bTime = Date.parse(b.asOfDate || "1900-01-01");
      return aTime - bTime;
    });
  }

  function previousIsoDate(dateValue) {
    const date = new Date(`${dateValue}T00:00:00`);

    if (Number.isNaN(date.getTime())) {
      return dateValue;
    }

    date.setDate(date.getDate() - 1);
    return date.toISOString().slice(0, 10);
  }

  function buildHistory(existingKri, rows, latestRow) {
    const datedRows = rows
      .filter((row) => row.asOfDate && row.currentValue !== null)
      .map((row) => ({
        date: row.asOfDate,
        value: row.currentValue
      }));

    if (datedRows.length >= 2) {
      if (existingKri.categoryId === "market") {
        return rollingCalendarHistory(datedRows, 30);
      }

      return datedRows.slice(-16);
    }

    const existingHistory = (existingKri.history || []).slice(-10);
    const updatedHistory = existingHistory.map((point) => ({
      date: point.date,
      value: point.value
    }));
    const latestExistingPoint = existingHistory[existingHistory.length - 1];
    const asOfDate = latestRow.asOfDate || (latestExistingPoint && latestExistingPoint.date) || "";

    if (latestRow.previousValue !== null && updatedHistory.length >= 2) {
      updatedHistory[updatedHistory.length - 2] = {
        date: asOfDate ? previousIsoDate(asOfDate) : updatedHistory[updatedHistory.length - 2].date,
        value: latestRow.previousValue
      };
    }

    if (latestRow.currentValue !== null && updatedHistory.length >= 1) {
      updatedHistory[updatedHistory.length - 1] = {
        date: asOfDate || updatedHistory[updatedHistory.length - 1].date,
        value: latestRow.currentValue
      };
    }

    return updatedHistory;
  }

  function updateKriFromRows(data, code, rows) {
    const sortedRows = sortRecordsByDate(rows);
    const latestRow = sortedRows[sortedRows.length - 1];
    const previousRow = sortedRows[sortedRows.length - 2];
    const kri = data.kris[code];

    if (!latestRow || !kri) {
      return;
    }

    if (latestRow.currentValue !== null) {
      kri.currentValue = latestRow.currentValue;
    }

    if (latestRow.previousValue !== null) {
      kri.previousValue = latestRow.previousValue;
    } else if (previousRow && previousRow.currentValue !== null) {
      kri.previousValue = previousRow.currentValue;
    }

    if (latestRow.unit) {
      kri.unit = latestRow.unit;
    }

    if (latestRow.externalStatus) {
      kri.externalStatus = latestRow.externalStatus;
    }

    if (latestRow.exposure) {
      kri.exposure = latestRow.exposure;
    }

    if (latestRow.comment) {
      kri.comment = latestRow.comment;
      updateQualitativeComment(data, code, latestRow.comment);
    }

    kri.history = buildHistory(kri, sortedRows, latestRow);
  }

  function applyPlattsMarketData(data, plattsMarketData) {
    if (!plattsMarketData) {
      return {
        mappedMarketSeries: 0,
        mappedMarketKriCodes: [],
        latestDate: ""
      };
    }

    if (!data.marketProductPrices) {
      data.marketProductPrices = {};
    }

    let mappedMarketSeries = 0;
    let latestDate = "";
    const mappedMarketKriCodes = new Set();

    Object.keys(PRODUCTS).forEach((productKey) => {
      const product = plattsMarketData[productKey];

      if (!product || !product.history.length) {
        return;
      }

      const productHistory = productKey === "brent"
        ? rollingCalendarHistory(product.history)
        : rollingCalendarHistory(product.history, 30);

      if (!productHistory.length) {
        return;
      }

      if (productKey === "brent") {
        data.plattsBrentHistory = productHistory;
      }

      const details = PRODUCT_DETAILS[productKey] || {};
      const productCurrency = normalizeCommodityCurrency(product.currency || product.unit) || details.currency || "USD";
      const productUnit = normalizeCommodityUnit(product.commodityUnit || product.unit) || details.commodityUnit || "";
      const latest = productHistory[productHistory.length - 1];
      const previous = productHistory[productHistory.length - 2] || latest;
      const kriCode = PRODUCT_KRI_CODES[productKey];
      const kri = data.kris[kriCode];

      if (kri) {
        kri.currentValue = latest.value;
        kri.previousValue = previous.value;
        kri.unit = formatCommodityUnitLabel(productCurrency, productUnit);
        kri.commodityCurrency = productCurrency;
        kri.commodityUnit = productUnit;
        kri.commodityValueFormat = true;
        kri.history = productHistory;
        mappedMarketKriCodes.add(kriCode);
        mappedMarketSeries += 1;
        latestDate = newerDate(latestDate, latest.date);
      }

      if (REFINED_PRODUCT_KEYS.includes(productKey)) {
        const conversionHistory = Array.isArray(product.conversionHistory)
          ? product.conversionHistory
          : [];
        const latestConversion = latestProductConversionObservation(conversionHistory, latest.date);

        data.marketProductPrices[productKey] = {
          code: PRODUCTS[productKey],
          name: details.name || product.name,
          shortName: details.shortName || product.shortName || details.name || product.name,
          currency: productCurrency,
          commodityUnit: productUnit,
          unit: formatCommodityUnitLabel(productCurrency, productUnit),
          conversionHistory,
          conversionFactor: latestConversion ? latestConversion.barrelsPerMT : null,
          history: productHistory
        };
      }
    });

    return {
      mappedMarketSeries,
      mappedMarketKriCodes: Array.from(mappedMarketKriCodes),
      latestDate
    };
  }

  function latestProductConversionObservation(history, targetDate) {
    const observations = (history || [])
      .filter((point) => point && point.date)
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

  function rollingCalendarHistory(history, days) {
    const observations = (history || [])
      .map((point) => ({
        date: point.date,
        value: parseNumber(point.value)
      }))
      .filter((point) => point.date && point.value !== null)
      .sort((a, b) => Date.parse(a.date) - Date.parse(b.date));

    if (!observations.length) {
      return [];
    }

    if (!days) {
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

  function newerDate(left, right) {
    if (!left) {
      return right || "";
    }

    if (!right) {
      return left;
    }

    return Date.parse(right) > Date.parse(left) ? right : left;
  }

  function updateQualitativeComment(data, sourceCodeOrId, commentText) {
    const comments = splitComments(commentText);

    if (!comments.length) {
      return;
    }

    const qualitative = data.qualitativeComments.find((item) => (
      item.sourceCode === sourceCodeOrId || item.id === sourceCodeOrId
    ));

    if (qualitative) {
      qualitative.comments = comments;
    }
  }

  function newestDate(records, fallbackDate) {
    const times = records
      .map((record) => Date.parse(record.asOfDate))
      .filter((time) => Number.isFinite(time));
    const fallbackTime = Date.parse(fallbackDate);

    if (Number.isFinite(fallbackTime)) {
      times.push(fallbackTime);
    }

    if (!times.length) {
      return fallbackDate || "";
    }

    return new Date(Math.max(...times)).toISOString().slice(0, 10);
  }

  function normalizeWorkbookRecords(records, options) {
    const settings = options || {};
    const columnMap = settings.columnMap || DEFAULT_COLUMN_MAP;
    const data = global.OilRiskData.cloneDashboardData();
    data.coreExportData = Array.isArray(settings.coreExportData)
      ? settings.coreExportData
      : [];
    const groupedKriRows = new Map();
    const normalizedRecords = (records || [])
      .map((row) => normalizeRecord(row, columnMap))
      .filter((row) => row.code || row.name || row.comment);

    normalizedRecords.forEach((record) => {
      const code = resolveKriCode(record, data);

      if (code && data.kris[code]) {
        if (!groupedKriRows.has(code)) {
          groupedKriRows.set(code, []);
        }

        groupedKriRows.get(code).push(record);
        return;
      }

      const qualitativeId = resolveQualitativeId(record, data);

      if (qualitativeId && record.comment) {
        updateQualitativeComment(data, qualitativeId, record.comment);
      }
    });

    groupedKriRows.forEach((rows, code) => {
      updateKriFromRows(data, code, rows);
    });

    const plattsSummary = applyPlattsMarketData(data, settings.plattsMarketData);

    data.source = {
      type: settings.sourceType || "excel",
      label: settings.sourceLabel || (settings.sourceType === "live" ? "Live" : "Excel"),
      name: settings.sourceName || "Uploaded workbook",
      asOfDate: newestDate(normalizedRecords, plattsSummary.latestDate || data.source.asOfDate),
      lastRefreshed: new Date().toISOString(),
      refreshEndpoint: settings.refreshEndpoint || data.source.refreshEndpoint || "/api/dashboard-data"
    };

    const mappedKriCodes = new Set(groupedKriRows.keys());

    (plattsSummary.mappedMarketKriCodes || []).forEach((code) => {
      mappedKriCodes.add(code);
    });

    const mappedKris = mappedKriCodes.size;

    data.importInfo = {
      recordsRead: (records || []).length,
      mappedKris,
      mappedMarketSeries: plattsSummary.mappedMarketSeries,
      missingKris: Object.keys(data.kris).length - mappedKris
    };

    return data;
  }

  async function fetchDashboardDataFromApi(endpoint) {
    const response = await fetch(endpoint || "/api/dashboard-data", {
      headers: {
        Accept: "application/json"
      }
    });

    if (!response.ok) {
      throw new Error(`Dashboard API returned ${response.status}`);
    }

    const payload = await response.json();
    return normalizeApiPayload(payload, endpoint);
  }

  function normalizeApiPayload(payload, endpoint) {
    if (payload && payload.schemaVersion && payload.kris) {
      const data = global.OilRiskData.cloneDashboardData(payload);
      data.source = {
        ...data.source,
        type: "live",
        label: "Live",
        name: data.source?.name || "Backend API",
        lastRefreshed: new Date().toISOString(),
        refreshEndpoint: endpoint || data.source?.refreshEndpoint || "/api/dashboard-data"
      };
      return data;
    }

    const records = Array.isArray(payload)
      ? payload
      : Array.isArray(payload?.records)
        ? payload.records
        : [];

    return normalizeWorkbookRecords(records, {
      sourceType: "live",
      sourceLabel: "Live",
      sourceName: "Backend API",
      refreshEndpoint: endpoint || "/api/dashboard-data"
    });
  }

  function downloadSampleWorkbook() {
    ensureSheetJs();

    const workbook = global.XLSX.utils.book_new();
    const dataSheet = global.XLSX.utils.json_to_sheet(global.OilRiskData.sampleWorkbookRows);
    const schemaSheet = global.XLSX.utils.json_to_sheet(global.OilRiskData.sampleWorkbookSchema);

    dataSheet["!cols"] = [
      { wch: 24 },
      { wch: 30 },
      { wch: 28 },
      { wch: 15 },
      { wch: 15 },
      { wch: 14 },
      { wch: 12 },
      { wch: 30 },
      { wch: 70 },
      { wch: 14 }
    ];

    schemaSheet["!cols"] = [
      { wch: 22 },
      { wch: 78 }
    ];

    global.XLSX.utils.book_append_sheet(workbook, dataSheet, "Daily KRI Data");
    global.XLSX.utils.book_append_sheet(workbook, schemaSheet, "Schema");
    global.XLSX.writeFile(workbook, "daily-oil-risk-sample.xlsx");
  }

  global.OilRiskExcel = {
    DEFAULT_COLUMN_MAP,
    PRODUCTS,
    downloadSampleWorkbook,
    extractPlattsMarketData,
    fetchDashboardDataFromApi,
    normalizeApiPayload,
    normalizeWorkbookRecords,
    parseCoreExportSheet,
    parseNumber,
    parseNullableNumber,
    readWorkbook,
    readWorkbookData,
    workbookToRecords
  };
})(typeof window !== "undefined" ? window : globalThis);
