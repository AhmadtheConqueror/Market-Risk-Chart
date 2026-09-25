# Daily Oil Trading Risk Dashboard — FastAPI Backend

Production-ready backend API service for the Daily Oil Trading Risk Dashboard, implemented with Python, FastAPI, SQLAlchemy, Alembic, and Supabase PostgreSQL.

## Phase 6 AI Analysis

Gemini is an interpretation layer over verified backend context. The backend
builds that context from market observations and calculations, official macro
records, the risk register and active dashboard content. It validates the
strict structured response, persists successful and failed attempts, and keeps
failed attempts from replacing the latest successful result. Missing values,
unavailable instruments, proxy qualifications and insufficient history remain
explicit. The chatbot endpoint remains unavailable until a later phase.

Configure the provider only in `backend/.env`:

```text
AI_PROVIDER=gemini
GEMINI_API_KEY=<server-only key>
GEMINI_MODEL=gemini-3.8-flash
```

## Final MVP Hybrid Market Data

`POST /api/market/import-excel` accepts the controlled `.xlsx` upload, validates
the `Market Risk` sheet and persists normalized physical benchmark observations
with `provider=internal_excel`, actual assessment dates, Platts symbols,
retrieval timestamps and benchmark definitions. The response is a compact
summary containing rows read/valid/stored/updated/rejected, affected
instruments, date range and validation errors.

Source resolution is explicit: OilPriceAPI is preferred for Brent and WTI;
the internal workbook is preferred for Forcados, Naphtha, Gasoil, Gasoline and
Jet. Preferred-source absence is unavailable/stale, not a reason to silently
fall back to a different benchmark. Existing observation uniqueness provides
idempotent repeat uploads.

## Automated Energy News

Migration `0004_news_items` creates the dedicated `news_items` table. The
whitelisted providers are EIA RSS, OPEC official press releases, NUPRC and
NNPC Limited. `POST /api/news/refresh` fetches them independently, validates
publication dates and URLs, classifies each item into `international`,
`africa` or `nigeria`, applies a restrained topic vocabulary, and upserts by
unique external URL. Only short snippets are stored; full articles are not.

`GET /api/news/latest?region=nigeria&limit=5` returns active verified items
from the last seven days. Successful source items are retained when another
source fails. Gemini receives a maximum of 20 recent news records through the
authoritative context builder; news refresh never triggers Gemini automatically.

Source failures are surfaced individually. In the current controlled probe,
the OPEC page returned HTTP 403 to the backend client while EIA, NUPRC and NNPC
loaded successfully; the service does not fall back to non-whitelisted sources.

---

## Architecture Overview

```text
Browser Dashboard (HTML/JS)
       ↓
FastAPI Backend (/api)
       ↓
Supabase PostgreSQL
       ↓
Market Data Provider (Generic Abstraction: OilPriceAPI, Argus, etc.)
       ↓
Calculation Engine (Z-scores, 90D window, spreads, conversions)
       ↓
AI Analysis / Chatbot (Scaffold: Gemini, OpenAI)
```

---

## Directory Structure

```text
backend/
├── alembic.ini                   # Database migration configuration
├── alembic/
│   ├── env.py                   # Alembic environment runner
│   └── versions/
│       ├── 0001_initial_schema.py # Initial migration for core PostgreSQL tables
│       └── 0002_macro_indicators_history.py # Historical macro indicator uniqueness
├── app/
│   ├── __init__.py
│   ├── config.py                # Pydantic Settings (reads backend/.env)
│   ├── main.py                  # FastAPI app factory, CORS, and routers
│   ├── api/                     # API routers
│   │   ├── ai.py                # AI analysis & chat scaffold endpoints
│   │   ├── dashboard.py         # Complete dashboard snapshot endpoint
│   │   ├── health.py            # Health check endpoint
│   │   ├── macro.py             # Official macro refresh/latest/history endpoints
│   │   └── market.py            # Instruments, latest, and history endpoints
│   ├── db/                      # Database engine, session, and declarative Base
│   ├── models/                  # SQLAlchemy ORM models (7 PostgreSQL tables)
│   │   ├── ai.py                # MarketSnapshot, AIAnalysis
│   │   ├── macro.py             # MacroIndicator
│   │   ├── market.py            # MarketInstrument, MarketObservation
│   │   └── risk.py              # RiskRegisterEntry (simplified), DashboardContent
│   ├── providers/               # Generic provider abstractions
│   │   ├── base.py              # MarketDataProvider & AIProvider ABCs
│   │   ├── ai/                  # Gemini & OpenAI scaffold providers
│   │   ├── macro/               # NBS, Stanbic/S&P PMI, and NUPRC providers
│   │   └── market/              # OilPriceAPI scaffold provider
│   ├── schemas/                 # Pydantic request/response schemas
│   └── services/
│       ├── calculations.py      # Statistical and financial calculation engine
│       └── macro_ingestion.py   # Macro validation, freshness, and idempotent upserts
├── scripts/
│   └── seed.py                  # Canonical instrument & test fixture seeder
├── tests/                       # Deterministic test suite
├── .env.example
├── README.md
└── requirements.txt
```

---

## Database Schema (7 PostgreSQL Tables)

1. `market_instruments`: Canonical oil instruments (`brent`, `wti`, `forcados`, `naphtha`, `gasoil`, `gasoline`, `jet`), units, categories, provider symbol mappings.
2. `market_observations`: Auditable price observations with `(instrument_id, provider, provider_symbol, assessment_date)` uniqueness and composite index.
3. `market_snapshots`: Saved snapshots of calculated dashboard state.
4. `ai_analyses`: Structured AI briefs, threats, desk recommendations, and executive summaries.
5. `macro_indicators`: Official-source macro observations. Phase 5 uniqueness is `(indicator_key, reporting_period, source)` so historical releases can coexist and repeated refreshes are idempotent. Useful fields include `value`, `unit`, `source_url`, `published_at`, `retrieved_at`, `status`, and `metadata_json`.
6. `risk_register`: Simplified company risk register containing:
   - `id`
   - `risk_category`
   - `materiality` (`Low`, `Moderate`, `Major`, `Catastrophic`)
   - `trend` (`increasing`, `unchanged`, `decreasing`)
   - `risk_owner`
   - `display_order`
   - `active`
   - `created_at`, `updated_at`
   *(No `risk_event` or `mitigant`)*
7. `dashboard_content`: Executive narrative summaries and watch items.

---

## Environment Configuration

Place your production or development credentials in `backend/.env`.

See `backend/.env.example`:

```bash
# Database Configuration (Supabase PostgreSQL)
DATABASE_URL=postgresql+psycopg://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
ENVIRONMENT=development
FRONTEND_ORIGIN=http://localhost:3000

# AI Provider Configuration
AI_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.8-flash
OPENAI_API_KEY=

# Market Data Provider Configuration (Scaffold in Phase 2)
MARKET_DATA_PROVIDER=oilpriceapi
OILPRICEAPI_KEY=
MARKET_DATA_API_KEY=
MARKET_DATA_BASE_URL=https://api.oilpriceapi.com/v1
```

> **Security Rule**: Never commit `backend/.env` or expose database credentials in browser JavaScript or client files.

---

## Migrations & Database Setup

To apply migrations to your configured database:

```powershell
# From project root:
py -m alembic -c backend/alembic.ini upgrade head
```

To seed canonical instruments into the database:

```powershell
# Seeds canonical instruments only (brent, wti, forcados, naphtha, gasoil, gasoline, jet):
py backend/scripts/seed.py
```

To populate isolated development demo fixture data (clearly tagged as test data):

```powershell
py backend/scripts/seed.py --include-dev-demo
```

---

## Running the API Server

Start the Uvicorn development server:

```powershell
py -m uvicorn app.main:app --reload --app-dir backend --port 8000
```

Interactive API documentation will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## API Endpoints

### 1. `GET /api/health`
Returns health check status and database connection state:
```json
{
  "status": "ok",
  "app": "Daily Oil Trading Risk Dashboard API",
  "environment": "development",
  "database": "connected"
}
```

### 2. `GET /api/market/instruments`
Returns canonical active market instruments:
```json
[
  {
    "id": 1,
    "instrument_key": "brent",
    "display_name": "Dated Brent",
    "unit": "USD/bbl",
    "category": "crude",
    "enabled": true
  }
]
```

### 3. `GET /api/market/latest`
Returns the latest normalized price observation for each instrument from Supabase PostgreSQL, including freshness status (`fresh` / `stale`), source timestamps, and raw unit values.

### 4. `GET /api/market/history?instrument=brent&days=90`
Returns historical dated price points for an instrument within the requested calendar day window from Supabase PostgreSQL. Includes `history_status` (`valid`, `insufficient_history`, or `unavailable`).

### 5. `POST /api/market/refresh`
Admin-triggered or scheduled live refresh endpoint. Requests latest prices from OilPriceAPI-owned instruments, performs idempotent upserts into `market_observations`, and returns an execution summary:
```json
{
  "provider": "oilpriceapi",
  "requested": 4,
  "stored": 0,
  "updated": 4,
  "skipped": 0,
  "failed": 0,
  "refreshedAt": "2026-09-24T12:54:01.738Z",
  "instruments": ["brent", "wti", "naphtha", "gasoil"],
  "message": null
}
```

### 6. `POST /api/market/import-excel`
Accepts the controlled workbook upload, validates the `Market Risk` sheet and
persists only configured physical benchmark observations. It returns an import
summary and does not return workbook contents.

### 7. `GET /api/dashboard/snapshot`
Returns the comprehensive dashboard state including:
- Instrument statistics (1D change, % change, 90D mean, 90D SD, z-scores, `history_status`)
- Outliers (`|z-score| >= 2.0σ`)
- Dynamic refined product conversions and Product-Brent crack spreads
- Active macro indicators
- Simplified risk register entries
- Latest completed AI analysis / briefing

### 8. `POST /api/macro/refresh`
Fetches the six canonical macro indicators from official publishers and upserts them into `macro_indicators`:
- NBS CPI: `headline_inflation`, `food_inflation`, `core_inflation`
- NBS GDP: `real_gdp_growth`
- Stanbic IBTC Bank / S&P Global PMI: `nigeria_pmi`
- NUPRC crude production: `crude_oil_production`

Response summary:
```json
{
  "requested": 6,
  "stored": 6,
  "updated": 0,
  "unchanged": 0,
  "failed": 0,
  "indicators": [],
  "errors": []
}
```

### 9. `GET /api/macro/latest`
Returns one response item for each canonical macro key. If no verified value exists, the item has `value: null`, `status: "unavailable"`, and `freshness_status: "unavailable"`.

### 10. `GET /api/macro/history?indicator=headline_inflation`
Returns stored observations for one canonical indicator, newest first.

### 11. `POST /api/ai/analyse`
Returns a standardized scaffold response (`unconfigured`) indicating external AI calls are reserved for future phases.

### 12. `POST /api/ai/chat`
Returns a standardized scaffold response (`unconfigured`) for conversational inquiries.

---

## Phase 5 Macro Source Rules

| Key | Official publisher | Definition | Unit | Frequency | Extraction method |
|---|---|---|---|---|---|
| `headline_inflation` | National Bureau of Statistics Nigeria | National all-items YoY CPI inflation | `%` | Monthly | Latest CPI ZIP Excel workbook, validated Table1 all-items YoY column |
| `food_inflation` | National Bureau of Statistics Nigeria | National food YoY inflation | `%` | Monthly | Latest CPI ZIP Excel workbook, validated Food YoY column |
| `core_inflation` | National Bureau of Statistics Nigeria | National all-items less farm produce and energy YoY inflation | `%` | Monthly | Latest CPI ZIP Excel workbook, validated Core YoY column |
| `real_gdp_growth` | National Bureau of Statistics Nigeria | Total real GDP YoY growth | `%` | Quarterly | Latest GDP ZIP Excel workbook, real GDP growth sheet, total constant-price GDP row |
| `nigeria_pmi` | Stanbic IBTC Bank / S&P Global | Headline seasonally adjusted PMI | `index` | Monthly | Latest valid public PDF, headline PMI value |
| `crude_oil_production` | NUPRC | Strict crude oil production excluding condensate, average daily production | `mbpd` | Monthly | Latest official NUPRC article, strict crude-only BPD converted to mbpd |

Macro freshness is frequency-aware. Monthly indicators are not stale merely because they were retrieved several days ago; freshness is based on the reporting period and expected publication cycle. GDP uses a quarterly cycle.

Fallback behavior is explicit: if extraction fails and a verified prior value exists, the prior reporting period is preserved and marked stale. If no verified prior value exists, the API returns unavailable with `value: null`. The backend never uses Google results, AI estimates, or hard-coded old values.

---

## Statistical Formulas & Business Logic

- **1D Change**: `current_value - previous_value`
- **1D % Change**: `(change / |previous_value|) * 100` (returns `None` if `previous_value == 0`)
- **90D Calendar Window**: Filtered to `[latest_date - 89 days, latest_date]`
- **90D Mean**: Sample arithmetic mean over valid finite numbers
- **90D Sample Standard Deviation**: `sqrt(sum((x - mean)^2) / (N - 1))` for `N >= 2`
- **Z-Score**: `(current_value - mean_90) / std_dev_90`
  - `+2.0σ`: 2 standard deviations above 90-day mean
  - `-2.0σ`: 2 standard deviations below 90-day mean
- **Zero Standard Deviation**: If `std_dev_90 == 0`, `z_score` is returned as `None` to prevent division by zero.
- **Approved Product Conversions**:
  - Naphtha: 8.90 bbl / mt
  - Gasoil: 7.44 bbl / mt
  - Gasoline: 8.33 bbl / mt
  - Jet: 7.70 bbl / mt
  - Formula: `USD/bbl = USD/mt / barrels_per_metric_ton`
  - Product Spread: `product_USD_per_bbl - brent_USD_per_bbl`
- **Missing Data Policy**:
  - `blank != 0`
  - No forward filling
  - No backward filling
  - No nearest-date substitution
  - Missing dates remain omitted from calculation

---

## Automated Tests

Run the deterministic test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -v
```

The macro tests mock official source HTML/ZIP/XLSX/PDF/article inputs. They do not depend on live websites.
