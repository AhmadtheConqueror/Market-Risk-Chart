# Phase 3 — OilPriceAPI Live Market Data Integration
## Completion Report & Verification Walkthrough

---

### 1. Executive Summary

Phase 3 of the Daily Oil Trading Risk Dashboard is fully implemented, verified, and operational. Live market data integration with **OilPriceAPI** has been established and connected through the generic provider abstraction directly to **Supabase PostgreSQL** via session pooler.

All three specified user refinements have been rigorously implemented:
1. **Preserve Raw Provider Observations**: `market_observations` stores original OilPriceAPI values (`833.59`), raw units (`metric_ton`, `tonne`, `barrel`), provider symbols, source timestamps, and retrieval timestamps. No premature unit conversion occurs in database ingestion; dynamic conversion to USD/bbl and product crack spreads occurs exclusively in the application's calculation service.
2. **Idempotent Same-Day Refresh Semantics**: Successive refreshes on the same assessment date idempotently update existing observations (`(instrument_id, provider, provider_symbol, assessment_date)`), updating price, source timestamp, and retrieval timestamp without generating duplicate rows.
3. **Persist Available History & Strict Null Z-Score Policy**: Historical observations are read directly from Supabase. Because the active OilPriceAPI subscription tier returns `HTTP 402 Payment Required` for historical endpoints (`past_week`, `past_month`, `past_year`), the system rigorously sets `history_status: "insufficient_history"` and `z_score: null` for windows with fewer than 60 points. No legacy Excel fallback or synthetic data is used to fabricate missing history.

The frontend remains untouched in `DATA_SOURCE_MODE = "legacy"` as required.

---

### 2. Provider Discovery & Fit Assessment

The provider's `/v1/commodities` catalog (1,010 entries) and `/v1/prices/latest` endpoint were probed with the active key.

| Canonical Instrument | Canonical Display Name | Canonical Unit | OilPriceAPI Symbol | Provider Name / Commodity Description | Provider Unit | Fit Status | Rationale |
|---|---|---|---|---|---|---|---|
| `brent` | Dated Brent | USD/bbl | `BRENT_CRUDE_USD` | ICE Brent Crude Front-Month Futures | `barrel` | **Confirmed** | Clean match with high liquidity and real-time futures quotes. |
| `wti` | WTI Cushing | USD/bbl | `WTI_USD` | WTI Crude Oil Front-Month Futures | `barrel` | **Confirmed** | Clean match with real-time NYMEX futures quotes. |
| `forcados` | Forcados Blend | USD/bbl | *None* | *Not available in OilPriceAPI catalog* | — | **Unavailable** | Nigerian physical crude benchmark requires specialized physical provider (e.g. Argus / Platts). Left unmapped with `null` provider symbol. |
| `naphtha` | Naphtha CIF NWE Cargoes | USD/MT | `NAPHTHA_USD` | Naphtha | `metric_ton` | **Candidate Test Proxy** | Clean metric ton pricing. Raw unit preserved; dynamic conversion uses `8.90 bbl/mt`. |
| `gasoil` | Low Sulphur Gasoil 10ppm | USD/MT | `GASOIL_USD` | ICE Low Sulphur Gasoil Rotterdam | `tonne` | **Candidate Test Proxy** | Clean tonne pricing. Raw unit preserved; dynamic conversion uses `7.44 bbl/mt`. |
| `gasoline` | Premium Motor Gasoline 10ppm | USD/MT | *None* | `GASOLINE_USD` (US RBOB) | `gallon` | **Unavailable (Unit Mismatch)** | OilPriceAPI quotes US retail/terminal gasoline in USD/gallon ($3.58/gal), not Northwest Europe physical cargo quotes in USD/MT. |
| `jet` | Aviation Jet Fuel CIF NWE | USD/MT | *None* | `JET_FUEL_USD` (US Gulf Coast) | `gallon` | **Unavailable (Unit Mismatch)** | OilPriceAPI quotes US Gulf Coast jet fuel in USD/gallon ($4.35/gal), not CIF NWE cargo quotes in USD/MT. |

---

### 3. Latest Retrieved Live Market Data

Successfully ingested from OilPriceAPI and persisted in Supabase PostgreSQL (`market_observations`):

| Instrument | Provider Symbol | Ingested Price | Provider Unit | Assessment Date | Source Timestamp (UTC) | Converted USD/bbl | Product-Brent Spread |
|---|---|---|---|---|---|---|---|
| **Brent** | `BRENT_CRUDE_USD` | 105.32 | `barrel` | 2026-09-24 | 2026-09-24 12:51:06 | $105.32 | Benchmark |
| **WTI** | `WTI_USD` | 93.94 | `barrel` | 2026-09-24 | 2026-09-24 12:51:06 | $93.94 | -$11.38 |
| **Naphtha** | `NAPHTHA_USD` | 833.59 | `metric_ton` | 2026-09-24 | 2026-09-24 00:15:18 | $93.66 | -$11.66 |
| **Gasoil** | `GASOIL_USD` | 1455.50 | `tonne` | 2026-09-24 | 2026-09-24 12:52:07 | $195.63 | +$90.31 |

*Note: Calculations confirm conversion formula: $833.59 / 8.90 = $93.66/bbl; Spread = $93.66 - $105.32 = -$11.66/bbl. Gasoil: $1455.50 / 7.44 = $195.63/bbl; Spread = $195.63 - $105.32 = +$90.31/bbl.*

---

### 4. Idempotent Same-Day Refresh Verification

Calling `POST /api/market/refresh`:

- **First run**:
  ```json
  {"provider": "oilpriceapi", "requested": 4, "stored": 2, "updated": 2, "skipped": 0, "failed": 0, "instruments": ["brent", "wti", "naphtha", "gasoil"]}
  ```
  *(Inserted 2 new products, updated 2 existing crudes).*
- **Second run (Immediate re-trigger)**:
  ```json
  {"provider": "oilpriceapi", "requested": 4, "stored": 0, "updated": 4, "skipped": 0, "failed": 0, "instruments": ["brent", "wti", "naphtha", "gasoil"]}
  ```
  *(Zero duplicates created; all 4 existing records updated with latest provider timestamps).*
- **Total rows in `market_observations`**: Exactly 4 unique records.

---

### 5. Historical Entitlements & Z-Score Rule Verification

- Probed endpoints: `past_week`, `past_month`, `past_year`.
- Response: `HTTP 402 Payment Required` (account tier does not include historical timeseries).
- Verification of statistical policy:
  - `GET /api/market/history?instrument=brent&days=90` returns `total_observations: 1`, `history_status: "insufficient_history"`.
  - `GET /api/dashboard/snapshot` returns `z_score: null`, `history_status: "insufficient_history"` for all active instruments with < 60 points.
  - Zero data fabrication; legacy Excel prices are not mixed into the live pipeline.

---

### 6. Endpoint Verification Against Live Supabase

Verified with `backend/scripts/verify_api_live.py`:

```text
--- 1. Testing GET /api/market/latest ---
Status: 200
Returned 4 items:
  • brent      | val: 105.32 barrel     | freshness: fresh (age: 342.8s)
  • wti        | val: 93.94 barrel      | freshness: fresh (age: 343.7s)
  • naphtha    | val: 833.59 metric_ton | freshness: fresh (age: 45691.8s)
  • gasoil     | val: 1455.5 tonne      | freshness: fresh (age: 282.9s)

--- 2. Testing GET /api/market/history?instrument=brent&days=90 ---
Status: 200
Instrument: brent | Observations returned: 1 | History Status: insufficient_history

--- 3. Testing GET /api/dashboard/snapshot ---
Status: 200 | Snapshot Date: 2026-09-24
Market Stats:
  • brent      | curr: 105.32  | 1D: None | z-score: None | history_status: insufficient_history
  • wti        | curr: 93.94   | 1D: None | z-score: None | history_status: insufficient_history
  • forcados   | curr: None    | 1D: None | z-score: None | history_status: unavailable
  • naphtha    | curr: 833.59  | 1D: None | z-score: None | history_status: insufficient_history
  • gasoil     | curr: 1455.5  | 1D: None | z-score: None | history_status: insufficient_history
  • gasoline   | curr: None    | 1D: None | z-score: None | history_status: unavailable
  • jet        | curr: None    | 1D: None | z-score: None | history_status: unavailable

Product Spreads:
  • naphtha    | raw: 833.59 metric_ton | bbl/mt: 8.9  | converted: $93.66/bbl  | spread: -$11.66/bbl
  • gasoil     | raw: 1455.5 tonne      | bbl/mt: 7.44 | converted: $195.63/bbl | spread: $90.31/bbl

=== ALL LIVE ENDPOINT VERIFICATIONS PASSED WITH ZERO ERRORS ===
```

---

### 7. Automated Test Suite Results

1. **Backend Test Suite (`py -m pytest backend/tests -v`)**:
   - **32 tests collected, 32 passed (100%)**
   - Includes 10 dedicated OilPriceAPI unit tests mocking single-code, multi-code, HTTP 401 error, JSON decode error, missing prices, raw unit preservation, same-day upsert semantics, and insufficient 90D history z-score handling. Zero quota consumed during testing.
2. **Frontend Architecture Suite (`node --test tests/market-architecture.test.js`)**:
   - **5 tests collected, 5 passed (100%)**
   - Verified legacy data adapter, normalized calculations, approved product conversions, missing value rejection, and AI hook contracts.

---

### 8. Environment & Secrets Cleanup

- **Root `.env`**: Cleaned to contain only frontend/server environment settings (`PORT`, `SESSION_SECRET`). All database and provider keys removed.
- **`backend/.env`**: All backend secrets (`DATABASE_URL`, `OILPRICEAPI_KEY`, AI keys) strictly isolated and gitignored (`.gitignore` protects all `.env` files).
- **Credentials Security**: Zero keys or database connection strings printed, echoed, or committed.
