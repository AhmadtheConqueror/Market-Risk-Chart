# API Architecture

## Phase 6 Status

Gemini analysis is now available as an explicit interpretation layer. The
browser loads `GET /api/ai/latest` on normal page load and only runs Gemini
when the user selects **Refresh AI Analysis**. The backend builds the input
context from verified market, macro, risk-register and dashboard-content
records; browser-submitted prices or metrics are ignored.

`POST /api/ai/analyse` accepts an optional `force_refresh` flag, persists both
the verified input snapshot and the result in `ai_analyses`, and returns a
strict structured response. Failed attempts are retained for audit but never
replace the latest successful analysis. `/api/ai/chat` remains deliberately
unavailable until a later chatbot phase.

Gemini configuration is server-only:

```text
AI_PROVIDER=gemini
GEMINI_API_KEY=<server-only key>
GEMINI_MODEL=gemini-3.8-flash
```

The official `google-genai` SDK is used with JSON/Pydantic schema validation,
a bounded request timeout, and provider errors that do not expose credentials.

## Final MVP Hybrid Market Data Policy

Excel is an additional backend provider, never a browser calculation source.
The Admin upload control sends the workbook to `POST /api/market/import-excel`.
FastAPI validates the `Market Risk` sheet, normalizes supported Platts
observations, stores them in `market_observations` with
`provider=internal_excel`, and returns only an import summary.

| Instrument | Preferred source | Symbol / definition |
|---|---|---|
| Brent | OilPriceAPI | `BRENT_CRUDE_USD` / ICE Brent Crude Futures |
| WTI | OilPriceAPI | `WTI_USD` / WTI Crude Oil Futures |
| Forcados | Internal workbook | `PCABC00` / Forcados FOB Nigeria physical assessment |
| Naphtha | Internal workbook | `PAAAM00` / Naphtha FOB Rdam Barge physical assessment |
| Gasoil | Internal workbook | `AAVJI00` / Gasoil 0.1%S FOB Med Cargo physical assessment |
| Gasoline | Internal workbook | `PGABM00` / Gasoline Prem Unleaded 10ppmS FOB AR Barge physical assessment |
| Jet | Internal workbook | `PJAAV00` / Jet FOB NWE Cargo physical assessment |

The configured source is selected before calculations. A missing preferred
series is shown as unavailable/stale; the system does not silently fall back
to another benchmark or merge OilPriceAPI and workbook histories. Duplicate
uploads update the existing source/date record instead of creating duplicates.

## Automated Energy News MVP

The whitelisted news registry contains EIA RSS feeds, the official OPEC press
release page, NUPRC's official news API, and NNPC Limited's official insights
page. Providers normalize only title, external URL, publication time, a short
source excerpt, region, topic and audit metadata. Full articles are never
stored.

`POST /api/news/refresh` fetches each source independently, validates and
deduplicates by URL, then persists to `news_items`. A failed source does not
discard successful source items. `GET /api/news/latest` returns only active
verified items from the last seven days and supports `region`, `topic` and
`limit` filters.

The AI context includes at most 20 recent news records. Gemini is instructed to
treat them as attributed source context, keep facts separate from interpretation,
and never invent stories or causal claims. News refresh and AI analysis remain
separate actions.

Provider access is reported per source. In the current controlled live probe,
the OPEC press-release page returned HTTP 403 to the backend client; EIA,
NUPRC and NNPC items were still ingested successfully. The implementation does
not substitute an unapproved source when an official provider is unavailable.

## Phase 5 Status (Superseded by Hybrid MVP)

The dashboard has switched from legacy Excel data to the live backend API: `DATA_SOURCE_MODE = "api"`.

The browser communicates exclusively with first-party backend endpoints (`/api/dashboard/snapshot`, `/api/market/latest`, `/api/market/history`, `/api/market/refresh`, `/api/macro/latest`, `/api/macro/history`, `/api/macro/refresh`). It never receives OilPriceAPI credentials or calls external market/macro providers directly. External provider tokens are isolated in `backend/.env`.

The legacy Excel adapter is preserved temporarily for rollback and static development testing. Controlled Admin workbook uploads now enter production market calculations through FastAPI and Supabase.

## Data Flow

```text
OilPriceAPI (Live Provider)
      |
      v
FastAPI Backend (OilPriceAPIProvider)
      |
      v
Supabase PostgreSQL (market_observations)
      |
      v
Backend Calculation Service (Stats, 90D Sufficiency, Spreads)
      |
      v
Dashboard API (GET /api/dashboard/snapshot)
      |
      v
Dashboard Frontend (Vanilla JS Renderer)
```

Automated macro indicators use the same first-party backend boundary:

```text
Official macro publishers
  - NBS CPI related materials
  - NBS GDP related materials
  - Stanbic IBTC Bank Nigeria PMI PDF via S&P Global
  - NUPRC production release
      |
      v
Source-specific providers
      |
      v
Normalized MacroObservation records
      |
      v
macro_ingestion service
      |
      v
Supabase PostgreSQL (macro_indicators)
      |
      v
GET /api/macro/latest and GET /api/dashboard/snapshot
      |
      v
Macro Drivers cards
```

The legacy path remains only as a development/testing fallback:

```text
Excel Workbook (Admin Mode only)
      |
      v
Legacy Adapter
      |
      v
Fallback Development Observations
```

## Frontend Modules

| Module | Responsibility |
|---|---|
| `js/config/dashboardConfig.js` | Provider-independent instruments, source mode, approved product conversions, and first-party endpoint paths. |
| `js/market/marketDataModel.js` | Validates and normalizes observations, keeps audit fields, and models freshness/missing instruments. |
| `js/adapters/legacyMarketDataAdapter.js` | Converts the existing demo/Excel dashboard structures into normalized observations. |
| `js/services/marketDataService.js` | Selects `legacy` or `api` mode, calls only first-party market endpoints, normalizes macro indicators from dashboard snapshots, caches successful observations, and applies fallback/stale status. |
| `js/services/marketCalculationService.js` | Calculates latest/previous values, changes, calendar windows, mean, sample standard deviation, z-score inputs, conversions, and product spreads. |
| `js/services/aiService.js` | Defines the AI output contract, builds structured dashboard context, and reserves calls to first-party AI endpoints. |

## Normalized Market Observation

All provider and legacy records must become this shape before market calculations use them:

```json
{
  "instrumentId": "brent",
  "providerSymbol": "PROVIDER_SYMBOL",
  "name": "Dated Brent",
  "value": 0.01,
  "unit": "USD/bbl",
  "assessmentDate": "2026-09-24",
  "retrievedAt": "2026-09-24T07:00:00.000Z",
  "provider": "provider-name",
  "sourceType": "api"
}
```

The number above illustrates the response type only; it is not production or fallback market data. Missing or invalid prices are rejected, not converted to zero. Optional conversion audit fields may include `convertedValue` and `barrelsPerMT`.

## Data Source Modes

`DATA_SOURCE_MODE = "api"` is the current setting. It calls the first-party backend and then feeds normalized observations into the existing calculation and rendering layers. If the provider is unavailable, the service preserves the latest successful in-memory observations and marks them stale. If no successful API observation exists, values are shown as unavailable. Missing values are never invented, and legacy Excel values are not injected into API mode.

## Phase 3 Status — OilPriceAPI Integration

The first external market data provider (**OilPriceAPI**) is integrated into the backend pipeline and connected to Supabase PostgreSQL:
- **Authentication**: `Authorization: Token <OILPRICEAPI_KEY>` via `backend/.env`.
- **Database Storage**: Supabase PostgreSQL (`market_observations` table) using session pooling.
- **Frontend Mode**: `DATA_SOURCE_MODE = "api"` is active. Legacy mode remains only for local development/testing fallback.

### Core Architecture Rules:

1. **Preserve Raw Provider Observations**:
   - `market_observations` stores original values and units directly from OilPriceAPI: `value`, `unit`, `provider`, `provider_symbol`, `source_timestamp`, `retrieved_at`.
   - **No premature conversion** in database ingestion. For instance, Naphtha is stored as `833.59 metric_ton` and Gasoil as `1455.5 tonne`.
   - Conversions to USD/bbl and product crack spreads occur exclusively in the `calculation_service` (`original_price / barrels_per_mt - brent_price`).

2. **Idempotent Same-Day Refresh Semantics**:
   - Unique constraint: `(instrument_id, provider, provider_symbol, assessment_date)`.
   - Successive refreshes on the same assessment date update existing records with newest timestamps and latest prices instead of creating duplicate records.

3. **Controlled History & Strict Null Z-Score Policy**:
   - When historical data is requested (`GET /api/market/history`), points are served from Supabase.
   - For accounts without historical API tiers (where `past_week`, `past_month`, and `past_year` return `HTTP 402 Payment Required`), the system records `history_status: "insufficient_history"` and `z_score: null` whenever fewer than 60 data points are available in the 90-day window.
   - Historical gaps are **never** filled with fake data or legacy Excel data.

### OilPriceAPI Provider-Fit Table

| Instrument Key | Display Name | Canonical Unit | OilPriceAPI Symbol | Provider Name / Commodity | Provider Unit | Status |
|---|---|---|---|---|---|---|
| `brent` | Dated Brent | USD/bbl | `BRENT_CRUDE_USD` | ICE Brent Crude Front-Month Futures | `barrel` | **Confirmed** |
| `wti` | WTI Cushing | USD/bbl | `WTI_USD` | WTI Crude Oil Front-Month Futures | `barrel` | **Confirmed** |
| `forcados` | Forcados Blend | USD/bbl | *None* | *Not available in OilPriceAPI catalog* | — | **Unavailable** |
| `naphtha` | Naphtha CIF NWE Cargoes | USD/MT | `NAPHTHA_USD` | Naphtha | `metric_ton` | **Candidate Test Proxy** |
| `gasoil` | Low Sulphur Gasoil 10ppm | USD/MT | `GASOIL_USD` | ICE Low Sulphur Gasoil Rotterdam | `tonne` | **Candidate Test Proxy** |
| `gasoline` | Premium Motor Gasoline | USD/MT | *None* | `GASOLINE_USD` is US RBOB ($/gallon) | `gallon` | **Unavailable (Unit Mismatch)** |
| `jet` | Aviation Jet Fuel CIF NWE | USD/MT | *None* | `JET_FUEL_USD` is US Gulf Coast ($/gallon) | `gallon` | **Unavailable (Unit Mismatch)** |

## Data Flow

```text
OilPriceAPI (prices/latest)
      ↓
OilPriceAPIProvider (backend/app/providers/market/oilpriceapi.py)
      ↓
Normalized Observations (Raw Value & Raw Unit preserved)
      ↓
market_ingestion service (Idempotent upsert on instrument + provider + date)
      ↓
Supabase PostgreSQL (market_observations)
      ↓
calculation service (Dynamic USD/MT -> USD/bbl conversion & product crack spreads)
      ↓
FastAPI Endpoints (GET /api/market/latest, GET /api/dashboard/snapshot)
      ↓
Browser Dashboard (when DATA_SOURCE_MODE = "api")
```

## Market API Contracts

### `GET /api/market/latest`

Returns the latest stored observation for each mapped instrument in Supabase with freshness audit fields.

Response:

```json
{
  "observations": [
    {
      "instrumentId": "brent",
      "providerSymbol": "BRENT_CRUDE_USD",
      "name": "Dated Brent",
      "value": 105.32,
      "unit": "barrel",
      "assessmentDate": "2026-09-24",
      "retrievedAt": "2026-09-24T12:54:01.738Z",
      "provider": "oilpriceapi",
      "sourceType": "api",
      "sourceTimestamp": "2026-09-24T12:51:06.902Z",
      "ageSeconds": 294.0,
      "freshnessStatus": "fresh",
      "barrelsPerMT": null,
      "convertedValue": null
    }
  ]
}
```

### `GET /api/market/history?instrument=brent&days=90`

Returns historical observations stored in Supabase with `history_status`:

```json
{
  "instrument": "brent",
  "days": 90,
  "total_observations": 1,
  "history_status": "insufficient_history",
  "observations": [
    {
      "date": "2026-09-24",
      "value": 105.32,
      "unit": "barrel"
    }
  ]
}
```

### `POST /api/market/refresh`

Fetches latest prices from the configured provider, updates or inserts observations into Supabase, and returns an execution summary:

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

## Macro API Contracts

### Canonical Indicators

| Key | Definition | Official publisher | Source URL | Unit | Frequency | Extraction method | Freshness rule | Frontend field |
|---|---|---|---|---|---|---|---|---|
| `headline_inflation` | Nigeria national all-items year-on-year CPI inflation | National Bureau of Statistics Nigeria | `https://microdata.nigerianstat.gov.ng/index.php/catalog/154/related-materials` | `%` | Monthly | Discover latest CPI ZIP, extract Excel workbook, validate Table1 labels and latest national YoY row | Monthly cycle; stale only when the reporting period is beyond the expected publication window | Macro Drivers: Headline Inflation |
| `food_inflation` | Nigeria national food year-on-year inflation | National Bureau of Statistics Nigeria | `https://microdata.nigerianstat.gov.ng/index.php/catalog/154/related-materials` | `%` | Monthly | Same CPI workbook, Food YoY column | Monthly cycle | Macro Drivers: Food Inflation |
| `core_inflation` | Nigeria national all-items less farm produce and energy year-on-year inflation | National Bureau of Statistics Nigeria | `https://microdata.nigerianstat.gov.ng/index.php/catalog/154/related-materials` | `%` | Monthly | Same CPI workbook, Core YoY column | Monthly cycle | Macro Drivers: Core Inflation |
| `real_gdp_growth` | Nigeria total real GDP year-on-year growth | National Bureau of Statistics Nigeria | `https://microdata.nigerianstat.gov.ng/index.php/catalog/147/related-materials` | `%` | Quarterly | Discover latest GDP ZIP, extract Excel workbook, validate real GDP growth sheet and total constant-price GDP row | Quarterly cycle | Macro Drivers: Real GDP Growth |
| `nigeria_pmi` | Headline seasonally adjusted Stanbic IBTC Bank Nigeria PMI | Stanbic IBTC Bank / S&P Global | Public monthly Stanbic IBTC Bank PMI PDF | `index` | Monthly | Discover latest valid PDF, extract headline PMI value and reporting month | Monthly cycle | Macro Drivers: PMI |
| `crude_oil_production` | Strict crude oil production, excluding condensate, monthly average daily production | Nigerian Upstream Petroleum Regulatory Commission | `https://www.nuprc.gov.ng/` news release | `mbpd` | Monthly | Discover latest production article, extract strict crude-only BPD and convert to mbpd; combined crude + condensate retained only as metadata | Monthly cycle | Macro Drivers: Crude Oil Production |

### `POST /api/macro/refresh`

Fetches latest values from official publishers, validates canonical definitions, and upserts by `(indicator_key, reporting_period, source)`.

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

Re-running the same official observations returns `unchanged` instead of inserting duplicate rows. If a source revises a value for the same period, the existing row is updated and revision metadata is preserved.

### `GET /api/macro/latest`

Returns one record for each canonical macro indicator. Missing records are returned as `value: null`, `status: "unavailable"`, and `freshness_status: "unavailable"` rather than `0`.

### `GET /api/macro/history?indicator=headline_inflation`

Returns historical observations for one canonical key, ordered from newest to oldest.

### Dashboard Snapshot

`GET /api/dashboard/snapshot` includes `macro_indicators`, sourced from verified records in `macro_indicators`. The frontend renders value, unit, reporting period, source, and freshness status. Oil production is labelled as crude only, excluding condensate.

### Macro Failure Handling

| Condition | Expected behavior |
|---|---|
| Today's extraction fails but a verified prior value exists | Keep the prior value, preserve its reporting period, and mark it stale. |
| No verified prior value exists | Return `value: null`, `status: "unavailable"`, and show `Data unavailable`. |
| Missing label or malformed workbook/PDF/article | Fail closed with an extraction error; do not take nearby values. |
| Source returns non-PDF for PMI candidate | Skip it and continue discovery. |
| Combined crude + condensate appears in NUPRC article | Store only as metadata; main value remains strict crude only. |

## AI API Contracts

OpenAI is an interpretation layer. It is not the source of truth for market prices or calculated risk metrics. Latest prices, changes, averages, standard deviations, z-scores, conversions, and spreads are calculated by application code before AI receives context.

### `POST /api/ai/analyse`

Request:

```json
{
  "context": {
    "generatedAt": "2026-09-24T07:05:00.000Z",
    "market": [],
    "outliers": [],
    "productSpreads": [],
    "macro": {},
    "geopolitical": {},
    "companyRisk": {},
    "overallRisk": {}
  }
}
```

Expected saved response contract:

```json
{
  "dailyBriefing": [],
  "riskAdvisor": {
    "threats": [],
    "opportunities": [],
    "watch": []
  },
  "traderDesk": {
    "counterpartyColour": "",
    "riskStrategy": [],
    "watchItems": []
  },
  "managementActions": [],
  "overallCommentary": ""
}
```

The scheduled market refresh should run analysis once and save the result server-side. Dashboard page loads should read the saved analysis rather than create a new paid AI request.

### `POST /api/ai/chat`

Request:

```json
{
  "message": "User question",
  "context": {}
}
```

Chat is the exception to saved shared analysis because each user question requires a live response. The current phase provides service hooks only; it does not add chatbot UI or fake responses.

## Failure Handling

| Condition | Expected behavior |
|---|---|
| Provider unavailable | Keep the latest successful observation, mark it stale, and record a service error. |
| Invalid provider response | Reject the invalid record; do not coerce blanks or invalid values to zero. |
| Rate limit | Return a `RATE_LIMITED` service state and preserve cached data. |
| Stale data | Keep the value with its assessment/retrieval timestamps and set freshness to `stale`. |
| Missing instrument | Report it in `missingInstruments`; do not synthesize a price. |
| Missing observation | Leave the value unavailable or retain the last successful stale value. |
| AI unavailable | Return an unavailable/not-configured state; verified dashboard calculations continue normally. |

## Secrets And Environment

`.env.example` lists variable names only. `.env` is ignored by Git. Future hosted configuration may use:

```text
OPENAI_API_KEY
MARKET_DATA_PROVIDER
MARKET_DATA_API_KEY
MARKET_DATA_BASE_URL
```

Optional provider-specific names are included for future evaluation, but no provider is assumed to cover all instruments. Provider selection and symbol mapping belong on the backend.

## Future Database

The database should retain raw/provider observations, normalized observations, provider and symbol, source and retrieval timestamps, units, refresh status, calculated metrics, and saved AI analysis. This supports auditability and lets all users read one consistent result after each scheduled refresh.
