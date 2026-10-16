# News Phase 1A - foundation, classification and reliability

Baseline: 87c2f2a. Existing providers only: EIA, OPEC, NUPRC, NNPC and African
Energy Chamber. No CNN, BBC, Al Jazeera, Bloomberg, Nairametrics or Proshare
adapter was added. No new Gemini call, migration, active schedule or deployment
configuration change. No commit or push.

## Loading and presentation

Before: initialization awaited three region news GETs and administrator status
before the main render. Now: the market-backed dashboard renders first; News
starts separately and administrator status does not gate rendering. Loading and
failure states are confined to News. Concurrent load calls share one promise;
three region requests are settled independently, preserving valid prior stories
for failed regions while accepting successful results elsewhere. Rendering still
excludes articles older than seven days. Failed reads never substitute empty
success responses or relabel stale articles as fresh. The News read deadline is
12 seconds; market, historical and other request timeouts are unchanged.

Source labels are computed when reading, not written back across old news rows:
EIA/OPEC/NUPRC institutional release; NNPC company release; AEC industry
organization release. Explicit article_kind metadata can identify commentary,
analysis or opinion; no guess is made from a headline containing those words.
Known media classes exist for synthetic tests/future metadata, not integrations.
Unclassified sources are labelled honestly. Original publisher, URL and published
UTC timestamp remain intact; the UI displays publication date/time in WAT.
The section subtitle no longer labels all sources as official institutions.

## Geography and relevance

Classification uses subject/location evidence, with headline focus taking
precedence over incidental excerpt mentions. Nigeria-specific institutions,
companies/refineries, assets and naira/CBN stories map Nigeria regardless of
publisher. Non-Nigerian African subjects map Africa; multi-country Africa stories
use Africa, cross-continent/global/unknown focus uses International without
inventing a specific national focus. Explicitly global headlines are not moved
into Nigeria merely because an excerpt names it. Publisher nationality/defaults
are not used. Synthetic CNN/BBC/other-publisher fixtures test these rules; there
is no new live media collection.

The existing energy-keyword filter and seven-day backend selection window are
unchanged. A successful all-irrelevant collection is now distinguished from a
provider failure, with structured per-provider outcome/fresh/stale/region/rejection
counts. Existing stored source provenance is not rewritten and no mass geographic
backfill is performed; future explicitly requested refreshes use the corrected
classifier. GET /api/news/latest adds source_type and operational diagnostics.
Collapsed provider health shows provider-wide counts; they are not attributed to
an individual empty region. Updated/Partial refresh/Refresh failed remain.

No refresh audit means not yet attempted/recorded; unavailable regional reads are
shown as errors; a valid empty result remains no recent verified stories. Malformed
or unavailable feeds remain failed/partial with detailed backend rejection and
request audits. Previously stored, recent valid articles remain available.

## Refresh and scheduling safeguards

API collection executes in FastAPI's worker pool, so synchronous persistence does
not block the ASGI event loop. Per-provider asynchronous fetch budget: 45 seconds;
existing HTTP request timeout: 20 seconds. Provider savepoint isolation, URL
idempotency, stale-row retention and last-run audit persistence remain intact.

PostgreSQL uses pg_try_advisory_xact_lock with shared key 1313167187. The lock spans
one refresh transaction across API and CLI processes, returns HTTP 409 for overlap,
and releases at commit/rollback/cancellation. Transaction-scoped locks work with
the existing Supabase transaction pooler; session advisory locks are not used.
SQLite uses a process-local nonblocking lock for fixtures/local single-process
use; it is not advertised as a cross-process SQLite production lock.

Existing providers still make zero retries. The shared helper supports at most
one opt-in retry for transport/timeouts or HTTP 429/502/503/504, but no existing
caller enables it. It never retries 403 or challenge pages, honors bounded numeric
Retry-After, and stops for larger/date-form/unknown retry allowances. Retrying or
increasing frequency requires publisher/operational approval first. No access
control evasion or provider-list expansion is present.

Dormant command:

    python backend/scripts/refresh_news.py

This is plan-only: no provider requests and no database access. Explicit --run
would run the existing provider service once; it was NOT invoked during this
phase. The API remains the existing explicit user-triggered refresh mechanism.
No live provider refresh or increased polling was performed for validation.

Before deployment activation, obtain approval for each existing publisher's
intended reuse, automated access cadence/rate/retry limits and content/AI rights;
confirm Render plan cost, approved cadence and Supabase connection capacity.
Only then add a separately approved Render cron service using existing private
environment settings and the --run entry point. No job was added to render.yaml.
Provide bounded runtime/exit monitoring, single-flight outcomes, failed/partial
alerts and an observation period proving actual scheduled item arrival.
Do not place credentials in commands, YAML values or public responses.
The lock holds one database transaction/connection during a refresh; connection
capacity and bounded publisher duration still matter even with overlap excluded.

## Verification

- Backend: 349 passed; frontend: 116 passed; proxy: 1 passed.
- Geography cases: Nigeria subjects from CNN/BBC/synthetic publishers, national
  entities/FX, Nigerian precedence within generic Africa context, Angola focus
  despite Nigeria in excerpts, multi-country Africa, cross-continent, global and
  ambiguous headlines. Fixtures contain only synthetic content.
- Refresh tests: idempotency, failed-source isolation, rollback, all-irrelevant
  versus unavailable, provider deadlines, overlap rejection and lock release.
- Retry tests: default one request, never retry 403, one opt-in transient retry.
- Scheduler default test proves plan-only behavior without requests/database.
- Read-only actual Supabase check: first transaction acquired the shared lock,
  second was excluded, then acquired it after first rollback. No provider calls
  or data writes were made during that check.
- Normal dashboard/CDP: intercepted only News GETs with held then explicitly
  synthetic responses or HTTP 503. Main dashboard rendered 16-instrument state
  and eight cards while News was held and while unavailable; deterministic risk
  matched before/after. Exactly three news GETs; zero new publisher requests.
- Source labels/publication times verified at 1440px and 390px, no page overflow
  or uncaught JavaScript exceptions. Existing overall risk remains Catastrophic,
  Primary Driver Company Exposures; Platts scoring/history services are unchanged.
- Live read-only GET retained the previous persisted refresh time
  2026-10-16T11:16:17.159360Z. One recent NUPRC item was institutional; diagnostics
  reported the retained OPEC failure and three relevance rejections across all
  providers. No stored provider audit/news rows were refreshed by this phase.
- Migration head remains 0011_intelligence_synthesis. All 21 source/public pairs
  match; the private tracked/proposed-secret scan passed. Protected Platts, risk,
  Advisor, Shipping, provider-factory and deployment files/functions match HEAD.

Ignored evidence: .venv/phase1-qa/news1a-browser.json, news1a-desktop.png,
news1a-mobile.png, news1a-backend-full.log and news1a-frontend.log.

## Files changed

backend/app/api/news.py; backend/app/models/news.py (computed property only);
backend/app/providers/news/base.py; backend/app/schemas/news.py;
backend/app/services/news_ingestion.py; backend/scripts/refresh_news.py;
backend/tests/test_news_foundation.py; dashboard.js; js/services/newsService.js;
index.html; public copies of those three UI assets; tests/market-architecture.test.js;
this documentation.

Remaining limitations: no active scheduler, no new publisher rights/integrations,
no historic geographic rewrite, no global deployment run history, no fix claimed
for underlying variable Supabase transport. A provider request or database stall
can still affect its own refresh outcome; News no longer gates main rendering.
