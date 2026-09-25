# Daily Oil Trading Risk Dashboard
## Simple Data and Calculation Guide

This guide explains the dashboard in plain English. It is for someone who does not need to understand coding, but needs to know:

- where each number comes from;
- which Excel sheet or Platts symbol feeds it;
- which numbers are calculated by the dashboard;
- which sections are typed in manually by Admin;
- what to do if a metric should be changed or removed;
- whether a value is current legacy data, a future automated source, a derived calculation, AI-generated content, or manual/internal data.

## 1. The Big Picture

### Phase 6 AI interpretation

AI output is interpretive and is never a source of truth. The backend builds a
verified context from stored market observations, calculated statistics and
spreads, official macro indicators, the risk register and active dashboard
content. It includes source/provider metadata, freshness, 30-day history where
available, 90-day statistics, unavailable instruments and data-quality
qualifications. Nulls and missing observations are preserved; the AI must not
fill or interpolate them.

The structured sections are Daily Briefing, Risk Advisor View, Trader Desk
Pulse, Pattern & Inference, Management Actions, Overall Position and Data
Quality Notes. A normal page load reads the latest successful record; a manual
refresh is required to request a new provider analysis.

The dashboard uses five source classifications:

| Type | What it means | Example |
|---|---|---|
| Live automated API source | Comes from OilPriceAPI via FastAPI backend and Supabase PostgreSQL. | ICE Brent Crude Futures and WTI Crude Oil Futures. |
| Controlled internal workbook source | Comes from the validated Admin workbook upload via FastAPI and Supabase PostgreSQL. | Forcados, Naphtha, Gasoil, Gasoline and Jet physical assessments. |
| Official macro publisher source | Comes from official publisher files/pages through FastAPI and Supabase PostgreSQL. This is the active Macro Drivers feed in Phase 5. | NBS CPI, NBS GDP, Stanbic IBTC/S&P PMI, NUPRC crude production. |
| Unavailable instrument | The configured preferred source has no valid observation. The card remains visible with an honest unavailable state; no zero values or cross-source prices leak. | Any benchmark before its preferred source is loaded. |
| Derived calculation | The backend calculation service calculates it from stored observations in Supabase. | 1D change, sample standard deviation, USD/MT to USD/bbl conversion, Product Spreads. |
| Legacy adapter | Retained temporarily in the codebase for static development and rollback testing. Admin production uploads use the FastAPI importer. | Local `excel.js` adapter. |
| Manual/internal data | Someone types it into the dashboard in Admin mode or it comes from an internal business source. | Macro commentary, risk register, management actions. |

The active market pipeline is:
```text
OilPriceAPI → FastAPI Backend → Supabase PostgreSQL → Dashboard API (GET /api/dashboard/snapshot)
```
The browser never talks directly to OilPriceAPI or calculates market values from workbook contents. Provider keys remain server-side.

The Macro Drivers pipeline is:
```text
Official publishers -> FastAPI Backend -> Supabase PostgreSQL -> Dashboard API -> Frontend
```

The browser never talks directly to NBS, Stanbic/S&P, or NUPRC. Macro values are not entered manually in API mode.

## 2.1 Final MVP Hybrid Market Sources

The Admin workbook upload is submitted to FastAPI and validated server-side.
The browser does not parse or calculate market values from Excel. Valid
observations are stored with their actual assessment date, raw value/unit,
`provider=internal_excel`, Platts symbol, retrieval timestamp and benchmark
definition.

The source policy is fixed by benchmark: Brent and WTI remain OilPriceAPI;
Forcados, Gasoline and Jet use the internal workbook; the current workbook
definitions confirm that Naphtha and Gasoil are physical Platts benchmarks,
so they also use the internal workbook. If the preferred source is absent,
the benchmark is unavailable rather than silently replaced by a proxy.

All latest values, 1D changes, 30D trends, 90D mean/sample standard deviation,
z-scores, conversions and product spreads operate on the one resolved source
series only.

## 2.2 Automated Energy News

| Source key | Official source | Access method | Canonical region behavior |
|---|---|---|---|
| `eia` | U.S. Energy Information Administration | Today in Energy and press-release RSS | International, or Africa when the content names an African country |
| `opec` | OPEC | Official press-release/news page | International, or Africa for relevant African country coverage |
| `nuprc` | Nigerian Upstream Petroleum Regulatory Commission | Official news API | Nigeria |
| `nnpc` | NNPC Limited | Official insights/news page | Nigeria |

Stored fields are `title`, `source`, external `url`, `published_at`,
`retrieved_at`, short `snippet`, `region`, `topic`, relevance status and
provider metadata. URLs are unique for idempotency. The dashboard keeps only
the recent verified feed in view, while older valid records remain available
in Supabase for audit/history. Missing publication dates, invalid URLs and
missing headlines are rejected; no current date is fabricated.

## 2. Current Legacy Excel Sheets Used

The current workbook in the project is `uploads/active-market-data.xlsx`.

| Excel sheet | What it is used for |
|---|---|
| `Market Risk` | Main market price source. The dashboard finds Platts symbols here, such as `PCAAS00` for Dated Brent. |
| `Crude Supply Risk` | Source for the Crude Supply Risk chart. It contains dates, `ZNR734`, and `PCAAS00`. |
| `PAAAM00_PCAAS00_naphtha_crack_s` | Used for Naphtha conversion/spread data when matching columns are found. |
| `AAVJI00_PCAAS00_Gasoi_crak_spre` | Used for Gasoil conversion/spread data when matching columns are found. |
| `PGABM00_PCAAS00_gasoline_crack_` | Used for Gasoline conversion/spread data when matching columns are found. |
| `PCAAS00_minus_PJAAV00_jet_crack` | Used for Jet conversion/spread data when matching columns are found. |
| `CI.Results_UOM` | Present in the workbook, but not used as the only source of units. The dashboard also uses its own product defaults. |
| `CI.DataDictionary` | Present in the workbook, but not currently used by dashboard logic. |
| `CI.Results` | Mentioned in the original business specification, but the active workbook does not have this sheet. The dashboard currently reads `Market Risk` by finding Platts symbols. |
| `Core_Export_Data` | Preferred name in the code for crude supply data, but the active workbook uses `Crude Supply Risk`. |

Important: the dashboard mostly looks for Platts symbols, not just exact sheet names. So if a symbol appears on another sheet, the dashboard may still find it.

## 3. Current Legacy Platts Symbols

| Dashboard item | Platts symbol | Current Excel source | Unit shown |
|---|---|---|---|
| Dated Brent | `PCAAS00` | `Market Risk` | USD/bbl |
| Naphtha | `PAAAM00` | `Market Risk` | USD/mt |
| Gasoil | `AAVJI00` | `Market Risk` | USD/mt |
| Gasoline | `PGABM00` | `Market Risk` | USD/mt |
| Forcados | `PCABC00` | `Market Risk` | USD/bbl |
| WTI Cushing | `PCACG00` | `Market Risk` | USD/bbl |
| Jet | `PJAAV00` | `Market Risk` | USD/mt |
| Crude Supply Risk | `ZNR734` | `Crude Supply Risk` | volume/risk series |

Plain meaning: a Platts symbol is the current workbook's market-data code for a price or indicator. These are legacy adapter mappings, not permanent instrument IDs. Future providers may use different symbols while the dashboard continues to use internal IDs such as `brent`, `wti`, and `naphtha`.

### 3.1 OilPriceAPI Provider Integration Mappings & Fit Assessment

In Phase 3, live provider integration was established with **OilPriceAPI**. The table below documents the mapping between canonical dashboard instruments and provider symbols, their raw units, and fit status:

| Instrument Key | Canonical Display Name | Canonical Unit | OilPriceAPI Symbol | Provider Name | Provider Unit | Status |
|---|---|---|---|---|---|---|
| `brent` | Dated Brent | USD/bbl | `BRENT_CRUDE_USD` | ICE Brent Crude Front-Month Futures | `barrel` | **Confirmed** |
| `wti` | WTI Cushing | USD/bbl | `WTI_USD` | WTI Crude Oil Front-Month Futures | `barrel` | **Confirmed** |
| `forcados` | Forcados Blend | USD/bbl | *None* | *Not available in OilPriceAPI catalog* | — | **Unavailable** |
| `naphtha` | Naphtha CIF NWE Cargoes | USD/MT | `NAPHTHA_USD` | Naphtha | `metric_ton` | **Candidate Test Proxy** |
| `gasoil` | Low Sulphur Gasoil 10ppm Cargoes | USD/MT | `GASOIL_USD` | ICE Low Sulphur Gasoil Rotterdam | `tonne` | **Candidate Test Proxy** |
| `gasoline` | Premium Motor Gasoline 10ppm | USD/MT | *None* | `GASOLINE_USD` is US RBOB ($/gallon) | `gallon` | **Unavailable (Unit Mismatch)** |
| `jet` | Aviation Jet Fuel CIF NWE Cargoes | USD/MT | *None* | `JET_FUEL_USD` is US Gulf Coast ($/gallon) | `gallon` | **Unavailable (Unit Mismatch)** |

#### Raw Unit Preservation & Dynamic Calculation Rule
- **Database Storage (`market_observations`)**: Always stores the raw observation as received from OilPriceAPI: `value` (e.g. 833.59), `unit` (`metric_ton`), `source_timestamp`, and `retrieved_at`. **No conversion is performed on write**.
- **Calculation Service**: Product conversions to USD/bbl and crack spread calculations against Brent are executed dynamically in the application logic:
  $$\text{Converted Price (USD/bbl)} = \frac{\text{Raw Price (USD/MT)}}{\text{Barrels per MT}}$$
  $$\text{Product Spread} = \text{Converted Price (USD/bbl)} - \text{Brent Price (USD/bbl)}$$
- **History & Z-Score Rule**: If an API tier does not provide historical endpoints (`HTTP 402 Payment Required`), the system records `history_status: "insufficient_history"` and outputs `z_score: null`. Missing history is never fabricated or substituted with legacy data.

## 4. Market Product Cards

These are the small cards in the Market Risk section.

They currently show:

- Dated Brent;
- Naphtha;
- Gasoil;
- Gasoline;
- Forcados;
- WTI Cushing;
- Jet.

| Card value | Where it comes from | Formula / rule |
|---|---|---|
| Latest price | Latest valid price for that Platts symbol in Excel. | Use the most recent nonblank value. |
| 1D change | Latest price and the previous valid price. | `Latest price - Previous valid price` |
| 1D % change | Latest price and previous valid price. | `(Latest - Previous) / Previous * 100` |
| 30D trend | Last 30 calendar days of valid prices. | Shows valid observations only. Missing days are not treated as zero. |
| Z-score | Latest price compared with recent history. | See section 5. |
| Risk label | Calculated from z-score. | Low, Moderate, High, or Catastrophic. |

Important notes:

- Blank Excel cells are ignored.
- Blank does not mean zero.
- A real `0` in Excel is kept as zero.
- The previous value means the previous available valid price, not always the previous calendar day.

## 4.1 Macro Drivers

The Macro Drivers cards are automated official-source indicators in Phase 5. They are no longer hard-coded March/Q4 values and are not populated from Google snippets, news articles, AI guesses, or admin-entered numbers.

| Card | Canonical key | Definition | Official publisher | Source URL | Unit | Frequency | Extraction method | Freshness rule |
|---|---|---|---|---|---|---|---|---|
| Headline Inflation | `headline_inflation` | Nigeria national all-items year-on-year CPI inflation | National Bureau of Statistics Nigeria | `https://microdata.nigerianstat.gov.ng/index.php/catalog/154/related-materials` | `%` | Monthly | Latest CPI ZIP -> Excel workbook -> Table1 national YoY all-items column | Monthly publication cycle |
| Food Inflation | `food_inflation` | Nigeria national food year-on-year inflation | National Bureau of Statistics Nigeria | `https://microdata.nigerianstat.gov.ng/index.php/catalog/154/related-materials` | `%` | Monthly | Same CPI workbook, Food YoY column | Monthly publication cycle |
| Core Inflation | `core_inflation` | Nigeria national all-items less farm produce and energy year-on-year inflation | National Bureau of Statistics Nigeria | `https://microdata.nigerianstat.gov.ng/index.php/catalog/154/related-materials` | `%` | Monthly | Same CPI workbook, Core YoY column | Monthly publication cycle |
| Real GDP Growth | `real_gdp_growth` | Nigeria total real GDP year-on-year growth | National Bureau of Statistics Nigeria | `https://microdata.nigerianstat.gov.ng/index.php/catalog/147/related-materials` | `%` | Quarterly | Latest GDP ZIP -> Excel workbook -> real GDP growth sheet -> total constant-price GDP row | Quarterly publication cycle |
| PMI | `nigeria_pmi` | Headline seasonally adjusted Stanbic IBTC Bank Nigeria PMI | Stanbic IBTC Bank / S&P Global | Public Stanbic IBTC Bank monthly PMI PDF | `index` | Monthly | Latest valid PDF -> headline PMI value and reporting month | Monthly publication cycle |
| Crude Oil Production | `crude_oil_production` | Strict crude oil production, excluding condensate, monthly average daily production | Nigerian Upstream Petroleum Regulatory Commission | NUPRC official production news release | `mbpd` | Monthly | Latest production article -> strict crude-only BPD -> converted to mbpd | Monthly publication cycle |

Each card shows:

- value and unit;
- reporting period;
- source label;
- freshness status.

Crude Oil Production means crude only, excluding condensate. If NUPRC publishes crude plus condensate, that combined value is retained only as metadata and is not used as the card value.

Macro persistence uses the unique combination:

```text
indicator_key + reporting_period + source
```

Re-running a refresh for the same official value returns `unchanged`; a revised official figure updates the existing period and stores revision metadata. Missing macro values stay `null` and display as `Data unavailable`; they are never converted to `0`.

## 5. Z-Score / Sigma

The z-score tells you how unusual the latest price is compared with the last 90 calendar days.

Example: `+2.90 sigma` means the latest price is much higher than its recent average.

Formula:

```text
Z-score = (Latest Price - 90-day Average Price) / 90-day Standard Deviation
```

In simple terms:

| Z-score result | Meaning |
|---|---|
| Positive number | Latest price is above the recent average. |
| Negative number | Latest price is below the recent average. |
| Near zero | Latest price is close to normal. |
| Large number | Price is unusual compared with recent history. |

Risk label:

| Z-score size | Dashboard label |
|---|---|
| Less than 1 | Low |
| 1 to less than 2 | Moderate |
| 2 to less than 3 | High |
| 3 or more | Catastrophic |

The dashboard uses sample standard deviation. That means it divides by `number of observations - 1`.

When the card says something like `63 valid observations`, it means the dashboard found 63 usable, nonblank prices inside the 90 calendar-day window. That number comes from the workbook. It is not typed in manually.

## 6. Today's Triggers

Today's Triggers is the strip at the top of the dashboard showing counts such as:

```text
0 Low    4 Moderate    3 High    0 Catastrophic
```

It is obtained automatically from the Market Product Cards.

| Trigger number | What it means | Where it comes from |
|---|---|---|
| Low count | Number of market products currently rated Low. | Calculated from each product's z-score. |
| Moderate count | Number of market products currently rated Moderate. | Calculated from each product's z-score. |
| High count | Number of market products currently rated High. | Calculated from each product's z-score. |
| Catastrophic count | Number of market products currently rated Catastrophic. | Calculated from each product's z-score. |

Formula:

```text
Today's Triggers = Count of product cards in each risk label
```

Example:

If the seven product cards are:

```text
4 products = Moderate
3 products = High
0 products = Low
0 products = Catastrophic
```

then the top strip shows:

```text
0 Low    4 Moderate    3 High    0 Catastrophic
```

Important:

- Today's Triggers is not manually typed in.
- It is not directly editable in Admin mode.
- It changes when the Excel market data changes.
- It also changes if a developer changes which products are included or changes the z-score thresholds.
- Admin category overrides do not directly change Today's Triggers.

If you want a product removed from Today's Triggers, remove that product from the Market Product Cards list in `dashboard.js` and `public/dashboard.js`.

If you want the trigger thresholds changed, a developer must change the z-score threshold rules in `dashboard.js` and `public/dashboard.js`.

The `Last market refresh` text beside Today's Triggers comes from the workbook refresh/upload time.

## 7. Normalized Market Observation Layer

The legacy adapter converts current Excel/demo series into one provider-neutral observation shape before market calculations run.

| Field | Meaning |
|---|---|
| `instrumentId` | Stable internal ID, such as `brent` or `naphtha`. |
| `providerSymbol` | The symbol used by the source provider. Current legacy examples include `PCAAS00` and `PAAAM00`. |
| `name` | Human-readable instrument name. |
| `value` | Valid numeric observation. Missing values are not converted to zero. |
| `unit` | Source unit, such as USD/bbl or USD/mt. |
| `assessmentDate` | Date assigned to the market observation. |
| `retrievedAt` | Timestamp when the source data was loaded or retrieved. |
| `provider` | Auditable source/provider name. |
| `sourceType` | Source channel, currently `excel` or `demo`; future automated observations use `api`. |

The standalone Dated Brent YTD chart is no longer displayed. Dated Brent data remains active for its market card, z-score/outlier calculations, Product Spreads, and Crude Supply Risk comparison.

## 8. Refined Product Prices vs Dated Brent

This chart compares refined products against Dated Brent on the same USD/bbl basis.

Products compared:

| Product | Symbol | Original unit |
|---|---|---|
| Naphtha | `PAAAM00` | USD/mt |
| Gasoil | `AAVJI00` | USD/mt |
| Gasoline | `PGABM00` | USD/mt |
| Jet | `PJAAV00` | USD/mt |

Dated Brent benchmark:

| Benchmark | Symbol | Unit |
|---|---|---|
| Dated Brent | `PCAAS00` | USD/bbl |

Because the products are in USD/mt, the dashboard converts them to USD/bbl before comparing with Brent.

Fallback conversion factors:

| Product | Symbol | Barrels per metric ton |
|---|---|---:|
| Naphtha | `PAAAM00` | 8.90 |
| Gasoil | `AAVJI00` | 7.44 |
| Gasoline | `PGABM00` | 8.33 |
| Jet | `PJAAV00` | 7.70 |

Formula:

```text
Product USD/bbl = Product USD/mt / barrels per metric ton

Spread vs Brent = Product USD/bbl - Dated Brent USD/bbl
```

Meaning:

| Result | Meaning |
|---|---|
| Positive spread | Product is above Brent. |
| Negative spread | Product is below Brent. |

If the Excel workbook already contains a converted USD/bbl value and conversion factor, the dashboard uses the workbook conversion first. If not, it uses the fallback factors above.

## 9. Crude Supply Risk Chart

This is the chart called `Crude Supply Risk Total Global Price Risk`.

| Item | Detail |
|---|---|
| Current Excel source | `Crude Supply Risk` sheet |
| Preferred code name | `Core_Export_Data` |
| Date column | `Timestamp` |
| Supply risk column | `ZNR734 | CRUDE SUPPLY RISK TOTAL GLOBAL PRICE RISK : VOLUME` |
| Brent column | `PCAAS00 | DATED BRENT(USD/BBL) : CLOSE` |
| Time buttons | 1M, 3M, 6M, 9M, 1Y |

What it shows:

| Line | Meaning |
|---|---|
| Dated Brent | Price of Brent in USD/bbl. |
| Crude Supply Risk | ZNR734 volume/risk series. |

Rules:

- It uses exact dates from Excel.
- Blank cells stay blank.
- It does not fill missing values.
- It does not guess a value from the nearest date.
- It does not convert blanks to zero.
- If there is a gap in the data, the chart keeps the gap.

## 10. Overall Risk Position

The dashboard has four risk levels.

| Risk level | Score |
|---|---:|
| Low | 1 |
| Moderate | 2 |
| High | 3 |
| Catastrophic | 4 |

The overall risk is calculated from three categories:

| Category | Weight |
|---|---:|
| Market Risk | 1.0 |
| Macro/Geopolitical Risk | 1.1 |
| Company Exposures | 1.0 |

Formula:

```text
Overall score = Weighted average of the three category scores
```

Rating rule:

| Overall score | Overall rating |
|---|---|
| 3.25 or higher | Catastrophic |
| 2.50 to less than 3.25 | High |
| 1.75 to less than 2.50 | Moderate |
| Less than 1.75 | Low |

Admin can manually override the category ratings. If Admin overrides a category, the overall risk will use that override.

## 11. Manual Sections

These sections are not calculated from Excel. Admin types them in.

| Dashboard section | Who updates it | Stored where |
|---|---|---|
| Daily Briefing | Admin | Browser local storage |
| Risk Advisor's View | Admin | Browser local storage |
| Trader Desk Pulse | Admin | Browser local storage |
| Macro Drivers values | Official macro publishers | Supabase PostgreSQL via FastAPI |
| Macro commentary | Admin | Browser local storage |
| Pattern & Inference | Admin | Browser local storage |
| Geopolitical Risk | Admin | Browser local storage |
| Risk Register | Admin | Browser local storage |
| Management Actions | Admin | Browser local storage |
| Forward Calendar | Admin | Browser local storage |
| Risk by Category override | Admin | Browser local storage |

Admin login:

| Username | Password |
|---|---|
| `riskadmin` | `Password123` |

Security note: this is only a simple lock inside the browser page. It is not strong security like a real company login system.

## 12. Excel Upload / Refresh

How market data is refreshed:

```text
Admin logs in
-> clicks Load / Refresh Excel
-> selects the latest .xlsx workbook
-> dashboard reads the workbook
-> charts and calculated numbers update
```

The browser does not permanently remember the Excel file. If the workbook changes, Admin may need to load it again.

## 13. Missing Data Rules

The most important rule is:

```text
Blank is not zero.
```

| Situation | What the dashboard does |
|---|---|
| Blank Excel cell | Treats it as missing. |
| Real zero in Excel | Keeps it as zero. |
| Missing price day | Does not create a fake price. |
| Weekend or holiday with no value | Ignored in calculations. |
| Missing value inside a chart | Leaves a gap where relevant. |
| Previous price missing | Uses the previous valid available price. |

The dashboard does not interpolate, forward-fill, backward-fill, or guess missing values.

## 14. If You Want To Change Or Remove A Metric

This is the practical part.

There are usually two places to think about:

| Place | Why it matters |
|---|---|
| Excel workbook | Controls whether the data is available. |
| Dashboard code files | Control whether the dashboard looks for the metric and displays it. |

Removing a metric from Excel alone may not be enough, because the dashboard has a list of expected symbols in the code.

Changing the code alone may not be enough, because the new metric also needs to exist in Excel.

## 15. Example: Remove Dated Brent From The Dashboard

Dated Brent is not just one item. It appears in several places.

| Place where Dated Brent appears | What uses it |
|---|---|
| Market product card | Shows latest Dated Brent, 1D change, 30D trend, and z-score. |
| Dated Brent Price Trend chart | Shows monthly average Brent price. |
| Product Spreads chart | Uses Brent as the benchmark for product spreads. |
| Crude Supply Risk chart | Shows Brent line beside the `ZNR734` risk line. |

So first decide exactly what you mean by "remove Dated Brent".

### Option A: Remove Only The Dated Brent Product Card

Use this if you do not want Dated Brent to appear as one of the small Market Risk product cards, but you still want it available for charts and spreads.

Excel action:

- You do not need to remove `PCAAS00` from Excel.
- Keeping it in Excel is safer because other charts still need it.

Code action for developer:

| File | What to change |
|---|---|
| `dashboard.js` | In `PRODUCT_ORDER`, remove the Dated Brent entry with `marketCode: "PCAAS00"`. |
| `public/dashboard.js` | Make the same change if the app is served from the `public` folder. |

Plain-English instruction to give a developer:

```text
Please remove Dated Brent from the Market Product Cards only.
Do not remove PCAAS00 from the Excel parser because other charts still use Brent.
```

### Option B: Remove The Dated Brent Price Trend Chart

This change has already been made. The standalone Brent monthly-average chart is absent, while `PCAAS00` remains available to the legacy adapter because other dashboard calculations still use Brent.

### Option C: Remove Brent From The Product Spreads Chart

This is a bigger change because the chart is specifically "products vs Dated Brent".

Excel action:

- If you still want spreads, choose a new benchmark symbol first.
- Add the new benchmark to the workbook with the same date format.

Code action for developer:

| File | What to change |
|---|---|
| `charts.js` | Change the Product Spreads chart so it compares products against the new benchmark instead of `PCAAS00`. |
| `excel.js` | Add or map the new benchmark symbol so the dashboard can read it. |
| `index.html` | Rename the chart title so users know the new benchmark. |
| `public/*` copies | Repeat the same changes if the served app uses `public`. |

Plain-English instruction to give a developer:

```text
Please replace Dated Brent as the product-spread benchmark with [new benchmark symbol].
Update the chart title, Excel parser, and calculation so spreads are compared against the new benchmark.
```

### Option D: Remove Brent From The Crude Supply Risk Chart

This also needs care. The current parser expects the `PCAAS00 ... CLOSE` column when finding the Crude Supply Risk data.

Excel action:

- Do not simply delete the `PCAAS00` column from `Crude Supply Risk` unless the code is changed first.
- If it is deleted without a code change, the Crude Supply Risk chart may fail to load properly.

Code action for developer:

| File | What to change |
|---|---|
| `excel.js` | Update the crude supply parser so it does not require the `PCAAS00 ... CLOSE` column. |
| `charts.js` | Update the chart so it draws only `ZNR734`, or draws `ZNR734` plus a new comparison line. |
| `index.html` | Update the chart subtitle/legend wording. |
| `public/*` copies | Repeat the same changes if the served app uses `public`. |

Plain-English instruction to give a developer:

```text
Please remove the Brent line from the Crude Supply Risk chart.
Keep the ZNR734 line working, and update the parser so it no longer requires PCAAS00 in that sheet.
```

## 16. Example: Replace One Product With Another

Example: replacing Naphtha `PAAAM00` with another Platts product.

Excel action:

| Step | What to do |
|---|---|
| 1 | Add the new Platts symbol column to the workbook. |
| 2 | Keep the same date/assessment-date structure. |
| 3 | Make sure values are numeric. |
| 4 | If the product is in USD/mt and needs USD/bbl comparison, provide a conversion factor or confirm the fallback factor. |

Code action for developer:

| File | What to change |
|---|---|
| `dashboard.js` | Change the product name and `marketCode` in `PRODUCT_ORDER`. |
| `excel.js` | Change the product symbol in `PRODUCTS`, update the KRI mapping if needed, and update product details/unit. |
| `charts.js` | If the product is used in the Product Spreads chart, update the product order and conversion factor. |
| `data.js` | Update demo/default labels if the fallback data should match the new product. |
| `public/*` copies | Repeat matching changes if the app is served from `public`. |

Plain-English instruction to give a developer:

```text
Please replace [old product name and symbol] with [new product name and symbol].
The new product should appear in the Market Risk cards, be read from Excel, and be included/excluded from Product Spreads as agreed.
```

## 17. Before You Publish Any Metric Change

Use this checklist:

| Check | What to confirm |
|---|---|
| Excel source | The right Platts symbol exists in the workbook. |
| Latest price | Dashboard latest value matches Excel latest valid value. |
| 1D change | Dashboard change matches latest minus previous valid value. |
| Z-score | Observation count looks reasonable for the 90-day window. |
| Product spreads | Converted USD/bbl and spread make sense. |
| Crude supply chart | Missing data shows as gaps, not zero. |
| Manual sections | Admin-entered text is correct. |
| Overall risk | Category overrides are intentional. |

## 18. Short Formula Reference

| Dashboard number | Formula |
|---|---|
| Latest price | Most recent valid nonblank value |
| 1D change | `Latest - Previous valid value` |
| 1D % change | `(Latest - Previous) / Previous * 100` |
| 90-day average | `Sum of valid values / Count of valid values` |
| 90-day standard deviation | Sample standard deviation of valid values |
| Z-score | `(Latest - 90-day average) / 90-day standard deviation` |
| Today's Triggers | Count of market product cards in each risk label |
| Product USD/bbl | `Product USD/mt / barrels per metric ton` |
| Product spread vs Brent | `Product USD/bbl - Brent USD/bbl` |
| Overall risk score | Weighted average of category scores |
