# Controlled live USA/global macro verification

One refresh invoked after passing backend/frontend tests. Uses the configured project database; Nigeria providers were excluded.

| Geography | Indicator | Value | Unit | Period | Source | Freshness |
|---|---|---|---|---|---|---|
| USA | Headline Inflation | 3.40 | % | Aug 2026 | [U.S. Bureau of Labor Statistics](https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0) | Fresh |
| USA | Core Inflation | 2.45 | % | Aug 2026 | [U.S. Bureau of Labor Statistics](https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0L1E) | Fresh |
| USA | Real GDP Growth | 2.2 | % | Q2 2026 | [U.S. Bureau of Economic Analysis](https://www.bea.gov/sites/default/files/2026-09/hist2q26-3rd.xlsx) | Fresh |
| USA | Effective Federal Funds Rate | 3.88 | % | 2026-10-05 | [Federal Reserve / FRED](https://fred.stlouisfed.org/graph/fredgraph.csv?id=EFFR) | Fresh |
| USA | Unemployment Rate | 4.2 | % | Sep 2026 | [U.S. Bureau of Labor Statistics](https://api.bls.gov/publicAPI/v2/timeseries/data/LNS14000000) | Fresh |
| USA | Commercial Crude Inventories | 427.32 | million barrels | 2026-09-25 | [U.S. Energy Information Administration](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=WCESTUS1&f=W) | Fresh |
| Global | World Real GDP Growth | 3.1 | % | 2026 | [IMF World Economic Outlook](https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH/WEOWORLD) | Fresh |
| Global | World Inflation | 4.4 | % | 2026 | [IMF World Economic Outlook](https://www.imf.org/external/datamapper/api/v1/PCPIPCH/WEOWORLD) | Fresh |
| Global | China Manufacturing PMI | 50.1 | index | Sep 2026 | [National Bureau of Statistics of China](https://www.stats.gov.cn/sj/zxfbhjd/202609/t20260930_1965449.html) | Fresh |
| Global | Global Oil Demand Growth | -1.69 | mbpd | 2026 | [U.S. Energy Information Administration](https://www.eia.gov/outlooks/steo/tables/pdf/3etab.pdf) | Fresh |
| Global | Energy Price Index | 148.9 | index | Sep 2026 | [World Bank Commodity Price Data / Pink Sheet](https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx) | Fresh |
| Global | Broad U.S. Dollar Index | 121.3848 | index | 2026-10-02 | [Federal Reserve / FRED](https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTWEXBGS) | Fresh |

History observations: 15086 stored; 0 revised; 0 unchanged.
Nigeria history preserved: 6 records; before/after digest identical.

## Source retrieval failures

None. All 12 new indicators were retrieved from official sources.

## Definitions

CPI: matched monthly year-on-year index change. GDP: preceding-quarter growth at seasonally adjusted annual rate. Inventories: commercial crude excluding SPR, thousand barrels converted to million barrels.
World GDP/inflation: current reference year from the identified IMF WEO edition; future forecasts remain in history. Oil demand growth: current annual world liquid-fuels consumption minus previous-year annual consumption, mbpd; explicitly an EIA STEO estimate/forecast. Energy index: World Bank nominal USD, 2010=100. Broad USD: Fed nominal broad trade-weighted index, January 2006=100.

## Validation

- Backend: 124 passed; one existing Starlette/HTTPX deprecation warning. Gemini tests now explicitly use their supported asyncio runtime.
- Frontend: 60 passed.
- Native Chrome checks: all three tabs render six cards; arrow-key navigation works; no macro-section overflow at 1440, 1000, 390 or 320 pixels. Existing grid uses six desktop columns, three tablet columns and one mobile column.
- No schema migration, Nigeria extractor changes, KPI redesign, calendar sourcing, AI feature expansion or authentication changes.

Read-only HTTP smoke checks against the configured database returned HTTP 200 for /api/macro/latest (18 indicators, all 12 new values Fresh) and /api/dashboard/snapshot (18 macro indicators). No second live refresh was performed.
