# Shipping Intelligence — Phase 1 MVP pilot

The collector is a standalone process, never a FastAPI startup task. Only the
Africa / Gulf of Guinea pilot is configured for live collection. There is no
map, route deviation, ETA delay, cargo inference, port congestion, verified
port-call logic, shipping AI or Market Intelligence Pulse integration.

## Architecture and deployment

AISStream WSS → bounded in-memory queue → normalized PostgreSQL writes →
deterministic informational rules → FastAPI → same-origin dashboard proxy.

Apply migration `0009_shipping_pilot` after `0008_historical_market`:

```powershell
.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head
.venv/Scripts/python.exe backend/scripts/run_shipping_collector.py --duration 300
```

Future dedicated Render/background-worker start command, from repository root:

```
python backend/scripts/run_shipping_collector.py --enable-retention
```

No continuous production worker is enabled by this implementation. Deploy one
collector instance only. PostgreSQL session advisory locking prevents concurrent
collectors across hosts; local SQLite uses an OS file lock. Use a direct or
session-mode PostgreSQL connection, not a transaction-mode connection pooler.
FastAPI workers never open AISStream sockets. On graceful shutdown, pending
normalized observations drain and status becomes offline. An expired heartbeat
also displays offline after an abrupt process exit.

Required private backend variables:
- `DATABASE_URL`
- `AISSTREAM_API_KEY`
- `SHIPPING_ADMIN_TOKEN`: shared only by the dashboard proxy and FastAPI for
  authenticated watchlist writes. The proxy can read it from backend/.env locally;
  configure the same secret on both deployed services. It is not sent to browsers.

Existing dashboard authentication uses the Node server's administrator account.
The Shipping watchlist sign-in uses this actual server session; the dashboard's
portable static editing gate is not treated as shipping authorization.

Optional settings:
- `SHIPPING_RETENTION_DAYS=7` (1–365)
- `SHIPPING_STALE_MINUTES=15` (1–1440)
- `SHIPPING_STATIONARY_KNOTS=0.5` (0–5)
- `SHIPPING_HEARTBEAT_SECONDS=45` (20–300)

Detailed history cleanup is opt-in with `--enable-retention`; it remains off for
initial verification. It retains one latest position per vessel as compact current
state even after the detailed-history cutoff. Vessel identity, watchlist and
current event states remain separate. Events keep one current/resolved state per
MMSI/rule, not an unbounded record per broadcast.

## Source and geography

Endpoint: `wss://stream.aisstream.io/v0/stream`. One subscription:
`[3.5,1.5] – [6.7,8.5]`, latitude/longitude corners.

Named subregions:
- Lagos: `[5.9,3.0] – [6.65,3.7]`
- Niger Delta / Bonny–Port Harcourt: `[4.2,6.5] – [5.1,7.6]`
- Other positions in the pilot box: wider Gulf of Guinea.

Classification uses coordinates, never destination text. Wider-Gulf aggregate
counts include both subregions and must not be added to their counts. Additional
regions (Latin America, USA, UK, UAE) remain explicitly unmonitored.

Subscribed types: PositionReport, ShipStaticData, StandardClassBPositionReport,
StaticDataReport, ExtendedClassBPositionReport. The latter two are optional;
normal operation does not depend on their arrival.

## Tables, APIs and rules

Tables: `shipping_vessels`, `shipping_positions`, `shipping_watchlist`,
`shipping_events`, plus `shipping_collector_state` for heartbeat and diagnostics.
MMSI is operational identity. IMO, type, destination, ETA, draught and callsign
remain nullable. All observed identity and voyage fields are AIS-reported, not
verified vessel registries or cargo manifests.

Read APIs:
- `GET /api/shipping/status`
- `GET /api/shipping/vessels?minutes=60&region=lagos&type_code=80`
- `GET /api/shipping/events?active=true&limit=100`
- `GET /api/shipping/regions?minutes=60`
- `GET /api/shipping/watchlist`

Administrator APIs: POST watchlist, PUT/DELETE watchlist/{id}. FastAPI requires
its private shipping-admin header; the proxy strips client-supplied headers,
checks the Node administrator session and same-origin requests, then injects
its private credential. No token is serialized to frontend code or API responses.
Vessel responses are capped at 500 and events at 200; no raw position history is
returned to the dashboard. API reads do not change vessel records or events.

Rules:
- `watched_vessel_seen`: active watched MMSI with a received usable position.
- `no_recent_observation`: gap above configured minutes for a watched vessel or
  one with at least two stored position observations. Unknown/unseen watchlisted
  vessels do not generate invented absence events.
- `stationary_observation`: individual SOG at/below the configured threshold.
- `reported_anchor`, `reported_moored`, `reported_not_under_command`: informational
  events based on the reported navigation status. No sustained-stop inference.

New observations resolve stale-gap events. Changed speeds/statuses resolve
superseded observations. Stale rules sweep while the collector runs; API read
paths suppress outdated positive events and calculate position ages live.
After collector shutdown, new gap events are not generated until collection
resumes, but offline collection status and stale position labels remain visible.

## Quality, time and deduplication

Collector receipt time is system last_seen. Position receipt time is kept
separately: static updates cannot refresh a position. Provider envelope time is
stored independently, and AIS UTC-second is never promoted into a complete
dated vessel-transmission time. Ages clamp at zero for minor clock skew.

ETA raw month/day/hour/minute stays yearless. Values are not used for ETA-delay
rules. Freshly received voyage messages can still contain outdated voyage
information; the UI labels it AIS-reported and possibly stale.

Zero speed/course/heading/time components remain valid. AIS unavailable values
(SOG 102.3, COG 360, heading 511, UTC-second 60+, nav 15, draught 0, IMO 0 and
invalid IMO checksums) normalize to null. Invalid decoded messages and invalid
coordinates are rejected. Class B multipart updates join by MMSI without
requiring the unavailable fields.

Position dedupe fingerprints MMSI, provider timestamp, position/message type
and normalized motion fields. If provider time is absent, a one-second receipt
bucket is used; replay deduplication cannot be perfectly established in that
case. A unique database key also prevents duplicate stored positions.

The reader continuously consumes binary UTF-8 JSON with compression enabled.
A bounded 1,000-record queue separates reads from database I/O. Overflow, invalid
messages, errors, writes and duplicate counts are tracked. Reconnect uses
exponential backoff with jitter (up to ~60 seconds), stopping after eight
consecutive failures. Logs contain status, aggregate counters and exception
types, not credentials or full raw payloads.

## UI and limits

Current Watch, Watchlist, Shipping Exceptions, Regional Activity, and Data
Coverage & Quality remain useful when collection is offline. Tables scroll
inside cards on mobile. Data coverage is based on observed activity, not whether
an area is inside the subscription box. No recent AIS activity means neither
zero vessels nor zero traffic. Static coverage reflects whether voyage context
has ever been received for recently observed vessels; it does not certify the
voyage fields' current accuracy.

Diagnostic evidence indicated silent Lagos coverage and sparse static/voyage
broadcasts. These are disclosed limits, not conditions hidden by fabricated data.
Official operations/schema: https://www.aisstream.io/documentation


## Controlled local verification — 13 October 2026

The development database was migrated and the standalone collector ran for
300 seconds, with graceful drain/shutdown completing after approximately 308s.
Retention cleanup was not enabled. No watchlist entries were manufactured.

- 74 AIS messages / normalized records.
- 52 unique position rows, 36 MMSIs with received usable positions.
- 44 unique vessel identities; 22 static updates / static-context vessels.
- 56 natural current/resolved event records: 35 stationary observations,
  17 reported-moored, 4 reported-anchor. No watchlist alerts were manufactured.
- 0 rejected duplicates, and stored position count equalled distinct dedupe keys.
- Activity in Niger Delta and its inclusive wider-Gulf parent; Lagos had no
  recent observed activity.
- Last collector observation: 2026-10-13 09:34:19 UTC (10:34:19 Lagos time).
- No observed reconnect, provider, malformed-message or persistence errors.

Desktop/mobile browser QA used real stored shipping API responses and verified
online and offline states, local table scrolling, no page overflow, clear quality
warnings and a clean console. The collector is stopped. Stale position labels
were checked with read-only forward-clock evaluation and deterministic fixtures,
without modifying live receipt timestamps or manufacturing live gap events.

Production deployment remains separate: provision exactly one dedicated worker,
configure private environment variables on both proxy/backend, and rotate the
existing dashboard server's seeded/default administrator password before
exposing watchlist administration publicly. That legacy credential was not
changed as part of this pilot. Use HTTPS/secure session-cookie settings for the
production proxy. No production worker or deployment configuration was enabled.
