# Market Intelligence Pulse — Phase 2

## Scope and architecture

Completed Phase-1 documents → accepted findings → deterministic normalization,
window filtering and compatible groups → existing Gemini SDK candidate selection
→ validated extractive synthesis → evidence links → executive cards/drill-down.
Raw files and chunks are never sent to synthesis. Phase-1 ingestion remains in
place; its replacement/deletion transaction now invalidates dependent cards.
No risk-scoring, Risk Advisor, Shipping correlation, calendar creation, downloads,
provider integration, embeddings or chat was introduced.

Migration `0011_intelligence_synthesis` follows `0010_intelligence_pulse`:
- intelligence_synthesis_runs: window, generated timestamp, status, configured
  model version, input fingerprint, metrics, safe failure message.
- intelligence_syntheses: typed cards, dimensions, direction, deterministic
  confidence/basis and expected evidence count, linked to a run.
- intelligence_synthesis_evidence: unique card/finding links with foreign keys
  and evidence fingerprints. Source findings are not duplicated.

The migration was applied to the existing configured development database.
Original files and synthetic verification data remain private and Git-ignored.

## Scope dates and processing bounds

7D and 30D mean inclusive calendar dates, six or twenty-nine days before the
UTC end date. Custom windows allow at most 366 inclusive days. Document report
date is authoritative; missing report dates use upload date solely for scope,
with explicit disclosure, Low confidence and no temporal-change comparison.
Failed, extracting, analysing and otherwise incomplete documents are excluded.
Findings are filtered in SQL before loading: latest 240 eligible findings, at most
32 balanced candidate groups, 60 findings per candidate and 90,000 serialized
candidate characters. Oversized groups are omitted rather than silently losing
critical evidence. Bounds and omission reasons are returned in run metrics.
Only five accepted cards per section, twenty overall. These are bounded subsets,
not a claim to have evaluated all reports if a bound is exceeded.

Commodity/geography/horizon aliases are deliberately narrow (e.g. crude → crude
oil, worldwide → global, short-term → near-term). Signal and direction use the
Phase-1 canonical taxonomy. Unknown dimensions isolate the document; Nigeria
is not merged into Africa, nor WTI into Brent. Near-term groups spanning more
than thirty days are excluded from cross-report comparison. Other horizons must
match exactly. Broad relative horizons are an approximation; semantic equivalence
of arbitrary free-text horizons is not inferred.

## Candidate rules and factual validation

- What Changed compares the latest report-date cohort against earlier dated,
  compatible reports inside the selected window. A changed direction set and a
  non-repeated recent key fact are required. It reports changes in assessments,
  never measured production/price changes. Unchanged/repeated commentary is omitted.
- Cross-Source Signals require aligned bullish, bearish or neutral assessments,
  at least two independent publisher/claim groups and distinct claim text.
- Divergence requires comparable evidence from at least two independent groups.
  Opposing bullish/bearish claims from different publishers are Divergent;
  neutral/directional variation or explicit mixed assessments are Mixed.
  Incompatible evidence is disclosed as Insufficient comparability, not disagreement.
- Watch Next uses low-confidence/unclear/mixed or explicitly forward-looking or
  uncertain findings. It asks for subsequent source clarification without
  manufacturing outcomes, event dates or calendar entries.

Gemini ranks/selects bounded candidates and copies a representative accepted
key_fact. Local Pydantic validation forbids unknown fields; candidate IDs must
exist; the full finding-ID set must match; duplicate IDs/cards and excess cards
are rejected. The representative summary must exactly equal a contributing
key_fact. Invented numeric AND nonnumeric claims are rejected. Card comparisons,
counts, confidence and explanations come from deterministic templates. This
conservative extractive approach avoids trusting a free-form factual paraphrase;
it is intentionally less fluent than unrestricted AI prose. Phase-1 evidence
validation remains the limit of source truth, not independent fact verification.

## Source independence and confidence (evidence-v1)

Display distinct source_organisation and document counts, never raw finding count
as independent-source count. Internally count findings separately. Identical
key-fact claims connect publishers into one claim origin; explicit "according to",
"citing", "reported by" or "via" attribution to a known publisher uses that origin.
Multiple reports from one publisher never add publisher independence. Other is
not an identified independent publisher. Undetected syndication/paraphrase may
remain; source independence is not externally verified.

Confidence is server-computed and Gemini cannot change it:
- Low by default, for one independent source, any low Phase-1 confidence,
  evidence older than thirty days, or any upload-date fallback.
- Medium requires at least two independent claim origins, two reports, no low
  Phase-1 confidence, and all evidence at most thirty days old.
- High requires at least three independent origins and reports, all Phase-1
  confidence high, all evidence at most seven days old, and unanimous direction.
- Divergence is capped at Medium. Age uses the later of current UTC date and
  selected window end, so historical windows cannot manufacture freshness.

Confidence basis records counts, directions, age/reference date, Phase-1
confidence values and rule version. It measures evidence support, not forecast
accuracy or the probability of a trade succeeding.

## API, freshness and failure behavior

- POST /api/intelligence/synthesis/refresh — JSON window_start/window_end;
  existing dashboard admin session at Node, private existing backend header;
  same-origin enforcement and client-header stripping remain intact.
- GET /api/intelligence/synthesis?window_start=...&window_end=... — latest
  completed run and latest attempt for the exact window; public dashboard access.
- GET /api/intelligence/synthesis/{id} — saved run and evidence drill-down.

Refresh is explicit, request-bound, and never performed on page load. Each
refresh creates a new run; history is retained. Failure records a safe message
and leaves the last completed supported result available. Empty evidence makes
an honest empty completed run without a Gemini call. UI exposes busy, empty,
single-source, failed, changed-evidence and bounded-subset states.

Dependent cards/links are deleted transactionally when Phase-1 findings are
replaced or a source document is deleted. Read-time fingerprints also hide
missing, changed or no-longer-completed evidence, including out-of-band database
edits. New/changed source evidence marks an old run stale; no orphan card is shown.
Generated_at and evidence freshness are separate. Batched evidence reads avoid
per-card database round trips.

The controlled run exposed psycopg named-statement collisions on the configured
Supabase transaction pooler. Only psycopg connections to *.pooler.supabase.com
port 6543 now set prepare_threshold=None, following the official guidance:
https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL
Direct PostgreSQL, session pooling and SQLite connection behavior is unchanged.

## Controlled synthetic verification — 14 October 2026

Three clearly synthetic TXT reports were uploaded and processed through the real
Phase-1 extraction, Gemini analysis, validation and persistence APIs. The scoped
window 30 September–6 October isolates these fixtures from the earlier Phase-1
synthetic report. No genuine licensed publisher documents were used.

- Document 2: Synthetic Argus-style; 30 September; two accepted findings.
- Document 3: Synthetic S&P Global-style; 6 October; two accepted findings.
- Document 4: Synthetic Kpler-style; 6 October; four accepted findings.
- Eight findings, three organisations; zero Phase-1 rejected findings.
- Supply agreement: S&P and Kpler bullish; earlier Argus supply bearish.
- Demand divergence: Argus bullish, S&P bearish, Kpler neutral.
- Unique Jet/Nigeria restart uncertainty and weak WTI/USA/unspecified-horizon
  forecast evidence create source-supported review watches, not agreement.

Run 3, generated by the authenticated browser refresh, used all eight findings:
two What Changed, one Cross-Source Signal, two Divergences, four Watch Next.
Nine candidates selected, zero rejected/generated omissions; one unknown-horizon
group excluded from cross-report comparison. Synthesis duration 18.143 seconds.
Original real Phase-1 processing durations were 14.726 / 12.205 / 15.292 seconds;
completed documents were reused for synthesis regeneration without re-analysis.
Every item was checked against source finding IDs, document IDs, exact key facts
and source locators. Expansion showed the publisher, title, report date,
Phase-1 fact and confidence. Desktop 1440px and mobile 390px had no page overflow
and a clean JavaScript console; explicit regeneration created a new saved run.
Synthetic originals/findings/runs remain clearly labelled in the development
application for review. They are fixtures, not real market intelligence.

## Limitations

Exact grouping intentionally misses some semantically related evidence. Change
detection is directional, not free-form numerical time-series comparison.
Publisher attribution/duplicate detection is conservative and heuristic, not a
syndication provenance service. Source-level ambiguities remain visible. Gemini
may omit a valid candidate; rejected and unselected counts are auditable.
Request-bound refresh has no durable job worker or cross-browser single-flight
lock; callers should avoid simultaneous charged refreshes. Processing bounds
and the historical verification fixture scope are disclosed rather than hidden.

## Final validation and changed files

Backend: 228 passed (four existing dependency/workbook warnings).
Frontend: 87 passed. Proxy: 1 passed. All 21 source/public pairs match.
Configured secret-value scan passed across tracked and pending files; .env files
remain ignored/untracked. No dependency was added. No commit or push was made.

Changed files:
- backend/alembic/versions/0011_intelligence_synthesis.py
- backend/app/api/__init__.py
- backend/app/api/synthesis.py
- backend/app/db/session.py
- backend/app/models/__init__.py
- backend/app/models/synthesis.py
- backend/app/providers/ai/gemini.py
- backend/app/schemas/synthesis.py
- backend/app/services/intelligence.py
- backend/app/services/synthesis.py
- backend/tests/test_synthesis.py
- index.html / public/index.html
- intelligence.js / public/intelligence.js
- style.css / public/style.css
- tests/market-architecture.test.js
- tests/market-proxy.test.js
- docs/MARKET_INTELLIGENCE_PULSE_PHASE2.md
