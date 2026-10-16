# Snapshot bounded reads — 16 October 2026

This optimization preserves the uncommitted Platts-authoritative source policy.
It changes retrieval volume, not source definitions, scoring or calculations.
No migrations, data edits, credentials, SSL options or application timeout changes.

## Retrieval

- Macro: PostgreSQL ranks eligible records per canonical indicator and returns
  only the selected records. Period parsing preserves ISO validation, annual
  December 31, monthly/quarterly day 28, unknown-month January fallback,
  invalid-period minimum ordering, publication timestamp and ID tie-breaks.
  WEO/outlook selection still requires the exact current-year reporting period.
  SQLite fixtures register the existing pure Python parser as a connection-local
  function. No persistent database function or schema change is required.
- Official snapshot history: an aggregate query returns seven date/count anchors.
  The observation query returns each exact Platts series' latest-anchored inclusive
  90-calendar-day window, plus the two latest assessments for sparse-series 1D
  changes, and same-date Brent observations needed for product spreads.
  Sample standard deviation, the 60-observation minimum, units, factors,
  provenance and outlier rules remain unchanged.
- Saved AI: snapshot selects only output_json; saved-analysis validation is
  unchanged. Other saved-analysis endpoints retain their existing behavior.
- The full historical analytics endpoint is unchanged, including full-history
  counts. Older records remain stored; no API observations enter official KPIs.

## Development Supabase measurements

Three interleaved read-only before/after handler comparisons used a preserved
copy of the pre-optimization application. Time was held constant for exact
response comparison; no Gemini or provider collection was invoked.

| Stage | Before median / worst | After median / worst |
|---|---:|---:|
| Historical queries | 2.608 / 5.257s | 0.540 / 0.672s |
| Macro queries | 4.296 / 6.326s | 0.293 / 0.774s |
| Snapshot handler, excluding acquisition | 7.739 / 12.769s | 1.408 / 1.736s |

Historical observations transferred: 2,656 -> 441, plus seven aggregate rows.
Macro retrieval: 15,092 candidates + 18 selected rows -> 18 selected rows.
Fresh acquisition in this comparison was 2.501s; subsequent pooled acquisitions
were 0.130–0.171s. Connection settings were not modified.

Normal HTTP processes: three before samples per path; five successful after
samples per path, including the first successful responses following restart.

| HTTP path | Before median / worst | After median / worst |
|---|---:|---:|
| Direct FastAPI | 11.228 / 31.269s | 4.552 / 8.284s |
| Existing Node proxy | 13.657 / 27.188s | 2.397 / 5.806s |

The final three warmed samples alone were direct 2.114 / 4.552s and proxied
2.306 / 2.397s. During the intentional backend restart, one immediate direct
request could not connect and one proxy request returned 503 before readiness.
Those are recorded as restart availability failures, not successful latencies.
The Node proxy was not restarted or reconfigured. FastAPI was restarted once
with the same development database and normal port to load the edited code.

## Correctness and browser verification

All three complete frozen-time before/after snapshot comparisons were identical:
seven assessments/units/dates, 90D counts and z-scores, all 18 Macro records and
freshness/source fields, spreads, risk register, content and saved AI output.
324 synthetic PostgreSQL period-ordering cases matched the existing Python parser,
including malformed ISO days, leap years, unknown periods and whitespace.
All 8,424 distinct reporting periods currently stored in development Supabase
also produced identical SQL/Python ordering keys (zero mismatches).

Direct and proxied live snapshot responses agree, excluding elapsed/generated
clock fields. Snapshot values, dates, z-scores and counts agree with the unchanged
historical endpoint. All seven latest assessments remain 2026-10-14; each has
63 observations in its 90D window. Stored full-history counts remain:
Brent 452, Naphtha 452, Gasoil 452, Gasoline 452, Forcados 199, WTI 197, Jet 452:
2,656 total.

The normal dashboard was checked in a disposable browser at 1440px and 390px:
seven cards rendered, all seven historical selections loaded, no uncaught JS
exceptions and no mobile horizontal overflow. Overall/category risk and Primary
Driver match the captured pre-optimization browser context: Market High, Macro
High, Company Catastrophic; Overall Catastrophic (3.3225806451612905), Primary
Driver Company Exposures. Today's Triggers remains 0 Low / 0 Moderate / 2 High /
1 Catastrophic. These are current-data results, not hardcoded references.

## Limitations and evidence

Reducing transfer volume does not establish that the underlying intermittent
Supabase/network/pooler condition is fixed. Fresh connections and result delivery
still vary; no TLS/connection exception was reproduced in completed final runs.
The deliberately unchanged full-history endpoint still transfers older history.

Ignored diagnostic evidence lives under .venv/phase1-qa/:
pre-bounded/backend/app (comparison copy), bounded-final-benchmark.json,
bounded-http-before.json, bounded-http-restart-warmup.json,
bounded-http-after.json, bounded-browser.json, bounded-final-checks.json,
bounded-desktop.png and bounded-mobile.png.


Final regression results: backend 282 passed (four existing warnings), frontend
109 passed, proxy 1 passed; all 21 source/public asset pairs match. Known configured
secrets were checked privately against tracked files: no matches; .env and
backend/.env are not tracked. git diff --check passes. All 29 original alignment
files are retained: 27 are byte-identical, while dashboard.py and official_market.py
contain only the additional snapshot optimization. This task additionally changes
macro_ingestion.py and adds test_snapshot_performance.py and this documentation.
No commit or push was performed.
