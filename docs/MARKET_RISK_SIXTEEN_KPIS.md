# Sixteen Platts Market Risk KPIs - controlled verification

Baseline: 07d6062. Migration head remains 0011_intelligence_synthesis.
No commit or push. Development Supabase and the normal FastAPI/Node processes
were used; no isolated data or fabricated browser responses were substituted.

## Architecture and source verification

The original seven HISTORICAL_MAPPING entries are unchanged. RISK_SCORING_KEYS
is frozen before adding the nine ANALYTICAL_MAPPING entries. All sixteen use
historical_market_observations; no new current-price store or collection metadata
records are created. Workbook Market Risk header descriptions, symbols, units,
closing assessment code c and latest values were checked before implementation.
New optional columns with invalid units or non-closing codes are skipped and
reported; an absent column does not erase previously imported history.

Backend responses and public configuration explicitly distinguish
monitored_for_analytics from included_in_risk_scoring. The original seven remain
scoring inputs; the nine analytical additions are filtered out of category
aggregation and both existing Risk Advisor context builders. No prompt or
Risk Advisor UI change was made. Macro queries and definitions are unchanged.

The three new USD/mt series have no approved bbl/mt factor and no Brent spread.
Their public convertedValue is null; only native-unit analytics are offered.
For schema compatibility the existing non-null converted_value storage column
retains the importer's native passthrough when no factor exists; that cache is
not exposed or interpreted as USD/bbl for these instruments. No conversion was
invented. Original four product spreads and all conversion defaults are unchanged.
Nigerian crude assessments are outright prices, not NNPC monthly OSP differentials.

## Controlled workbook import

Source: Daily Trading Risk Dashboard 1.xlsx, refreshed workbook ending 2026-10-14.
Before: 2,656 rows. First import: 1,791 inserted, 2,656 updated/unchanged;
after: 4,447. Repeat: 0 inserted, 4,447 updated/unchanged; total remains 4,447.
All nine new series have 199 assessments and 63 points in their latest 90D window.
Original seven native dates/values/units/factors and separate API-table fingerprints
were identical before and after both imports. Workbook hash, filename, worksheet,
assessment date and import timestamp continue to be persisted. Original older
history was retained. Missing observations are omitted, never synthesized as zero.

## Complete assessment verification

Values below are unrounded API/card input values; visible cards round normally.

| KPI | Code | Top-card value / date | Historical value / date | Unit | 90D count | Z-score | Source |
|---|---|---|---|---|---:|---:|---|
| Dated Brent | PCAAS00 | 127.545 / 2026-10-14 | 127.545 / 2026-10-14 | USD/BBL | 63 | +1.255482 | Platts workbook |
| Naphtha FOB Rotterdam Barge | PAAAM00 | 917 / 2026-10-14 | 917 / 2026-10-14 | USD/MT | 63 | +1.730387 | Platts workbook |
| Gasoil 0.1%S FOB Med Cargo | AAVJI00 | 1445.5 / 2026-10-14 | 1445.5 / 2026-10-14 | USD/MT | 63 | +0.812466 | Platts workbook |
| Premium Unleaded 10ppm FOB AR Barge | PGABM00 | 1224.25 / 2026-10-14 | 1224.25 / 2026-10-14 | USD/MT | 63 | +0.304865 | Platts workbook |
| Forcados FOB Nigeria | PCABC00 | 105.945 / 2026-10-14 | 105.945 / 2026-10-14 | USD/BBL | 63 | +0.628070 | Platts workbook |
| WTI Cushing Mo01 | PCACG00 | 95.09 / 2026-10-14 | 95.09 / 2026-10-14 | USD/BBL | 63 | +0.819398 | Platts workbook |
| Jet FOB NWE Cargo | PJAAV00 | 1636.75 / 2026-10-14 | 1636.75 / 2026-10-14 | USD/MT | 63 | +1.527054 | Platts workbook |
| Bonny Light FOB Nigeria London | PCAIC00 | 104.495 / 2026-10-14 | 104.495 / 2026-10-14 | USD/BBL | 63 | +0.569383 | Platts workbook |
| Bonga FOB Nigeria | PCNGC00 | 106.145 / 2026-10-14 | 106.145 / 2026-10-14 | USD/BBL | 63 | +0.625658 | Platts workbook |
| Brass River FOB Nigeria | AAEJB00 | 102.845 / 2026-10-14 | 102.845 / 2026-10-14 | USD/BBL | 63 | +0.534331 | Platts workbook |
| Erha FOB Nigeria | AAXUO00 | 105.895 / 2026-10-14 | 105.895 / 2026-10-14 | USD/BBL | 63 | +0.625221 | Platts workbook |
| Escravos FOB Nigeria | AAEIZ00 | 106.045 / 2026-10-14 | 106.045 / 2026-10-14 | USD/BBL | 63 | +0.628070 | Platts workbook |
| Qua Iboe FOB Nigeria | PCAID00 | 104.295 / 2026-10-14 | 104.295 / 2026-10-14 | USD/BBL | 63 | +0.569383 | Platts workbook |
| Gasoil .1%S (1000ppm) FOB ARA Barge (NextGen MOC) | AAYWT00 | 1417.5 / 2026-10-14 | 1417.5 / 2026-10-14 | USD/MT | 63 | +1.128602 | Platts workbook |
| ULSD 10ppmS FOB NWE Basis Le Havre Cargo | AAWZD00 | 1469.25 / 2026-10-14 | 1469.25 / 2026-10-14 | USD/MT | 63 | +0.824431 | Platts workbook |
| Jet CIF NWE Cargo | PJAAU00 | 1666.5 / 2026-10-14 | 1666.5 / 2026-10-14 | USD/MT | 63 | +1.558286 | Platts workbook |

Every latest assessment, date, unit, symbol, z-score and 90D count agreed between
snapshot and historical endpoints. Direct and proxied snapshot series agreed.
The original seven current/previous/change/percentage/mean/sample-SD/z-score/count
fields and the four full product-spread responses matched the saved baseline.
Current Market-wide Outlier Scan is empty: all sixteen absolute z-scores are <2.
Synthetic tests prove qualifying instruments in the second view still render,
rank correctly and disappear from eligibility below 60 valid points.

## UI and deterministic risk regression

Eight cards render in each view, in the specified order. Switching uses existing
state, makes zero additional API requests, and leaves the market-wide outlier scan
independent. All sixteen historical selections render the matching 2026-10-14
assessment. Desktop 1440px and mobile 390px checks show no uncaught JS exceptions
and no horizontal page overflow. Card grid and unrelated layout are unchanged.
Original seven scoring membership is protected independently from the visible view.

Before -> after:
- Market Risk: High -> High.
- Macro/Geopolitical: High -> High.
- Company Exposures: Catastrophic -> Catastrophic.
- Overall Risk: Catastrophic -> Catastrophic (3.3225806451612905 unchanged).
- Primary Driver: Company Exposures -> Company Exposures.
- Today's Triggers: 0 Low / 0 Moderate / 2 High / 1 Catastrophic -> unchanged.

## Performance

Snapshot transfers 1,008 observations (16 x 63), plus 16 aggregate anchors, rather
than all 4,447 stored rows. The seven-instrument scope transfers 441 points. Sparse
previous-assessment and same-date Brent spread-anchor logic is preserved. Macro
still returns 18 selected records; no all-candidate transfer was reintroduced.

Three sequential before/after HTTP samples per path, normal development processes:

| Path | Seven KPI median / worst | Sixteen KPI median / worst |
|---|---:|---:|
| Direct FastAPI | 6.382 / 8.065s | 3.099 / 6.060s |
| Existing Node proxy | 4.976 / 8.253s | 4.017 / 4.768s |

A separate three-pair read-only diagnostic alternated seven/sixteen mapping scopes
in the same code/database connection pool: handler median/worst 3.227/3.519s for
seven versus 4.960/5.564s for sixteen. This diagnostic changes only subprocess-local
mapping scope, never application files, server state or database data.
The additional bounded history increases result volume. Initial sixteen-handler
samples collected while browser/live verification was also active were slower:
7.044/9.778/10.094s. All these samples are retained; the older 1.41s seven-KPI
measurement is not a guaranteed latency target under changing network conditions.
HTTP and handler batches are separate samples, not directly additive/comparable.
No timeout, credential, SSL, pool setting or migration was changed. These results
verify bounded reads, not a fix of the underlying variable Supabase transport.

## Tests, safeguards and evidence

Backend 288 passed (four existing warnings); frontend 113 passed; proxy 1 passed.
Synthetic fixtures cover all sixteen mappings/import/refresh/idempotency, invalid
new-series isolation, null/zero handling, z-scores/insufficiency/outliers, unchanged
four spreads, bounded window reads, original-seven scoring and Advisor boundaries.
All 21 source/public pairs match. No configured secrets match tracked/proposed
source files; environment files and ignored diagnostic artifacts are not tracked.
No database schema change. Head remains 0011_intelligence_synthesis.

Ignored evidence under .venv/phase1-qa/: sixteen-import.json,
sixteen-before-snapshot.json, sixteen-verification.json, sixteen-browser.json,
sixteen-paired-timings.json, bounded-http-16-before.json,
bounded-http-16-after.json, and sixteen desktop/mobile screenshots.

## Remaining limitations

Assessments still require workbook upload; this is not a live Platts feed. There
are no approved conversion factors/spreads for the three new USD/mt definitions.
The unchanged full-history endpoint and importer still transfer complete histories
where needed; they can remain sensitive to transport variance. No NNPC OSP feed,
API blending, additional scoring inputs or unrelated dashboard feature was added.


## File scope (22 files)

Backend: backend/app/api/market.py, backend/app/schemas/market.py,
backend/app/services/historical_market.py, backend/app/services/official_market.py,
backend/app/services/ai_context.py.

Source UI: dashboard.js, index.html, style.css, js/config/dashboardConfig.js,
js/services/aiService.js; matching public/ copies of those five files.

Tests: backend/tests/test_api.py, backend/tests/test_historical_market.py,
backend/tests/test_official_market.py, backend/tests/test_sixteen_market.py,
tests/market-architecture.test.js.

Documentation: docs/MARKET_RISK_SOURCE_POLICY.md and this report.


## Approved checkpoint wording correction

The final UI check found that the existing <0.05% description classified small
nonzero changes as unchanged. The description now reserves unchanged for exactly
zero absolute movement and retains direction for smaller positive/negative changes.
Jet CIF NWE Cargo +0.50 reads Slightly above previous observation. This changes
wording only, with regression coverage for positive, negative, zero and missing
percentage cases; price/change calculations, thresholds and risk ratings are unchanged.
