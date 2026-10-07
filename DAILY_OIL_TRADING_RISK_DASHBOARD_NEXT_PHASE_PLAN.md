# Daily Oil Trading Risk Dashboard — Next Phase Implementation Plan

**Date:** 7 October 2026  
**Project:** ADE Market Risk / Daily Oil Trading Risk Dashboard  
**Objective:** Extend the dashboard from a market-risk monitoring MVP into a broader market-intelligence and shipping-risk decision tool, while preserving source integrity, auditability, and the current executive design language.

---

## 1. Executive Direction

The next phase will be implemented **one workstream at a time**, with each workstream fully tested and visually accepted before moving to the next.

### Agreed changes

1. **Remove the Risk by Category selector entirely**
   - Remove the selector from the UI.
   - Do **not** remove the underlying category calculations used by Overall Risk, Today's Triggers, AI context, or other risk logic.

2. **Expand Product Spreads / market analytics to cover all 7 market KPIs**
   - Use the historical Excel workbook as the history source.
   - Preserve instrument definitions, units, dates, and source provenance.
   - Do not mix non-equivalent historical and live series silently.

3. **Add a Shipping Intelligence section**
   - Preferred external source: **MarineTraffic**.
   - Initial geographic focus:
     - Africa
     - Latin America
     - USA
     - UK
     - UAE
   - Highlight only operationally important vessels/events rather than presenting an unfiltered global vessel feed.

4. **Rename `Trader Desk Pulse` to `Market Intelligence Pulse`**
   - This becomes a document-intelligence section driven by uploaded reports/files.
   - Primary source families:
     - Argus
     - CSCS
     - S&P Global
     - Kpler
   - AI will assist with classification, extraction, summarisation, comparison, and signal identification.
   - Every AI-derived statement must remain traceable to the uploaded source document.

---

## 2. Recommended Implementation Order

### Phase 0 — Protect the current working baseline

Before new development:

- Create a Git checkpoint/tag for the current working dashboard.
- Confirm all current frontend and backend tests pass.
- Record the current Supabase schema.
- Preserve the current Render deployment configuration.
- Do not combine the new workstreams into one large code change.

**Definition of done**
- Current dashboard can be restored easily.
- Existing Market Risk, Forward Calendar, News, Risk Advisor, Overall Risk, and admin features remain stable.

---

## 3. Phase 1 — Remove Risk by Category Selector

This is deliberately the smallest change and should be completed first.

### Scope

- Remove the Risk by Category selector/control from the visible dashboard.
- Remove any unused styling and event listeners that exist only for that selector.
- Preserve:
  - category risk calculations;
  - Market / Macro-Geopolitical / Company Exposure ratings;
  - Overall Risk calculation;
  - Today's Triggers counts;
  - Risk Advisor context;
  - admin persistence where still required elsewhere.

### Important rule

**Remove the selector, not the risk-category architecture.**

### Tests

- Overall Risk still renders.
- Today's Triggers still shows the correct counts.
- Risk Advisor still receives category context.
- No orphaned JS errors.
- No layout gap where the selector previously existed.

**Definition of done**
- Selector is gone.
- No business logic changes.
- Existing test suite remains green.

---

## 4. Phase 2 — Expand Product Spreads to All 7 Market KPIs

### 4.1 Instruments in scope

The section should support the seven established market instruments:

1. Brent
2. Naphtha
3. Gasoil
4. Gasoline
5. Forcados
6. WTI
7. Jet Fuel

Because not all seven are literally refined-product spreads, consider renaming the section later to something broader such as:

- **Market Price & Spread Analytics**, or
- **Crude & Product Analytics**

Do not rename it until the desired label is confirmed.

### 4.2 Historical source

Use the historical Excel workbook as the controlled history source.

Before ingestion, create an instrument mapping table with:

| Dashboard Instrument | Excel Series Code | Description | Unit | Currency | Frequency | Assessment Basis | Comparable to Live Series? |
|---|---|---|---|---|---|---|---|
| Brent | TBD | TBD | USD/bbl | USD | Daily | TBD | Yes/No |
| Naphtha | TBD | TBD | USD/mt | USD | Daily | TBD | Yes/No |
| Gasoil | TBD | TBD | USD/mt | USD | Daily | TBD | Yes/No |
| Gasoline | TBD | TBD | native source unit | USD | Daily | TBD | Yes/No |
| Forcados | TBD | TBD | USD/bbl | USD | Daily | TBD | Yes/No |
| WTI | TBD | TBD | USD/bbl | USD | Daily | TBD | Yes/No |
| Jet Fuel | TBD | TBD | native source unit | USD | Daily | TBD | Yes/No |

### Critical data-integrity rule

Do **not** create a single statistical series by combining two sources merely because their names appear similar.

Before historical data is allowed to backfill a live instrument, verify:

- same commodity/grade;
- same geography;
- same pricing basis;
- same unit;
- same currency;
- compatible timing/frequency;
- comparable assessment methodology.

If the Excel series and live API series are not directly comparable, keep them as separate labelled series.

### 4.3 Analytics to provide

For each of the seven instruments:

- Latest available value
- Previous observation
- 1D absolute change
- 1D percentage change
- 30D trend
- 30D average
- 90D mean
- 90D standard deviation
- 90D z-score where valid
- observation count
- source
- freshness
- unit

### Spread analytics

Where economically meaningful, calculate spreads such as:

- product vs Brent;
- product vs WTI where relevant;
- Forcados differential to Brent;
- crude benchmark differential;
- optional crack-style relationships only where units/conversions are explicitly validated.

Avoid creating meaningless “spreads” merely to force every instrument into the same calculation.

### 4.4 Excel ingestion approach

Create a reusable historical-market import pipeline:

**Excel upload → validation → instrument mapping → unit normalisation → deduplication → database persistence → analytics**

Store at minimum:

- instrument key;
- source code;
- assessment date;
- original value;
- original unit;
- normalised value where applicable;
- source file name;
- import timestamp;
- row/source reference;
- source/provider label.

Recommended dedupe key:

`instrument_key + assessment_date + provider/source_code`

Never silently overwrite a different source.

### 4.5 UI direction

Do not create seven giant charts.

Recommended executive structure:

- compact selector/tabs for the seven instruments;
- one main historical chart;
- small metric strip for latest / 1D / 30D / 90D;
- optional spread comparison selector;
- source + observation-count disclosure.

**Definition of done**
- All seven instruments are selectable.
- Excel history is traceable.
- Missing values remain missing.
- No non-comparable source mixing.
- Statistical calculations have tests.
- Existing Market Risk cards remain unaffected.

---

## 5. Phase 3 — Shipping Intelligence

### 5.1 External source strategy

Preferred provider: **MarineTraffic**.

Use an authorised API/data service rather than scraping the public website.

MarineTraffic exposes AIS-related information including vessel positions and, depending on the purchased service, vessel/voyage/port-call information.

### Important commercial dependency

MarineTraffic API access is a separate service from ordinary online-plan access. Before production integration, confirm:

- API entitlement;
- API key;
- endpoint package;
- call limits;
- permitted historical depth;
- permitted vessel/port fields;
- production usage/licensing terms.

### Development strategy if API access is not yet available

Build a provider adapter now:

`ShippingProvider`

with implementations such as:

- `MarineTrafficProvider`
- `MockShippingProvider`
- optional future `KplerAISProvider`

This prevents the UI and database model from being tightly coupled to one vendor.

### 5.2 Geographic focus

Initial dashboard filters:

1. **Africa**
2. **Latin America**
3. **USA**
4. **UK**
5. **UAE**

These are mixed geographic levels, so implement them as **Region Groups**, each containing explicit countries/ports.

Example:

```text
Region Group: UAE
Countries: United Arab Emirates
Ports: Fujairah, Jebel Ali, Ruwais, etc.

Region Group: UK
Countries: United Kingdom
Ports: selected crude/product ports

Region Group: Africa
Countries/ports: controlled watchlist rather than every African port
```

Do not rely on free-text continent matching.

### 5.3 First-version shipping KPIs

For each region group:

- vessels currently in scope;
- arrivals expected next 24h / 72h / 7d;
- recent departures;
- vessels at anchor;
- vessels underway;
- stale AIS count;
- delayed / ETA-change count where data supports it;
- relevant tanker count;
- top active ports.

Each important vessel/event row should contain:

- Vessel name
- IMO / MMSI
- Vessel type
- Flag
- Current region / position
- Origin / last port
- Destination
- ETA
- Speed
- Draught/load condition where available
- Last AIS timestamp
- Data source
- Reason it is highlighted

### 5.4 “Important” shipping logic

Start rule-based, not AI-based.

Suggested priority score:

#### High priority
- vessel is on explicit company/watchlist;
- tanker/product carrier relevant to dashboard coverage;
- ETA within configured horizon;
- material ETA slippage;
- route diversion;
- unusually long anchorage;
- stale AIS for a watched vessel;
- unusual speed/stop behaviour;
- important monitored port congestion.

#### Medium priority
- relevant vessel approaching monitored region;
- normal arrival/departure of significant tanker;
- route/port activity worth watching.

#### Information
- normal activity without a risk trigger.

AI may later explain a flagged event, but **AI should not decide whether the raw AIS event occurred**.

### 5.5 Shipping database model

Recommended tables:

- `shipping_region_groups`
- `shipping_ports`
- `shipping_watchlist`
- `shipping_snapshots`
- `shipping_alerts`

Key fields should preserve provider, IMO/MMSI, timestamps, route/port metadata, current position, ETA, and alert reason.

### 5.6 Shipping UI

Recommended new navigation item:

**Shipping Intelligence**

Layout:

1. Region tabs: Africa | Latin America | USA | UK | UAE
2. Summary KPI strip
3. Important vessel/event table
4. Optional compact map later
5. Port congestion / arrivals panel later
6. Source freshness disclosure

Do not begin with a large decorative map. The first version should prioritise **exceptions, arrivals, delays, and watched vessels**.

**Definition of done**
- At least one authorised shipping source works end-to-end.
- Region filtering is deterministic.
- Important vessels/events have explainable rule-based triggers.
- API failures produce stale/unavailable states, not fake zeroes.
- Call limits are respected.
- No API key is exposed to the browser.

---

## 6. Phase 4 — Market Intelligence Pulse

### 6.1 Rename

Rename:

**Trader Desk Pulse** → **Market Intelligence Pulse**

This becomes the dashboard’s structured intelligence layer for uploaded proprietary/industry reports.

### 6.2 Source families

Initial document sources:

- Argus
- CSCS
- S&P Global
- Kpler

Include `Other` as a controlled fallback.

The source should be selected by the uploader or detected by AI and confirmed by the user.

### 6.3 Upload capability

Supported MVP file types:

- PDF
- DOCX
- XLSX
- CSV
- TXT

Optional later:
- PPTX
- email/message ingestion
- direct licensed APIs

Upload workflow:

`Upload → store file → parse → classify → extract → validate → publish intelligence`

The original uploaded file must remain the source of truth.

### 6.4 AI extraction schema

AI should extract structured findings rather than produce one long summary.

For every meaningful finding:

- Source agency
- Document/report title
- Publication/report date
- Upload date
- Commodity
- Geography
- Market segment
- Signal type
- Direction: bullish / bearish / neutral / mixed
- Time horizon
- Key fact
- Key numerical values
- Driver
- Risk implication
- Confidence
- Source page/sheet/section
- Extraction timestamp

Suggested signal taxonomy:

- Price
- Supply
- Demand
- Refining
- Inventory
- Shipping / flows
- OPEC+
- Sanctions
- Geopolitics
- FX
- Macro
- Trade flow
- Forecast
- Maintenance / outage
- Other

### 6.5 AI guardrails

AI is an analyst assistant, not the source.

Requirements:

- Every finding must have source provenance.
- For PDFs/reports, retain page references.
- For Excel, retain sheet/row/range where possible.
- No unsupported numbers.
- Missing information must remain missing.
- Do not merge conflicting reports into a single “fact”.
- Preserve contradictory signals.
- Avoid long verbatim reproduction of proprietary reports.
- Uploaded/licensed documents remain private and access-controlled.
- AI summary should distinguish source fact, model interpretation, and cross-source inference.

### 6.6 Market Intelligence Pulse UI

Header:

**Market Intelligence Pulse**  
`Upload Intelligence` button  
`Refresh Analysis` button

Source strip:

- Argus
- CSCS
- S&P Global
- Kpler

Show latest document date / document count / freshness.

Main intelligence blocks:

1. **What Changed** — top new signals since prior upload/analysis.
2. **Cross-Source Signals** — areas where multiple sources agree.
3. **Divergence** — areas where sources materially disagree.
4. **Watch Next** — short forward-looking monitoring list.
5. **Source Findings** — expandable source-specific cards with citations/page references.

Filters:

- Source
- Commodity
- Geography
- Date
- Signal type
- Direction

### 6.7 Document database model

Recommended tables:

- `intelligence_documents`
- `intelligence_findings`
- `intelligence_analysis_runs`

Store original file metadata, file hash, report date, source agency, extraction status, structured findings, source locators, and analysis-run metadata.

---

## 7. Phase 5 — Cross-Section Intelligence

Only after Product History, Shipping, and Market Intelligence Pulse are individually stable should they interact.

Possible later integrations:

### Shipping → Risk Advisor
A watched tanker delayed at a key supply port can be referenced by Risk Advisor with source and timestamp.

### Intelligence documents → Market Risk
A report indicating tighter exports can be displayed as qualitative intelligence, **not as a replacement for price data**.

### Market Intelligence → Forward Calendar
A report identifying scheduled refinery maintenance can be promoted to the calendar after analyst review.

### Cross-source confirmation
Price signal + shipping slowdown + multiple intelligence reports pointing in the same direction can be surfaced as a higher-confidence intelligence theme.

Do not automate these cross-links until the individual source pipelines are trusted.

---

## 8. Architecture Principles

### 8.1 Keep deterministic calculations separate from AI

**Deterministic**
- prices;
- spreads;
- z-scores;
- vessel positions;
- ETA calculations;
- freshness;
- event counts;
- risk scores.

**AI-supported**
- document classification;
- document extraction;
- concise summarisation;
- cross-source comparison;
- explaining why an already-detected event matters.

AI must not invent raw market or shipping observations.

### 8.2 Provider adapters

Use provider interfaces for external data:

```text
MarketDataProvider
ShippingProvider
NewsProvider
CalendarProvider
IntelligenceDocumentProcessor
```

This makes MarineTraffic replaceable and allows future Kpler/Argus/S&P licensed APIs without rewriting the UI.

### 8.3 Source provenance everywhere

Every displayed intelligence item should be able to answer:

- Where did this come from?
- When was it published?
- When did we retrieve/upload it?
- Is it fresh?
- Is it raw data, deterministic calculation, or AI interpretation?

---

## 9. Testing Requirements

### Product history
- duplicate dates;
- invalid dates;
- missing prices;
- unit conversion;
- source mismatch;
- insufficient history;
- 30D/90D calculations;
- exact Excel provenance.

### Shipping
- missing AIS update;
- stale vessel;
- duplicate vessel records;
- ETA changes;
- provider timeout;
- rate limits;
- region mapping;
- alert-rule thresholds.

### Intelligence uploads
- duplicate file upload;
- unsupported file;
- corrupt file;
- extraction failure;
- conflicting sources;
- missing report date;
- AI output schema validation;
- source/page citation preservation;
- failed AI call retains original document and prior findings.

### Regression
Every phase must rerun:
- existing frontend tests;
- backend tests;
- source/public asset parity;
- local browser QA;
- Supabase persistence checks.

---

## 10. Recommended Delivery Sequence

| Order | Workstream | Complexity | External Dependency | Recommended Status |
|---|---|---:|---|---|
| 1 | Remove Risk by Category selector | Low | None | Do now |
| 2 | Seven-KPI historical Excel analytics | Medium | Historical workbook | Do next |
| 3 | Shipping Intelligence MVP | High | MarineTraffic API entitlement | Build after history |
| 4 | Market Intelligence Pulse uploads + AI | High | Source documents / AI service | Build after shipping MVP |
| 5 | Cross-source intelligence | High | All prior phases | Final integration |

---

## 11. Immediate Next Action

The **next development task should be Phase 1 only**:

> Remove the Risk by Category selector from the UI while preserving all underlying risk-category calculations and regression-test the dashboard.

After that:

> Build the seven-KPI historical Excel mapping and analytics **before starting MarineTraffic integration**.

The shipping and document-intelligence workstreams should not begin as ad-hoc UI cards. Their provider interfaces, database schema, provenance rules, and access/licensing dependencies should be established first.

---

## 12. Inputs / Decisions Needed Later

These do not block Phase 1.

### For seven-KPI history
- exact Excel historical workbook;
- final source code for each of the seven instruments;
- confirmation of whether current live and historical series are directly comparable.

### For Shipping Intelligence
- MarineTraffic API entitlement/key;
- agreed key ports/routes within Africa, Latin America, USA, UK, UAE;
- any company-specific vessels/IMO numbers to watch;
- definition of an “important” vessel/event for the trading desk.

### For Market Intelligence Pulse
- clarify the exact CSCS source/entity;
- sample Argus, CSCS, S&P Global, and Kpler documents;
- approved file types and maximum file size;
- retention/security requirements for proprietary reports;
- whether source users want page-level citations visible in the UI.

---

## Final Recommendation

Proceed **incrementally**:

**Clean UI → establish seven-instrument history → build shipping data foundation → build uploaded-document intelligence → connect the signals.**

The dashboard already has a strong decision-support core. The next phase should add new data domains without weakening the qualities already established: transparent source provenance, honest missing-data handling, deterministic calculations, controlled AI use, and executive-level presentation.
