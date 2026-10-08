# Supabase application schema snapshot — 8 October 2026

- Snapshot: [supabase-schema-2026-10-08.json](supabase-schema-2026-10-08.json).
- Capture date: **8 October 2026 (Africa/Lagos)**; exact UTC capture timestamp is in the JSON metadata.
- Migration revision verified live: **0007_calendar_events**.
- Provider: Supabase PostgreSQL.
- Supabase project reference (public identifier): `gdstuqxmpqsupuztavqn`.
- Configured application environment: `development`. This is the application's configuration label, not an independently verified Render deployment environment.
- Scope: nine application tables plus `alembic_version` in `public`.
- PostgreSQL catalog capture performed in a repeatable-read, read-only transaction.
- Included: columns and types, nullability, defaults, identity/generated attributes, primary/foreign/unique/check/exclusion constraints, index definitions, table RLS flags, visible policies, relevant enum labels, user triggers, visible table grants and owned sequence definitions.
- Policies found: **0**. RLS enabled on: **0** captured tables. Relevant enum labels found: **0**.
- No secrets, credentials, connection strings, API keys, application row data or sequence current values are included. Role names are schema authorization identifiers, not login credentials.

## Limits

This JSON is a dated structural reference snapshot, not an executable `pg_dump` restore script or a database data backup. Use the versioned Alembic migrations to recreate application tables, and compare against this capture. The Alembic revision is migration metadata, not an application data export.

Supabase-managed `auth`, `storage` and other platform schemas, database users/passwords, global role definitions, extensions, custom function bodies, views, ownership recreation commands and live Render environment settings are outside the capture. Policy/trigger expressions may reference platform functions which must already exist in the destination Supabase project. Table grants and policies reflect objects visible to the configured capture role; absence does not independently prove platform-wide absence. Column-level grants, default privileges and domain definitions are not separately exported.

The existing annotated `baseline-phase0` tag remains on `978bbfedac30003f514cca66982da05dac682c61`, protecting the application baseline. The commit adding this snapshot is a later Phase 0 documentation/protection state. The existing tag is not moved; no replacement tag is created. The final protection commit is identified by remote `main` and the audit report.
