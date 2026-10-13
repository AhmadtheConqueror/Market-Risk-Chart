# Controlled AISStream diagnostic

Run from the project root:

```powershell
.venv/Scripts/python.exe backend/scripts/test_aisstream.py --area lagos
```

Only if the Lagos subscription is too quiet, run `--area gulf` after the first
run has finished. The fixed geographic boxes are deliberately not global.
Each run stops at 30 distinct MMSIs or 60 seconds, with at most three sequential
connection attempts and exponential backoff with jitter. It uses the official
WSS endpoint, requests permessage-deflate compression, subscribes immediately,
and continuously decodes text or binary UTF-8 JSON messages.

The key is read from AISSTREAM_API_KEY in the process environment or backend/.env.
Never enable WebSocket debug/frame logging. Provider error payloads are withheld;
only sanitized vessel rows, field counts and connection summaries are printed.
No AIS data is persisted and no Supabase connection is used.

`websockets==16.1.1` is now explicitly pinned because the diagnostic directly
imports it. This exact version was already installed through google-genai;
no additional client framework, worker or infrastructure is introduced.

Missing AIS sentinel values are treated as unavailable: SOG 102.3, COG 360,
heading 511 and navigation status 15. Numeric zero remains valid. Time is the
full metadata timestamp when available, otherwise local receipt time (labelled).
Metadata freshness alone does not establish transmission freshness; the AIS
position-report Timestamp contains only the UTC second within the minute.

Official requirements: https://www.aisstream.io/documentation


## Diagnostic 2 — static/voyage coverage

```powershell
.venv/Scripts/python.exe backend/scripts/test_aisstream_quality.py --area all --seconds 180
```

The areas are tested sequentially (one active connection):

| Area | Southwest latitude/longitude | Northeast latitude/longitude |
|---|---|---|
| Lagos approaches | 5.9, 3.0 | 6.65, 3.7 |
| Niger Delta / Bonny–Port Harcourt | 4.2, 6.5 | 5.1, 7.6 |
| Wider Gulf of Guinea | 3.5, 1.5 | 6.7, 8.5 |

Each area runs for 180 seconds by default; `--seconds` accepts 180–300.
Subscriptions include PositionReport, ShipStaticData, StaticDataReport,
StandardClassBPositionReport and ExtendedClassBPositionReport. Correlation is
by MMSI and stays in memory. Output is limited to aggregate metrics and eight
sanitized combined examples per area. Regional samples overlap geographically;
counts from separate runs must not be added as a unique fleet total.

Field availability means a usable value was seen at least once for that MMSI
within that area's run. Valid earlier values are retained across partial
updates, allowing StaticDataReport parts A and B to join. Extended Class B
position reports can supply a name/type without a separate static message.
Destination, ETA and draught belong to Class A static/voyage broadcasts and
are not assumed available for Class B vessels. AIS type is a ship/type category
code, not a cargo manifest or independently verified cargo description.

Timestamp distinctions:
- Receipt time is the diagnostic machine's UTC clock.
- Envelope time is AISStream metadata; its delivery age is measured separately.
- Position report Timestamp is only a UTC second (0–59), not a full dated time.
- Last position envelope/receipt times update only on usable position reports;
  cached metadata coordinates on static messages do not refresh a position.
- Static envelope/receipt times refer to arriving static/voyage messages,
  not independent verification that the voyage fields remain current.

ETA has no year: valid month/day/hour/minute components are reported without
inventing a year. ETA hour/minute zero are valid; month/day zero, hour 24 and
minute 60 are unavailable. IMO zero/invalid checksums are unavailable. Type
zero/reserved values, draught zero, invalid decoded messages and placeholder
strings are unavailable. Draught 25.5 is the saturated 25.5m-or-more value.
No UI, collectors, database tables, or persisted vessel records are created.
