# Official Market Risk source policy

Effective 16 October 2026. Historical-refresh baseline: d76a08c.

The sixteen monitored Market Risk KPIs use exact Platts workbook assessments for
both latest value and historical/statistical analysis. Only the original seven
are risk-scoring inputs; the nine additions are analytical only. See
[the sixteen-KPI verification](MARKET_RISK_SIXTEEN_KPIS.md) for the current mappings,
controlled imports and performance results. Earlier seven-KPI verification sections
below are retained as chronological checkpoint evidence. Similar commodity names
do not establish benchmark equivalence: **same commodity name != same benchmark**.

| KPI | Platts code | Assessment | Native unit | bbl/mt for spreads |
|---|---|---|---|---|
| Brent | PCAAS00 | Dated Brent | USD/bbl | — |
| Naphtha | PAAAM00 | Naphtha FOB Rotterdam Barge | USD/mt | 8.9000 |
| Gasoil | AAVJI00 | Gasoil 0.1%S FOB Med Cargo | USD/mt | 7.3137 |
| Gasoline | PGABM00 | Premium Unleaded 10ppm FOB AR Barge | USD/mt | 8.5286 |
| Forcados | PCABC00 | Forcados FOB Nigeria | USD/bbl | — |
| WTI | PCACG00 | WTI Cushing Mo01 | USD/bbl | — |
| Jet | PJAAV00 | Jet FOB NWE Cargo | USD/mt | 7.7892 |

## Canonical path

Admin workbook upload -> validated mapped materialized Market Risk results plus
retained approved older workbook history -> historical_market_observations
(provider platts_excel) -> official latest/history endpoints, dashboard snapshot,
seven cards, statistics, outlier scan, spreads and existing deterministic risk engine.

No database migration or rebuild is required. Imports retain prior history and
upsert by instrument/provider/Platts symbol/assessment date, with workbook filename,
hash, worksheet and import timestamp. Imports no longer write a second current
Forcados copy into market_observations or change market_instruments provider metadata.
Daily_Historical_Template1.xlsx is not the seven-KPI source.

The snapshot supplies both latest values and their normalized 90-day histories
in one response, preventing independent current/history reads from crossing an
import boundary. Crude & Product Analytics reads the same persisted series.
The shared analysis-context builder uses this lineage too, retaining its existing
bounded 30-day market context; Risk Advisor prompts and integration rules are unchanged.

## Analytics and freshness

Display native assessments without converting product cards into USD/bbl.
Compute 1D against the previous valid observation. Calendar windows end at each
series' latest valid assessment. Continue using existing sample standard deviation
and a 60-observation minimum for 90D z-scores. Outliers require a finite z-score,
at least 60 valid observations and absolute z >= 2, ordered by descending absolute z.
Missing data remain unavailable; valid zero is preserved. Stale is not unavailable.
Freshness is assessment-date based (existing historical rule: stale after 3 days),
not based on import time. Values are assessments, not live/real-time prices.

Spreads are raw native product price / the workbook-specific factor minus
same-date PCAAS00 Dated Brent. A missing same-date leg yields a null spread.
Recompute from raw prices; do not use workbook Jet spread signs or trust a cached
converted price. API conversion defaults remain separate and unchanged.

Risk thresholds, category weights, scoring methodology, Company Exposure and
Macro rules are unchanged. Corrected source values can legitimately change results.

## API infrastructure retained

OilPriceAPI provider code, credentials, stored observations, collection/backfill
services and scripts remain available as separate infrastructure. Its legacy
policies are explicitly API_SOURCE_POLICIES/get_api_source_policy; official
SOURCE_POLICIES/get_source_policy describe Platts. market_instruments retains
collection metadata, while its public instrument response describes official KPIs.

GET /api/market/latest and /history now expose official Platts data only.
GET /api/dashboard/snapshot and /api/market/historical use the same lineage.
POST /api/market/refresh reloads persisted assessments and does not call a provider;
new assessments require Admin workbook upload. Legacy API backfill can still
populate its separate table, but those rows do not affect the official dashboard.
There is no API fallback, including when a Platts series is missing. The frontend
also rejects non-Platts or wrong-code payloads, including from an older backend.
No new live-market context section is implemented.

Future automation may extend a historical series only after verified equivalence
of commodity/grade, geography, pricing basis, units/currency, assessment methodology
and timing. API proxy/futures histories must never be merged into Platts histories.

## Limitations

Updates remain manual workbook assessments. This is not a live Platts feed.
External database/network latency remains operationally relevant; the source
alignment does not change Supabase credentials, connection policy or unrelated
Shipping/News/Calendar/Pulse functionality. No new provider was introduced.


## Controlled verification (16 October 2026)

The refreshed Daily Trading Risk Dashboard 1.xlsx was imported through the real
running backend: 0 inserted, 2,656 updated/unchanged, and 2,656 rows before/after.
The API observation-table fingerprint remained unchanged. Direct backend snapshot
and historical responses agreed on all seven codes, native values, dates and z-scores.
Each latest assessment is 2026-10-14; each 90D window contains 63 observations.
Five long histories have 452 total observations, Forcados 199 and WTI 197.
All current absolute z-scores are below 2; no material outliers qualify.

Subsequent live Supabase reads intermittently stalled and returned SSL unexpected
EOF errors, including unrelated endpoints. No credentials/connection settings were
changed. Large provenance fields are excluded from per-point card queries; latest
provenance is loaded separately when required. Full hash/file provenance stays stored.

Controlled Chrome verification therefore used the same real workbook in an ignored,
isolated SQLite backend and a temporary Node proxy, retaining the recorded baseline
risk register. It exercised real API routes, frontend code and all seven selectors,
without fabricated market responses or external Gemini calls. This verifies UI/data
alignment; it does not certify live Supabase availability. Temporary QA servers are
stopped after verification; the normal local development servers remain separate.

Recorded baseline -> controlled corrected-source result:
- Market Risk: High -> High.
- Macro/Geopolitical: High -> High.
- Company Exposures: Catastrophic -> Catastrophic.
- Overall Risk: Catastrophic -> Catastrophic.
- Primary Driver: Company Exposures -> Company Exposures.
- Triggers: 0 Low | 0 Moderate | 2 High | 1 Catastrophic -> unchanged.

These are measured outputs, not hardcoded references. Native source values changed;
existing deterministic threshold and weight definitions were not edited.


Final checks: backend 271 passed, frontend 109 passed, proxy 1 passed;
21 source/public asset pairs match. No schema change; Alembic head remains
0011_intelligence_synthesis. No secrets tracked. No commit or push performed.
Desktop controlled Chrome verification passed with no JavaScript exceptions.
Mobile assessment labels remain legible; the existing sparkline SVG overflows its
card's internal width and is clipped by the card. This existing chart sizing issue
was observed and left outside this source-policy task; no dashboard redesign was made.


## Final normal-environment verification — 16 October 2026

Status: **PARTIAL / NOT FULLY LIVE-VERIFIED**. This check used the existing
normal Node proxy on localhost:3000, normal FastAPI on 127.0.0.1:8000 and configured
development PostgreSQL/Supabase transaction pooler (6543). No isolated database,
response substitution, application-code change, credential change or migration
was used for this final live check.

### Reproduction and observed results

- GET /api/market/historical: direct and proxied HTTP 200, identical seven
  codes/native values/dates/z-scores. First requests took 17.99s and 19.03s;
  repeat requests took 13.36s and 19.70s.
- GET /api/dashboard/snapshot: direct and proxied timed out at 25s; repeat
  requests timed out at 35s. A separate attempt saw connection refusal / proxy
  HTTP 503 while the normal backend PID changed from 28116 to 31616.
  The cause of that process replacement was not established; this verification
  did not restart the normal servers.
- Two normal Chrome runs did not render KPI cards within 60s. The historical
  endpoint did respond without a disk/service-worker cache response, and all
  seven historical selectors displayed 2026-10-14, the expected native values,
  charts and z-scores. No JavaScript exceptions were observed.
- The snapshot-dependent top cards, Market-wide Outlier Scan and top/history
  agreement therefore remain **unverified in the normal live browser**.
  One pending-load capture still showed the initial Demo metadata and no cards;
  this is not a validated source or risk result. The frontend request path has
  no request deadline for the initial snapshot, so delayed reads block completion
  of dashboard preparation. No timeout/fallback functionality was changed here.

Reproduce with the existing servers running (read-only):

```powershell
curl.exe --max-time 35 http://127.0.0.1:8000/api/dashboard/snapshot
curl.exe --max-time 35 http://localhost:3000/api/dashboard/snapshot
curl.exe --max-time 35 http://127.0.0.1:8000/api/market/historical
curl.exe --max-time 35 http://localhost:3000/api/market/historical
```

### Connection investigation

Existing configuration uses SQLAlchemy pool_pre_ping=True and disables psycopg
named prepared statements with prepare_threshold=None for the Supabase transaction
pooler. It is unchanged from the approved baseline. No credential or connection
URL is included in this report.

Fresh raw-driver probes resolved DNS in 0.015–0.03s and connected in 1.18–2.44s.
A narrow raw read returned all 2,656 rows in about 12s (13.4s including cleanup).
A full raw-driver read and a first SQLAlchemy read each exceeded a 25s diagnostic
process deadline, even with prepared statements disabled; the latter had not yet
reached its second pooled iteration. A contemporaneous database activity sample
showed zero blocking-lock waiters; most sampled connections were idle/ClientRead.

The fresh-driver failure means stale SQLAlchemy connection reuse alone does not
explain the issue. Evidence points to slow/intermittent database/pooler transport
or result transfer, but does not conclusively distinguish network conditions from
Supabase pooler behavior. Earlier SSL unexpected-EOF failures are recorded above;
this final check reproduced timeouts, not a new confirmed SSL EOF. Provider-side
and network-side telemetry would be needed to isolate the remaining cause.
No speculative production or database-connection change was made.

### Checkpoint and scope integrity

Historical-refresh correction is already committed separately as
`d76a08ca95533d53b0942e65660527b333280010` (`fix: refresh historical analytics from
updated workbook`). Its Market Risk date overlay, idempotent persistence, import
summary and historical-panel refresh remain present. The current uncommitted
work is the Platts-authoritative source-policy refactor and its tests/docs;
there is no outstanding separate historical-refresh commit to make.

Final normal-verification suites: backend 271 passed; frontend 109 passed;
proxy 1 passed. All 21 source/public pairs match; secret scan passed and env
files are ignored/untracked. Threshold/weight files and the existing dashboard
risk aggregation functions match HEAD. No functional edits or commit were made
during this verification; only this documentation section and ignored diagnostic
artifacts were added.
