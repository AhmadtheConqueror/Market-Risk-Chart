# Phase 2B — Seven-KPI historical analytics

The approved Phase 2A workbook mapping is independent of OilPriceAPI mappings.
Platts histories are stored in `historical_market_observations` under provider
`platts_excel`. They are never used as API risk-card fallback or concatenated
with API history. Forcados additionally continues its existing
`internal_excel / PCABC00` current-market series.

## Mapping

| Instrument | Platts symbol | Definition | Native unit | Historical bbl/mt | Selected workbook history |
|---|---|---|---|---|---|
| Brent | PCAAS00 | Dated Brent | USD/BBL | — | Naphtha crack sheet, C |
| Naphtha | PAAAM00 | FOB Rotterdam barge | USD/MT | 8.9000 | Naphtha crack sheet, B |
| Gasoil | AAVJI00 | 0.1%S FOB Med cargo, NextGen MOC | USD/MT | 7.3137 | Gasoil crack sheet, B |
| Gasoline | PGABM00 | Premium unleaded 10ppmS FOB AR barge | USD/MT | 8.5286 | Gasoline crack sheet, C |
| Forcados | PCABC00 | FOB Nigeria | USD/BBL | — | Market Risk, R |
| WTI | PCACG00 | Cushing Mo01 | USD/BBL | — | Market Risk, T |
| Jet | PJAAV00 | FOB NWE cargo | USD/MT | 7.7892 | Jet crack sheet, C |

Exact worksheet names and columns are defined in
`backend/app/services/historical_market.py::HISTORICAL_MAPPING`.
The longer authoritative raw histories are selected once, rather than merging
short worksheet copies. Missing values are rejected; numeric zero is retained.
Repeated dates within a selected sheet are rejected and reported.

## Units, windows and chart

API normalization independently routes metric-ton prices through existing API
factors, gallon prices through multiplication by 42, and barrel prices unchanged.
Unknown units have no converted value. Historical factors do not replace API defaults.

Historical product spreads are recomputed from raw USD/MT prices as
`product / historical factor - same-date Platts Dated Brent`. The workbook's
opposite-sign Jet spread is not imported. No spread is calculated for Brent,
WTI or Forcados, or when the same-date Brent assessment is absent.

The section uses one selector and one native-price chart over the latest 90
calendar days. Latest and absolute changes retain the native unit. 1D means
change from the preceding available assessment, including across weekends.
30D/90D changes are latest minus first valid price inside the inclusive
calendar window ending at the instrument's latest observation. Counts refer
to valid observations within those same windows, not a fixed row count.
Historical freshness uses the assessment date (stale after three calendar days),
not the upload timestamp. Stale remains available; absent remains unavailable.

## Persistence and operation

Migration: `0008_historical_market`, following `0007_calendar_events`.
Apply on each target backend before using the new endpoint:

```powershell
.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head
```

Upload the approved workbook through the existing Excel upload flow
(`POST /api/market/import-excel`). Historical storage preserves instrument,
Platts identifier, native value/unit, converted value, factor, assessment date,
source definition, filename, SHA-256 file identity, worksheet and import timestamp.
The unique source/date key makes re-imports idempotent. Re-import updates the
latest provenance for that source/date; this is not an immutable revision archive.

`GET /api/market/historical` supplies all seven independently grouped histories.
The frontend's Reload history button re-fetches this endpoint. No API fallback
is used if history is unavailable.

The audited workbook has 2,488 observations: 428 each for Brent, Naphtha,
Gasoil, Gasoline and Jet; 175 Forcados; 173 WTI. Latest date: 2026-09-10.
At 2026-10-08 all seven are stale. Latest-anchored windows have 21 observations
in 30D; 63 in 90D except WTI, which has 61.

## Unresolved source definitions

Platts Dated Brent is not approved as equivalent to the API Brent series.
Platts WTI Cushing Mo01 equivalence to API WTI remains unconfirmed.
API refined-product geography, grade, delivery basis and provider methodology
are not approved as equivalent to their Platts physical assessments.
Forcados has workbook continuity but no approved automated live feed.
These limitations do not prevent separate historical analytics.
