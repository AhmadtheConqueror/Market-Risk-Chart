require("dotenv").config();

const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { DatabaseSync } = require("node:sqlite");

const bcrypt = require("bcryptjs");
const express = require("express");
const session = require("express-session");
const multer = require("multer");
const XLSX = require("xlsx");

globalThis.XLSX = XLSX;
require("./data.js");
require("./risk-engine.js");
require("./excel.js");

const PORT = Number(process.env.PORT || 3000);
const SESSION_SECRET = process.env.SESSION_SECRET || crypto.randomBytes(32).toString("hex");
const ROOT_DIR = __dirname;
const PUBLIC_DIR = path.join(ROOT_DIR, "public");
const DATABASE_DIR = path.join(ROOT_DIR, "database");
const UPLOAD_DIR = path.join(ROOT_DIR, "uploads");
const DB_PATH = path.join(DATABASE_DIR, "dashboard.db");
const ACTIVE_WORKBOOK = path.join(UPLOAD_DIR, "active-market-data.xlsx");
const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

fs.mkdirSync(DATABASE_DIR, { recursive: true });
fs.mkdirSync(UPLOAD_DIR, { recursive: true });
fs.mkdirSync(PUBLIC_DIR, { recursive: true });

const db = new DatabaseSync(DB_PATH);
const app = express();
const upload = multer({
  dest: UPLOAD_DIR,
  limits: {
    fileSize: MAX_UPLOAD_BYTES
  },
  fileFilter(_req, file, cb) {
    if (path.extname(file.originalname).toLowerCase() !== ".xlsx") {
      cb(new Error("Only .xlsx files are accepted."));
      return;
    }

    cb(null, true);
  }
});

const DEFAULT_MACRO_METRICS = [
  ["headline-inflation", "fa-solid fa-cart-shopping", "Headline Inflation", "Mar 2026", "15.38%"],
  ["food-inflation", "fa-solid fa-bowl-food", "Food Inflation", "Mar 2026", "14.31%"],
  ["core-inflation", "fa-solid fa-bullseye", "Core Inflation", "Mar 2026", "16.21%"],
  ["real-gdp-q4", "fa-solid fa-chart-line", "Real GDP Growth", "Q4 2025", "4.07%"],
  ["real-gdp-fy", "fa-solid fa-chart-column", "Real GDP Growth", "FY 2025", "3.87%"],
  ["pmi", "fa-solid fa-industry", "PMI", "Mar 2026", "51.9"],
  ["oil-production", "fa-solid fa-oil-well", "Oil Production", "Mar 2026", "1.546 mbpd"]
];

const DEFAULT_NEWS = [
  ["International", "Oil & Gas", "OPEC+ supply discipline remains a key market driver as traders balance gradual production increases against resilient crude demand and ongoing geopolitical risk."],
  ["International", "Supply / Demand", "Refinery maintenance schedules and shifting product inventories continue to shape near-term crude balances and regional price spreads."],
  ["Africa", "Refining", "African refiners are adjusting crude runs and product procurement as local demand, import economics and freight costs diverge across regional markets."],
  ["Africa", "FX / Macro", "Currency liquidity and inflation pressures remain important watchpoints for regional fuel pricing, working capital and trade settlement."],
  ["Nigeria", "Oil & Gas", "The 700,000 bpd Dangote refinery utilization rate dropped to 71% in July after operating near full capacity for three consecutive months, amid weaker domestic fuel demand, higher local prices and a renewed increase in imports."],
  ["Nigeria", "Oil & Gas", "Domestic crude supply, terminal availability and export programme changes remain key variables for Nigerian production and physical market participants."]
];

const DEFAULT_RISK_REGISTER = [
  ["Capital Adequacy Risk", "Capital ratios could weaken under stress or rapid balance-sheet growth.", "Maintain capital buffers and monitor internal limits monthly.", "Major", "unchanged", "CFO"],
  ["Legal and Contract Management Risk", "Contract disputes or weak terms may create loss, delay or unenforceable obligations.", "Use approved templates, legal review and a central contract register.", "Moderate", "unchanged", "General Counsel"],
  ["Counterparty Default Risk", "A customer or trading counterparty may default and create receivable losses.", "Apply counterparty limits, collateral requirements and enhanced monitoring.", "Major", "increased", "Chief Risk Officer"],
  ["Project Selection and Planning Risk", "Poor project selection or planning may increase cost and delay delivery.", "Use stage-gate approval, feasibility checks and milestone reviews.", "Moderate", "unchanged", "COO"],
  ["Market Opportunity Risk", "Missed or mispriced opportunities may reduce earnings and market share.", "Use market intelligence, approval thresholds and scenario review.", "Moderate", "reduced", "Commercial Director"]
];

const DEFAULT_MANAGEMENT_ACTIONS = [
  ["takeaway", "Crude prices remain firm as geopolitical premium offsets softer demand signals."],
  ["takeaway", "Supply disruption and geopolitical indicators are the main drivers of current risk."],
  ["takeaway", "OPEC+ compliance remains supportive, while refined-product prices remain firm."],
  ["takeaway", "Company exposure is manageable, with counterparty and freight movements on watch."],
  ["recommended", "Review near-term crude and refined-product hedge coverage."],
  ["recommended", "Monitor refined-product price movement and freight sensitivity."],
  ["recommended", "Reassess counterparty limits and collateral requirements for watched accounts."],
  ["recommended", "Validate terminal capacity, laycan flexibility and sanctions-screening controls."]
];

const DEFAULT_CATEGORY_RATINGS = [
  ["market", "High"],
  ["macro", "High"],
  ["company", "Moderate"]
];

function nowIso() {
  return new Date().toISOString();
}

function initDatabase() {
  db.exec(`
    PRAGMA journal_mode = WAL;

    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS market_data_uploads (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      original_filename TEXT NOT NULL,
      stored_filename TEXT NOT NULL,
      uploaded_at TEXT NOT NULL,
      uploaded_by INTEGER,
      record_count INTEGER NOT NULL DEFAULT 0,
      mapped_kri_count INTEGER NOT NULL DEFAULT 0,
      total_kri_count INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL,
      is_active INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY (uploaded_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS macro_metrics (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      metric_key TEXT NOT NULL UNIQUE,
      icon_class TEXT NOT NULL,
      metric_name TEXT NOT NULL,
      period TEXT NOT NULL,
      value TEXT NOT NULL,
      sort_order INTEGER NOT NULL,
      updated_at TEXT NOT NULL,
      updated_by INTEGER,
      FOREIGN KEY (updated_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS news_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      region TEXT NOT NULL,
      section TEXT NOT NULL,
      content TEXT NOT NULL,
      sort_order INTEGER NOT NULL,
      updated_at TEXT NOT NULL,
      updated_by INTEGER,
      FOREIGN KEY (updated_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS risk_register (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      risk_category TEXT NOT NULL,
      risk_event TEXT NOT NULL,
      mitigant TEXT NOT NULL,
      materiality TEXT NOT NULL,
      trend TEXT NOT NULL,
      risk_owner TEXT NOT NULL,
      sort_order INTEGER NOT NULL,
      updated_at TEXT NOT NULL,
      updated_by INTEGER,
      FOREIGN KEY (updated_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS management_actions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      action_type TEXT NOT NULL,
      content TEXT NOT NULL,
      sort_order INTEGER NOT NULL,
      updated_at TEXT NOT NULL,
      updated_by INTEGER,
      FOREIGN KEY (updated_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS risk_categories (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      category TEXT NOT NULL UNIQUE,
      rating TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      updated_by INTEGER,
      FOREIGN KEY (updated_by) REFERENCES users(id)
    );
  `);
}

async function seedAdminUser() {
  const row = db.prepare("SELECT COUNT(*) AS count FROM users WHERE username = ?").get("admin");

  if (row.count > 0) {
    return;
  }

  const hash = await bcrypt.hash("Password123", 12);
  db.prepare(`
    INSERT INTO users (username, password_hash, role, created_at)
    VALUES (?, ?, ?, ?)
  `).run("admin", hash, "admin", nowIso());
}

function seedEditableContent() {
  seedRows("macro_metrics", DEFAULT_MACRO_METRICS, (row, index) => (
    db.prepare(`
      INSERT INTO macro_metrics
        (metric_key, icon_class, metric_name, period, value, sort_order, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(row[0], row[1], row[2], row[3], row[4], index + 1, nowIso())
  ));

  seedRows("news_items", DEFAULT_NEWS, (row, index) => (
    db.prepare(`
      INSERT INTO news_items (region, section, content, sort_order, updated_at)
      VALUES (?, ?, ?, ?, ?)
    `).run(row[0], row[1], row[2], index + 1, nowIso())
  ));

  seedRows("risk_register", DEFAULT_RISK_REGISTER, (row, index) => (
    db.prepare(`
      INSERT INTO risk_register
        (risk_category, risk_event, mitigant, materiality, trend, risk_owner, sort_order, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(row[0], row[1], row[2], row[3], row[4], row[5], index + 1, nowIso())
  ));

  seedRows("management_actions", DEFAULT_MANAGEMENT_ACTIONS, (row, index) => (
    db.prepare(`
      INSERT INTO management_actions (action_type, content, sort_order, updated_at)
      VALUES (?, ?, ?, ?)
    `).run(row[0], row[1], index + 1, nowIso())
  ));

  seedRows("risk_categories", DEFAULT_CATEGORY_RATINGS, (row) => (
    db.prepare(`
      INSERT INTO risk_categories (category, rating, updated_at)
      VALUES (?, ?, ?)
    `).run(row[0], row[1], nowIso())
  ));
}

function seedRows(table, rows, insertRow) {
  const count = db.prepare(`SELECT COUNT(*) AS count FROM ${table}`).get().count;

  if (count > 0) {
    return;
  }

  rows.forEach(insertRow);
}

function requireAdmin(req, res, next) {
  if (req.session && req.session.user && req.session.user.role === "admin") {
    next();
    return;
  }

  res.status(401).json({ error: "Unauthorized" });
}

function currentUserId(req) {
  return req.session && req.session.user ? req.session.user.id : null;
}

function parseWorkbookFile(filePath, sourceName) {
  const workbook = XLSX.readFile(filePath, {
    cellDates: false
  });
  const workbookData = {
    records: globalThis.OilRiskExcel.workbookToRecords(workbook),
    plattsMarketData: globalThis.OilRiskExcel.extractPlattsMarketData(workbook),
    coreExportData: globalThis.OilRiskExcel.parseCoreExportSheet(workbook)
  };
  const normalized = globalThis.OilRiskExcel.normalizeWorkbookRecords(workbookData.records, {
    sourceType: "excel",
    sourceLabel: "Excel",
    sourceName,
    plattsMarketData: workbookData.plattsMarketData,
    coreExportData: workbookData.coreExportData
  });

  normalized.source.lastRefreshed = nowIso();
  return normalized;
}

function validateWorkbookFile(filePath) {
  const workbook = XLSX.readFile(filePath, {
    cellDates: false
  });
  const sheetNames = workbook.SheetNames || [];
  const allSheetText = collectWorkbookText(workbook);
  const normalizedSheetNames = sheetNames.map(normalizeLoose);
  const hasUomSheet = normalizedSheetNames.includes("ciresultsuom");
  const hasResultsSheet = normalizedSheetNames.includes("ciresults") ||
    normalizedSheetNames.includes("marketrisk");
  const coreExportData = globalThis.OilRiskExcel.parseCoreExportSheet(workbook);
  const requiredSymbols = ["PCAAS00", "PAAAM00", "AAVJI00", "PGABM00", "PCABC00", "PCACG00", "PJAAV00"];
  const missingSymbols = requiredSymbols.filter((symbol) => !allSheetText.includes(symbol));
  const missing = [];

  if (!hasResultsSheet) {
    missing.push("CI.Results or Market Risk worksheet");
  }

  if (!hasUomSheet) {
    missing.push("CI.Results_UOM worksheet");
  }

  if (!coreExportData.length) {
    missing.push("Core_Export_Data or Crude Supply Risk series: ZNR734 and PCAAS00");
  }

  if (missingSymbols.length) {
    missing.push(`required series: ${missingSymbols.join(", ")}`);
  }

  if (missing.length) {
    const error = new Error(`Upload rejected. Missing ${missing.join("; ")}.`);
    error.validationError = true;
    throw error;
  }

  const records = globalThis.OilRiskExcel.workbookToRecords(workbook);
  const plattsMarketData = globalThis.OilRiskExcel.extractPlattsMarketData(workbook);
  const normalized = globalThis.OilRiskExcel.normalizeWorkbookRecords(records, {
    sourceName: "Validation",
    plattsMarketData,
    coreExportData
  });

  return normalized.importInfo;
}

function collectWorkbookText(workbook) {
  return (workbook.SheetNames || []).map((sheetName) => {
    const rows = XLSX.utils.sheet_to_json(workbook.Sheets[sheetName], {
      header: 1,
      defval: "",
      raw: false
    });

    return rows.flat().join(" ");
  }).join(" ").toUpperCase();
}

function normalizeLoose(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function getActiveUpload() {
  return db.prepare(`
    SELECT *
    FROM market_data_uploads
    WHERE is_active = 1
    ORDER BY uploaded_at DESC
    LIMIT 1
  `).get() || null;
}

function getDashboardData() {
  if (fs.existsSync(ACTIVE_WORKBOOK)) {
    const activeUpload = getActiveUpload();
    const data = parseWorkbookFile(
      ACTIVE_WORKBOOK,
      activeUpload ? activeUpload.original_filename : "active-market-data.xlsx"
    );

    if (activeUpload) {
      data.source.lastRefreshed = activeUpload.uploaded_at;
      data.source.activeUpload = {
        originalFilename: activeUpload.original_filename,
        uploadedAt: activeUpload.uploaded_at,
        recordCount: activeUpload.record_count,
        mappedKriCount: activeUpload.mapped_kri_count,
        totalKriCount: activeUpload.total_kri_count
      };
    }

    return data;
  }

  const data = globalThis.OilRiskData.cloneDashboardData(globalThis.dashboardData);
  data.source.type = "demo";
  data.source.label = "Demo";
  data.source.name = "Realistic development sample";
  return data;
}

function getMacroMetrics() {
  const rows = db.prepare(`
    SELECT id, metric_key, icon_class, metric_name, period, value, updated_at, updated_by
    FROM macro_metrics
    ORDER BY sort_order, id
  `).all();

  return {
    sectionTitle: "PRICES, GROWTH & REAL ECONOMY",
    metrics: rows.map((row) => ({
      id: row.id,
      key: row.metric_key,
      iconClass: row.icon_class,
      title: row.metric_name,
      period: row.period,
      value: row.value,
      updatedAt: row.updated_at,
      updatedBy: row.updated_by
    }))
  };
}

function getNewsItems() {
  const rows = db.prepare(`
    SELECT id, region, section, content, sort_order
    FROM news_items
    ORDER BY sort_order, id
  `).all();
  const regions = [];

  rows.forEach((row) => {
    let region = regions.find((item) => item.title === row.region);

    if (!region) {
      region = {
        id: slugify(row.region),
        title: row.region,
        sections: []
      };
      regions.push(region);
    }

    let section = region.sections.find((item) => item.title === row.section);

    if (!section) {
      section = {
        id: `${region.id}-${slugify(row.section)}`,
        title: row.section,
        items: []
      };
      region.sections.push(section);
    }

    section.items.push({
      id: row.id,
      headline: row.content
    });
  });

  return regions;
}

function getRiskRegisterRows() {
  return db.prepare(`
    SELECT
      id,
      risk_category AS riskCategory,
      risk_event AS riskEvent,
      mitigant,
      materiality,
      trend AS movement,
      risk_owner AS riskOwner,
      updated_at AS updatedAt,
      updated_by AS updatedBy
    FROM risk_register
    ORDER BY sort_order, id
  `).all();
}

function getManagementActions() {
  const rows = db.prepare(`
    SELECT id, action_type, content, sort_order, updated_at, updated_by
    FROM management_actions
    ORDER BY sort_order, id
  `).all();

  return {
    takeaways: rows.filter((row) => row.action_type === "takeaway").map((row) => row.content),
    recommendedActions: rows.filter((row) => row.action_type === "recommended").map((row) => row.content),
    rows
  };
}

function getRiskCategories() {
  return db.prepare(`
    SELECT id, category, rating, updated_at, updated_by
    FROM risk_categories
    ORDER BY id
  `).all();
}

function slugify(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function replaceMacroMetrics(payload, userId) {
  const metrics = Array.isArray(payload && payload.metrics) ? payload.metrics : [];
  const timestamp = nowIso();

  metrics.forEach((metric, index) => {
    const id = Number(metric.id);

    if (id) {
      db.prepare(`
        UPDATE macro_metrics
        SET metric_name = ?, period = ?, value = ?, sort_order = ?, updated_at = ?, updated_by = ?
        WHERE id = ?
      `).run(metric.title || "", metric.period || "", metric.value || "", index + 1, timestamp, userId, id);
    }
  });
}

function replaceNewsItems(items, userId) {
  const timestamp = nowIso();
  let sortOrder = 1;

  db.exec("BEGIN");
  try {
    db.prepare("DELETE FROM news_items").run();
    (Array.isArray(items) ? items : []).forEach((region) => {
      (region.sections || []).forEach((section) => {
        (section.items || []).forEach((item) => {
          const content = String(item.headline || "").trim();

          if (!content) {
            return;
          }

          db.prepare(`
            INSERT INTO news_items (region, section, content, sort_order, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?, ?)
          `).run(region.title || "", section.title || "", content, sortOrder, timestamp, userId);
          sortOrder += 1;
        });
      });
    });
    db.exec("COMMIT");
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}

function replaceRiskRegisterRows(rows, userId) {
  const timestamp = nowIso();

  db.exec("BEGIN");
  try {
    db.prepare("DELETE FROM risk_register").run();
    (Array.isArray(rows) ? rows : []).forEach((row, index) => {
      db.prepare(`
        INSERT INTO risk_register
          (risk_category, risk_event, mitigant, materiality, trend, risk_owner, sort_order, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        row.riskCategory || "",
        row.riskEvent || "",
        row.mitigant || "",
        row.materiality || "Moderate",
        row.movement || "unchanged",
        row.riskOwner || "",
        index + 1,
        timestamp,
        userId
      );
    });
    db.exec("COMMIT");
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}

function replaceManagementActions(payload, userId) {
  const timestamp = nowIso();
  const rows = [
    ...(Array.isArray(payload && payload.takeaways) ? payload.takeaways.map((content) => ["takeaway", content]) : []),
    ...(Array.isArray(payload && payload.recommendedActions) ? payload.recommendedActions.map((content) => ["recommended", content]) : [])
  ].filter((row) => String(row[1] || "").trim());

  db.exec("BEGIN");
  try {
    db.prepare("DELETE FROM management_actions").run();
    rows.forEach((row, index) => {
      db.prepare(`
        INSERT INTO management_actions (action_type, content, sort_order, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?)
      `).run(row[0], row[1], index + 1, timestamp, userId);
    });
    db.exec("COMMIT");
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}

function updateRiskCategory(category, rating, userId) {
  db.prepare(`
    UPDATE risk_categories
    SET rating = ?, updated_at = ?, updated_by = ?
    WHERE category = ?
  `).run(rating, nowIso(), userId, category);
}

app.use(express.json({ limit: "1mb" }));
app.use(session({
  name: "oilRiskAdmin",
  secret: SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    sameSite: "lax",
    secure: false
  }
}));
app.use(express.static(PUBLIC_DIR));

app.post("/api/auth/login", async (req, res) => {
  try {
    const username = String(req.body && req.body.username || "").trim();
    const password = String(req.body && req.body.password || "");
    const user = db.prepare("SELECT * FROM users WHERE username = ?").get(username);
    const isValid = user ? await bcrypt.compare(password, user.password_hash) : false;

    if (!isValid) {
      res.status(401).json({ error: "Invalid username or password." });
      return;
    }

    req.session.user = {
      id: user.id,
      username: user.username,
      role: user.role
    };
    res.json({
      authenticated: true,
      role: user.role
    });
  } catch (error) {
    console.error("Login failed:", error);
    res.status(500).json({ error: "Unable to log in. Please try again." });
  }
});

app.post("/api/auth/logout", (req, res) => {
  req.session.destroy(() => {
    res.clearCookie("oilRiskAdmin");
    res.json({ authenticated: false });
  });
});

app.get("/api/auth/status", (req, res) => {
  if (req.session && req.session.user) {
    res.json({
      authenticated: true,
      role: req.session.user.role,
      username: req.session.user.username
    });
    return;
  }

  res.json({ authenticated: false });
});

app.get("/api/market-data", (_req, res) => {
  try {
    res.json(getDashboardData());
  } catch (error) {
    console.error("Unable to load market data:", error);
    res.status(500).json({ error: "Unable to load market data." });
  }
});

app.get("/api/admin/market-data-status", requireAdmin, (_req, res) => {
  res.json({
    activeUpload: getActiveUpload()
  });
});

app.post("/api/admin/upload-market-data", requireAdmin, upload.single("workbook"), (req, res) => {
  if (!req.file) {
    res.status(400).json({ error: "Please select an .xlsx workbook." });
    return;
  }

  const tempPath = req.file.path;

  try {
    const importInfo = validateWorkbookFile(tempPath);
    const parsedData = parseWorkbookFile(tempPath, req.file.originalname);
    const storedName = "active-market-data.xlsx";

    fs.renameSync(tempPath, ACTIVE_WORKBOOK);
    db.prepare("UPDATE market_data_uploads SET is_active = 0 WHERE is_active = 1").run();
    db.prepare(`
      INSERT INTO market_data_uploads
        (original_filename, stored_filename, uploaded_at, uploaded_by, record_count, mapped_kri_count, total_kri_count, status, is_active)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    `).run(
      req.file.originalname,
      storedName,
      nowIso(),
      currentUserId(req),
      importInfo.recordsRead || 0,
      importInfo.mappedKris || 0,
      Object.keys(parsedData.kris || {}).length,
      "active"
    );

    res.json({
      message: "Workbook uploaded successfully.",
      importInfo,
      data: getDashboardData(),
      activeUpload: getActiveUpload()
    });
  } catch (error) {
    if (fs.existsSync(tempPath)) {
      fs.unlinkSync(tempPath);
    }

    if (error.validationError) {
      res.status(400).json({ error: error.message });
      return;
    }

    console.error("Upload failed:", error);
    res.status(500).json({ error: "Unable to upload workbook. Please try again." });
  }
});

app.post("/api/admin/reprocess-market-data", requireAdmin, (_req, res) => {
  try {
    if (!fs.existsSync(ACTIVE_WORKBOOK)) {
      res.status(404).json({ error: "No active workbook has been uploaded." });
      return;
    }

    const data = getDashboardData();
    res.json({
      message: "Market data reprocessed.",
      data,
      activeUpload: getActiveUpload()
    });
  } catch (error) {
    console.error("Reprocess failed:", error);
    res.status(500).json({ error: "Unable to reprocess market data." });
  }
});

app.get("/api/macro-metrics", (_req, res) => res.json(getMacroMetrics()));
app.put("/api/admin/macro-metrics", requireAdmin, (req, res) => {
  try {
    replaceMacroMetrics(req.body, currentUserId(req));
    res.json(getMacroMetrics());
  } catch (error) {
    console.error("Unable to save macro metrics:", error);
    res.status(500).json({ error: "Unable to save Macro Metrics. Please try again." });
  }
});
app.put("/api/admin/macro-metrics/:id", requireAdmin, (req, res) => {
  try {
    const id = Number(req.params.id);
    db.prepare(`
      UPDATE macro_metrics
      SET metric_name = ?, period = ?, value = ?, updated_at = ?, updated_by = ?
      WHERE id = ?
    `).run(req.body.title || "", req.body.period || "", req.body.value || "", nowIso(), currentUserId(req), id);
    res.json(getMacroMetrics());
  } catch (error) {
    console.error("Unable to save macro metric:", error);
    res.status(500).json({ error: "Unable to save Macro Metric. Please try again." });
  }
});

app.get("/api/news", (_req, res) => res.json(getNewsItems()));
app.put("/api/admin/news", requireAdmin, (req, res) => {
  try {
    replaceNewsItems(req.body.items || req.body, currentUserId(req));
    res.json(getNewsItems());
  } catch (error) {
    console.error("Unable to save news:", error);
    res.status(500).json({ error: "Unable to save Trending News. Please try again." });
  }
});
app.post("/api/admin/news", requireAdmin, (req, res) => {
  try {
    const maxSort = db.prepare("SELECT COALESCE(MAX(sort_order), 0) AS sort_order FROM news_items").get().sort_order;
    db.prepare(`
      INSERT INTO news_items (region, section, content, sort_order, updated_at, updated_by)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(req.body.region || "", req.body.section || "", req.body.content || "", maxSort + 1, nowIso(), currentUserId(req));
    res.json(getNewsItems());
  } catch (error) {
    console.error("Unable to create news item:", error);
    res.status(500).json({ error: "Unable to save Trending News. Please try again." });
  }
});
app.put("/api/admin/news/:id", requireAdmin, (req, res) => {
  try {
    db.prepare(`
      UPDATE news_items
      SET region = ?, section = ?, content = ?, updated_at = ?, updated_by = ?
      WHERE id = ?
    `).run(req.body.region || "", req.body.section || "", req.body.content || "", nowIso(), currentUserId(req), Number(req.params.id));
    res.json(getNewsItems());
  } catch (error) {
    console.error("Unable to update news item:", error);
    res.status(500).json({ error: "Unable to save Trending News. Please try again." });
  }
});
app.delete("/api/admin/news/:id", requireAdmin, (req, res) => {
  try {
    db.prepare("DELETE FROM news_items WHERE id = ?").run(Number(req.params.id));
    res.json(getNewsItems());
  } catch (error) {
    console.error("Unable to delete news item:", error);
    res.status(500).json({ error: "Unable to save Trending News. Please try again." });
  }
});

app.get("/api/risk-register", (_req, res) => res.json(getRiskRegisterRows()));
app.put("/api/admin/risk-register", requireAdmin, (req, res) => {
  try {
    replaceRiskRegisterRows(req.body.rows || req.body, currentUserId(req));
    res.json(getRiskRegisterRows());
  } catch (error) {
    console.error("Unable to save risk register:", error);
    res.status(500).json({ error: "Unable to save Risk Register entry. Please try again." });
  }
});
app.post("/api/admin/risk-register", requireAdmin, (req, res) => {
  try {
    const maxSort = db.prepare("SELECT COALESCE(MAX(sort_order), 0) AS sort_order FROM risk_register").get().sort_order;
    db.prepare(`
      INSERT INTO risk_register
        (risk_category, risk_event, mitigant, materiality, trend, risk_owner, sort_order, updated_at, updated_by)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      req.body.riskCategory || "",
      req.body.riskEvent || "",
      req.body.mitigant || "",
      req.body.materiality || "Moderate",
      req.body.movement || "unchanged",
      req.body.riskOwner || "",
      maxSort + 1,
      nowIso(),
      currentUserId(req)
    );
    res.json(getRiskRegisterRows());
  } catch (error) {
    console.error("Unable to create risk register row:", error);
    res.status(500).json({ error: "Unable to save Risk Register entry. Please try again." });
  }
});
app.put("/api/admin/risk-register/:id", requireAdmin, (req, res) => {
  try {
    db.prepare(`
      UPDATE risk_register
      SET risk_category = ?, risk_event = ?, mitigant = ?, materiality = ?, trend = ?, risk_owner = ?, updated_at = ?, updated_by = ?
      WHERE id = ?
    `).run(
      req.body.riskCategory || "",
      req.body.riskEvent || "",
      req.body.mitigant || "",
      req.body.materiality || "Moderate",
      req.body.movement || "unchanged",
      req.body.riskOwner || "",
      nowIso(),
      currentUserId(req),
      Number(req.params.id)
    );
    res.json(getRiskRegisterRows());
  } catch (error) {
    console.error("Unable to update risk register row:", error);
    res.status(500).json({ error: "Unable to save Risk Register entry. Please try again." });
  }
});
app.delete("/api/admin/risk-register/:id", requireAdmin, (req, res) => {
  try {
    db.prepare("DELETE FROM risk_register WHERE id = ?").run(Number(req.params.id));
    res.json(getRiskRegisterRows());
  } catch (error) {
    console.error("Unable to delete risk register row:", error);
    res.status(500).json({ error: "Unable to save Risk Register entry. Please try again." });
  }
});

app.get("/api/management-actions", (_req, res) => res.json(getManagementActions()));
app.put("/api/admin/management-actions", requireAdmin, (req, res) => {
  try {
    replaceManagementActions(req.body, currentUserId(req));
    res.json(getManagementActions());
  } catch (error) {
    console.error("Unable to save management actions:", error);
    res.status(500).json({ error: "Unable to save Management Actions. Please try again." });
  }
});
app.post("/api/admin/management-actions", requireAdmin, (req, res) => {
  try {
    const maxSort = db.prepare("SELECT COALESCE(MAX(sort_order), 0) AS sort_order FROM management_actions").get().sort_order;
    db.prepare(`
      INSERT INTO management_actions (action_type, content, sort_order, updated_at, updated_by)
      VALUES (?, ?, ?, ?, ?)
    `).run(req.body.actionType || "takeaway", req.body.content || "", maxSort + 1, nowIso(), currentUserId(req));
    res.json(getManagementActions());
  } catch (error) {
    console.error("Unable to create management action:", error);
    res.status(500).json({ error: "Unable to save Management Actions. Please try again." });
  }
});
app.put("/api/admin/management-actions/:id", requireAdmin, (req, res) => {
  try {
    db.prepare(`
      UPDATE management_actions
      SET action_type = ?, content = ?, updated_at = ?, updated_by = ?
      WHERE id = ?
    `).run(req.body.actionType || "takeaway", req.body.content || "", nowIso(), currentUserId(req), Number(req.params.id));
    res.json(getManagementActions());
  } catch (error) {
    console.error("Unable to update management action:", error);
    res.status(500).json({ error: "Unable to save Management Actions. Please try again." });
  }
});
app.delete("/api/admin/management-actions/:id", requireAdmin, (req, res) => {
  try {
    db.prepare("DELETE FROM management_actions WHERE id = ?").run(Number(req.params.id));
    res.json(getManagementActions());
  } catch (error) {
    console.error("Unable to delete management action:", error);
    res.status(500).json({ error: "Unable to save Management Actions. Please try again." });
  }
});

app.get("/api/risk-categories", (_req, res) => res.json(getRiskCategories()));
app.put("/api/admin/risk-categories/:id", requireAdmin, (req, res) => {
  try {
    updateRiskCategory(req.params.id, req.body.rating || "Moderate", currentUserId(req));
    res.json(getRiskCategories());
  } catch (error) {
    console.error("Unable to save risk category:", error);
    res.status(500).json({ error: "Unable to save Risk by Category. Please try again." });
  }
});

app.use((_req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, "index.html"));
});

async function start() {
  initDatabase();
  await seedAdminUser();
  seedEditableContent();

  app.listen(PORT, () => {
    console.log(`Daily Oil Trading Risk Dashboard running at http://localhost:${PORT}`);
  });
}

start().catch((error) => {
  console.error("Unable to start server:", error);
  process.exit(1);
});
