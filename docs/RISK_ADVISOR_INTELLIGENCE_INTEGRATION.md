# Market Intelligence Pulse → Risk Advisor

## Architecture and boundary

The base dashboard analysis still receives only its existing verified backend
context. Persisted, validated Phase-2 cards are selected separately. After a
successful base analysis, an optional second Gemini call receives a compact copy
of the existing Risk Advisor, bounded deterministic market facts and a qualitative
Pulse block. It returns only supplementary Risk Advisor interpretations with
synthesis-card citations. It cannot rewrite the base summary, risks, watches,
other AI sections or any deterministic risk input. A failed optional call leaves
the normal successful analysis intact. Page load never triggers either call.

Market/Company/Macro calculations, weights, thresholds, Overall Risk, Primary
Driver and triggers are untouched. Neither raw uploads/chunks nor rejected
findings enter the supplementary prompt. No Shipping correlation, calendar
creation, trade calls, downloading, provider or chatbot was added.

## Selection and bounded input

Completed persisted runs only; prefer today's default seven-day window, then
thirty-day window, then the latest applicable historical window. Inspect at most
twelve successful runs, with window ends no later than today and at most ninety
days old. Empty or unusable runs permit fallback. Each card is validated through
Phase-2 evidence fingerprints and completed source-document status before AND
after the model call. A card with any synthetic source is excluded as a whole.

Only stored High/Medium cards participate; Low cards are omitted. Divergence is
prioritized (at most three groups), then High confidence. Maximum eight cards,
12,000 serialized Pulse characters (with headroom for aggregate counts), and four
returned advisory statements. Oversized cards are omitted rather than cutting
meaning. Counts are deduplicated across actually supplied evidence; provenance
counts are recalculated from cards actually cited, not every card supplied.

The compact block contains run/window/generation identifiers, stale status,
source/report/finding counts, and what_changed/cross_source_signals/divergences/
watch_next. Cards contain only their ID, type, title/summary, dimensions,
direction, immutable stored confidence and contributing-source count. Finding,
document and publisher IDs/names are retained in server-side audit metadata;
full findings, source locators and raw excerpts are not sent to the advisor call.

## Schema, validation and divergence

RiskAdvisorView adds optional pulse_interpretations (default [], preserving old
records). Each has statement, synthesis_card_ids and relationship:
support/context/offset/uncertainty/background. Base-provider citations are cleared
before enrichment; the base prompt explicitly requires an empty list. The
supplementary prompt distinguishes deterministic facts, qualitative opinions and
conflicting intelligence. It prohibits assigning risk scores to publisher views.

Unknown/duplicate IDs, invented numeric claims, confidence upgrades and explicit
attempts to attribute changed scores/driver to external views are rejected.
Stored confidence and counts are always supplied by the server, not Gemini.
For a topic with a divergence, statements must cite its disagreement and use
uncertainty. If Gemini omits that uncertainty or selects a side, a deterministic
uncertainty statement citing the existing divergence card preserves the conflict.
Divergence statements are prioritized inside the four-statement bound.
Qualitative implications remain AI interpretations requiring analyst review;
ID/numeric validation does not independently prove every semantic inference.

## Freshness and invalidation

RISK_ADVISOR_PULSE_FRESHNESS_HOURS defaults to 72, validated in Settings and
illustrated in backend/.env.example. A run is stale if generation age OR age of
its window end exceeds the limit, or Phase-2 input fingerprints have changed.
Regenerating an old reporting window cannot manufacture fresh intelligence.
Stale statements are background-labelled; attempts to describe them as
recent/current/fresh are rejected. The UI recomputes staleness for saved records.

Deleted/reprocessed evidence cannot be used for a new advisory statement.
Historical analyses are never rewritten: saved provenance is checked against
current cards on read and labelled historical/invalidated or unavailable when
necessary. Optional reads use savepoints; missing tables, failed retrieval and
post-model read errors cannot poison the base-analysis transaction.

## Synthetic protection and verification isolation

Existing fixtures are identifiable by synthetic/fixture/test tokens in document
title or filename; accepted facts beginning with Synthetic or Test fixture are
also excluded. This exclusion applies to the normal path in every environment.
No browser request or environment setting can enable synthetic context. The
request's browser context remains ignored by the authoritative endpoint.
Conservative labels may exclude a genuine document whose title contains these
markers. Unlabelled future synthetic uploads must still be labelled by analysts;
this is metadata-based protection, not a classifier of document truth.

A private service-only _controlled_test argument supports isolated tests; it is
not exposed by the API or configuration. Such provenance explicitly records
controlled_test and renders TEST MATERIAL. Controlled model verification used
only synthetic dashboard fixtures, synthetic accepted findings and in-memory
SQLite, including JSON persistence/reload checks. No synthetic advisor result
was written to the application Supabase database. Fixtures were not deleted.

An initial proposed verification involving real dashboard context was rejected
by automatic approval review before execution. It was replaced with an entirely
synthetic dashboard/report scenario. No real dashboard context was exported for
this verification and no approval remains pending.

## Persistence, API and UI

No migration: existing ai_analyses.input_context_json stores the compact supplied
block, source-ID mapping and used_card_ids under advisor_intelligence. Existing
output_json stores the optional cited statements. These preserve run ID, card
IDs and synthesis generated_at without duplicating reports or source findings.
AIAnalyseResponse and AILatestResponse add optional pulse_provenance metadata.

Existing POST /api/ai/analyse and GET /api/ai/latest remain the interface. Old
records with no integration metadata load normally with no badge. Failed
supplementary processing stores/returns the successful base result without a
fake zero-source disclosure. No database credentials, environment secrets or
source-policy settings were changed.

Risk Advisor retains its three existing cards and gets only a compact disclosure:
actual organisations/signal count, generated date, stored confidence, cited IDs,
staleness and historical-validity warning where needed. Evidence links open the
exact saved run in the existing Market Intelligence Pulse interface, select its
window, and never regenerate it. There is no second evidence browser.

## Controlled Gemini results — 15 October 2026

Both scenarios: three synthetic publisher-style reports, six accepted findings;
Phase-2 synthesis, supplementary advisor processing, and provenance were saved
and reloaded in isolated local databases. One real base Gemini analysis was
reused across scenarios to isolate the effect of intelligence. All model inputs,
including market/macro/risk inputs, were synthetic fixtures.

A — supportive: four validated cards supplied, all four cited (local IDs 1,2,3,4).
Argus, Kpler and S&P Global support High-confidence source groups. Example:
“High confidence cross-source signals indicate global Brent available supply is
expected to tighten in the near-term, adding context to crude market dynamics.”
Advisory step including local persistence/reload: 9.886 seconds.

B — divergent: four cards supplied; two cited (local IDs 1,2). Three organisations.
The demand disagreement retained Medium confidence while supply support was High.
Example: “Divergent assessments introduce uncertainty regarding the near-term
direction of global Brent demand, with comparable sources holding opposing
bullish and bearish views.” No unsupported reconciliation occurred.
Advisory step including local persistence/reload: 7.736 seconds.

Actual dashboard category/Overall/driver/trigger functions were executed against
the synthetic regression fixture before and after loading each advisor result:
- Overall Risk: High → High in A and B.
- Primary Driver: Company Exposures (Catastrophic) → unchanged in A and B.
- Full category summaries, weights and Today's Triggers: identical.
- Deterministic backend inputs in each enriched context: identical.
- Every cited card resolved to a validated synthesis item, finding, source
  document and exact locator. Saved metadata retained only the cited cards.

Browser checks used the real renderers/CSS with the synthetic model responses:
new disclosure wraps at 1440px/390px; source counts, TEST MATERIAL, STALE,
historical invalidation and navigation to the referenced saved run passed with
a clean JavaScript console. The pre-existing three-column Risk Advisor cards
remain compressed at narrow mobile widths; their layout was not redesigned.

## Remaining limits

The optional enrichment adds at most one extra bounded Gemini request to an
explicit successful analysis refresh. It is request-bound, with no durable job
queue. Exact grouping, metadata-based synthetic detection and qualitative
interpretation have the limitations described above. Lookup is bounded to twelve
recent applicable successful runs; unavailable older evidence is omitted.

## Final validation and files

Backend: 256 passed (four existing dependency/workbook warnings).
Frontend: 103 passed. Proxy: 1 passed. All 21 source/public pairs match.
Secret-value scan passed; .env files remain ignored/untracked. Read-only
verification found all four existing development documents marked synthetic
and no Pulse block selected by the normal advisor path; zero external AI calls
were made by that production-exclusion check.

No migration is required. Head remains 0011_intelligence_synthesis.
No commit/push was made. No dependency or credential was changed.

Changed files:
- backend/.env.example
- backend/app/config.py
- backend/app/api/ai.py
- backend/app/schemas/ai.py
- backend/app/providers/ai/gemini.py
- backend/app/services/ai_prompt_service.py
- backend/app/services/advisor_intelligence.py
- backend/tests/test_ai_phase6.py
- backend/tests/test_advisor_intelligence.py
- dashboard.js / public/dashboard.js
- intelligence.js / public/intelligence.js
- style.css / public/style.css
- tests/market-architecture.test.js
- docs/RISK_ADVISOR_INTELLIGENCE_INTEGRATION.md
