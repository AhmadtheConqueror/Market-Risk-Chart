# Market Intelligence Pulse — Phase 1

## Architecture and boundaries

Analyst upload → immutable private original → deterministic format extraction
→ source-located chunks → existing server-side Gemini SDK → strict schema and
local evidence validation → selected-report findings/evidence UI.

This is separate from Risk Advisor, market scoring, Shipping Intelligence,
Forward Calendar, Macro Drivers and cross-source synthesis. The former manual desk panel has since been retired; stored browser notes are
left untouched, with no active UI or AI-context consumer. No external reports are downloaded.

Migration `0010_intelligence_pulse` follows `0009_shipping_pilot` and adds only
`intelligence_documents`, `intelligence_chunks`, `intelligence_findings`.

## Storage and uploads

Original bytes are saved under a SHA-256-derived object name outside public
assets, by default backend/storage/intelligence (ignored by Git). Original
filename, source organisation, analyst-provided title/date, upload timestamp,
validated MIME/type, hash, private storage reference and processing status are
retained. Original bytes are not overwritten during extraction or analysis.

Exact-hash duplicates return the existing document and do not trigger duplicate
analysis/findings. Different hashes remain separate revisions. Deletion is an
explicit administrator action removing findings, chunks, metadata and original.
A retry after AI failure keeps the original, extracted chunks and prior accepted
findings until replacement findings successfully validate and commit.

Uploads accept PDF, DOCX, XLSX, CSV and TXT. Maximum default file size: 20 MB.
Filename path components/control characters are sanitized; names are never used
as storage paths. MIME, PDF signature, Office ZIP structure and archive size are
checked. Macro-enabled archives are rejected. Text/CSV must be UTF-8. Content is
never executed; formulas, links, embedded objects and macros are not evaluated.

The proxy streams multipart bytes without rewriting their boundary. Original
responses preserve binary bytes. Read APIs never expose storage paths. Original
files download as attachments with nosniff and require administrator auth.

## Deterministic extraction

- PDF: page text with real page numbers; layout text retains tables where feasible.
  No OCR, and reconstructed table cell boundaries are not guaranteed.
- DOCX: XML body paragraphs/headings and tables, using standard-library bounded
  ZIP/XML parsing. Locators are paragraph or table/row ranges, not invented pages.
- XLSX: sheet/row cell ranges and values via read-only openpyxl. Cached values
  only; uncached formulas/charts may be unavailable. Numeric zero is preserved.
- CSV: headers plus logical record rows; multiline fields retain physical end-line
  context. Row numbers refer to CSV records, not necessarily physical text lines.
- TXT: original line ranges, preserving contiguous extracted substrings.

Limits default to 60 chunks and 120,000 extracted characters, with 6,000-character
pieces. PDF pages cap at 200; worksheets cap at 10,000 rows/100 columns. Partial,
unreadable and unavailable extraction is reported in limitations. Encrypted PDF
and unextractable/image-only reports fail honestly with the original retained.

No DOCX package dependency was introduced; existing pypdf/openpyxl/Gemini support
is reused. Source text is normalized deterministic extraction, not an assertion
that rendered layout or byte-for-byte document quotations were reconstructed.

## Gemini and validation

A document-scoped request supplies only its metadata and source chunks. It uses
the existing configured Gemini model/key on the backend. No dashboard context,
shipping observations, other reports or Risk Advisor data enter this prompt.

Strict output includes source organisation/title/date, commodity, geography,
canonical signal and direction, horizon, key fact, relevant numbers, driver,
risk implication, confidence, source chunk ID/locator and evidence excerpt.

Signals: Price, Supply, Demand, Refining, Inventory, Shipping/flows, OPEC+,
Sanctions, Geopolitics, FX, Macro, Forecast, Maintenance/outage, Other.
Directions: bullish, bearish, neutral, mixed, unclear. Confidence: low/medium/high.
Recognized casing/spacing is normalized; uncontrolled taxonomy is rejected.

Each finding must match document metadata and an actual chunk ID/locator. The
excerpt must be an exact contiguous substring of the extracted text; key_fact
must be contained in the excerpt. Relevant-number phrases must be literal excerpt
substrings. Numeric tokens in fact/interpretation/horizon cannot introduce values
absent from the excerpt. Unsupported/duplicate findings are counted and omitted.
The key fact is intentionally extractive in Phase 1, while classification and
risk implication remain labelled AI interpretations requiring analyst review.
This does not independently prove semantic truth, source reliability or inference
quality. A summary is deterministically generated from accepted findings.

Missing report dates remain null; Gemini cannot infer a date from report content
or filenames. Original source excerpts are never replaced by AI quotations.

## Processing and APIs

States: uploaded → extracting → extracted → analysing → completed; failures
become failed without deleting originals/chunks. An atomic ten-minute lease
prevents concurrent/repeated processing. Completed reports return existing
results unless reprocess=true is explicitly requested. Restart-interrupted
processing can be retried after lease expiry. Processing is request-bound;
there is no separate durable document-job worker in this phase.

Endpoints:
- POST /api/intelligence/documents (multipart report + source/title/optional date)
- GET /api/intelligence/documents (source/date filters; bounded listing)
- GET /api/intelligence/documents/{id} (metadata + bounded source chunks)
- GET /api/intelligence/documents/{id}/original (authenticated attachment)
- POST /api/intelligence/documents/{id}/process
- GET /api/intelligence/documents/{id}/findings (commodity/geography/signal/direction)
- DELETE /api/intelligence/documents/{id}

Changes/downloads require the existing Node administrator session and private
server-to-server credential. The existing SHIPPING_ADMIN_TOKEN value is reused
behind a separate private intelligence header; client headers are stripped. It
never reaches browser code. No new credential is required. Public read behavior
follows current dashboard conventions; deployed access controls should suit the
reports' confidentiality/licensing before real proprietary reports are uploaded.

UI: upload/sign-in, Recent Reports, Selected Report summary, expandable findings,
evidence/source chunks, source/date and selected-report finding filters. Failed,
empty, partial and processing states are explicit. No cross-document synthesis.

## Operation

```powershell
.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
npm start
```

Use an existing administrator account to upload/process/download/delete.
Production requires durable private storage mounted at INTELLIGENCE_STORAGE_DIR;
local filesystem storage on an ephemeral host alone is insufficient for originals.
Set the existing private proxy credential on both services, and keep Gemini
credentials backend-only. No hosting deployment or external integration is enabled.

Optional settings: INTELLIGENCE_STORAGE_DIR, INTELLIGENCE_MAX_UPLOAD_MB (20),
INTELLIGENCE_MAX_CHUNKS (60), INTELLIGENCE_MAX_EXTRACTED_CHARS (120000).


## Controlled verification — 13 October 2026

Only a clearly labelled synthetic TXT report (Other) was used. It contains no
confidential company/source-provider data. Actual local Node/FastAPI endpoints
and the configured Gemini 2.5 Flash provider were exercised.

One deterministic chunk (TXT lines 1–4) produced three accepted findings:
Price/bullish, Supply/bearish, Refining/bearish, with zero rejected findings.
These are model classifications of a synthetic scenario, not real market facts.
All source locators/excerpts matched stored extracted text. The successful retry
took 18.89 seconds including requests and validation. Original download matched
its SHA-256 and exact duplicate upload returned the same report without creating
findings again.

The initial live request exposed a Gemini 2.5 wire-schema incompatibility with
additionalProperties. The request schema now expands references and removes
unsupported wire-only constraints; strict local Pydantic/evidence validation is
still authoritative. Recovery reused the original/chunk and completed successfully.
No fabricated fallback findings were used.
