# Daily Oil Trading Risk Dashboard

## Phase 6 AI Analysis

The dashboard includes an explicit Gemini interpretation layer. Normal page
load reads the last successful result from `GET /api/ai/latest`; the user can
select **Refresh AI Analysis** to run `POST /api/ai/analyse`. The backend builds
the context from verified database records, validates the structured response,
and persists both the input snapshot and result. Missing values, unavailable
instruments, proxy qualifications and insufficient history remain explicit.

Set `AI_PROVIDER=gemini`, `GEMINI_API_KEY`, and optionally
`GEMINI_MODEL=gemini-3.8-flash` in `backend/.env`. Never expose the key in
browser JavaScript or commit it. The chatbot endpoint remains unavailable by
design until a later phase.

## Final MVP Hybrid Market Data

The Admin workbook upload now uses `POST /api/market/import-excel`. FastAPI
validates the workbook and persists supported physical Platts assessments as
`internal_excel` observations. The dashboard continues to consume only the
backend snapshot and deterministic calculation service.

The source policy is explicit: OilPriceAPI supplies Brent and WTI; the
internal workbook supplies Forcados, Naphtha, Gasoil, Gasoline and Jet when
their physical definitions are present. A missing preferred source produces
an unavailable/stale state; no cross-source fallback or benchmark-history
mixing is allowed. Re-uploading the same workbook is idempotent.

## Automated Energy News

The Admin/news flow uses only whitelisted official sources: EIA RSS, OPEC,
NUPRC and NNPC Limited. `POST /api/news/refresh` stores validated headlines,
external URLs, publication times, short excerpts, regions and restrained
topics in Supabase. Repeated URLs are idempotent, stale stories remain stored
for audit history but are excluded from the seven-day dashboard feed, and a
failed source does not block successful sources.

API mode renders the verified International, Africa and Nigeria news groups
from `GET /api/news/latest`; it does not use the local demo/manual briefing.
The separate **Refresh AI Analysis** action passes at most 20 recent news
records to Gemini as attributed context. Full article bodies are never stored
or sent to Gemini.

Each source reports independently during refresh. The current controlled probe
observed HTTP 403 from the OPEC page while the other approved sources still
loaded; no unapproved fallback source is used.

Executive dashboard for daily oil market risk, official Nigeria macro drivers, macro/geopolitical context, company exposure, editable briefing content, and overall risk position.

## How To Run

For API mode, run the FastAPI backend and the Node/Express frontend wrapper:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
npm start
```

Then open `http://localhost:3000`.

`index.html` can still be opened directly for static development, but production-style market and macro values come from the backend API.

## Admin Mode

Use the `Admin` button in the footer.

```text
Username: riskadmin
Password: Password123
```

Excel upload is available only in Admin Mode:

`Admin -> Data Management -> Load / Refresh Excel`

The selected `.xlsx` file is uploaded to FastAPI for validation and persistence. The workbook is not parsed or calculated in the browser and is not stored in `localStorage`.

## Main Files

- `index.html` is the static application entry point.
- `style.css` controls the executive dashboard layout, responsive behavior, and print view.
- `dashboard.js` controls rendering, local Admin Mode, editable sections, localStorage persistence, and Excel loading.
- `excel.js` is the retained legacy workbook adapter for static development and rollback tests; Admin uploads use the FastAPI importer.
- `risk-engine.js` calculates KRI metrics and aggregate risk summaries.
- `charts.js` draws local canvas/SVG charts without external CDNs.
- `data.js` contains fallback sample dashboard data.
- `vendor/xlsx.full.min.js` is the bundled local SheetJS browser library.

## Live API + Controlled Excel Pipeline

The dashboard runs in `api` data-source mode (`DATA_SOURCE_MODE = "api"`).

The live market pipeline is:
```text
OilPriceAPI → FastAPI Backend → Supabase PostgreSQL → Dashboard API → Frontend
```

- Live macro pipeline: official publishers -> FastAPI Backend -> Supabase PostgreSQL -> Dashboard API -> Frontend.
- Live market instruments: Brent and WTI from OilPriceAPI; Forcados, Naphtha, Gasoil, Gasoline and Jet from the validated internal workbook when uploaded.
- Live macro indicators: headline inflation, food inflation, core inflation, real GDP growth, Nigeria PMI, and crude oil production.
- Macro sources: NBS CPI/GDP ZIP workbooks, Stanbic IBTC Bank / S&P Global PMI PDF, and NUPRC production release.
- Crude Oil Production means strict crude only, excluding condensate. Combined crude plus condensate is metadata only.
- Z-score calculations: display `Insufficient 90D history` based on backend `history_status == "insufficient_history"`.
- Product Spreads: chart available products only; unavailable products are excluded from the comparison chart.
- Refresh: manual API refresh triggers `POST /api/market/refresh` for OilPriceAPI-owned instruments; Admin workbook upload triggers `POST /api/market/import-excel` then reloads the snapshot.
- Macro refresh: `POST /api/macro/refresh` performs idempotent upserts by `indicator_key + reporting_period + source`.
- Legacy Excel adapter: preserved for static development and rollback tests; normal Admin ingestion is backend-controlled.
- AI service: Gemini receives normalized backend data, including source and benchmark identity.

The browser communicates only with first-party `/api/...` endpoints and never receives API credentials. Provider keys remain isolated in `backend/.env`.

## Editable Local Content

Admin edits are saved in browser `localStorage` for manual sections such as briefing, macro commentary, risk advisor commentary, trader desk notes, geopolitical cards, risk register, forward calendar, management actions, and risk-by-category settings. Macro values themselves are automated official-source records in API mode.
