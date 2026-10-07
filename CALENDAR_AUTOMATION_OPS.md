# Forward Calendar Automated Refresh Operations

This operational note documents the automated daily ingestion and persistence architecture for the Forward Calendar.

---

## 1. Production Scheduled Command

From the `backend/` directory:
```bash
python scripts/refresh_calendar.py
```

Or from the workspace root:
```bash
python backend/scripts/refresh_calendar.py
```

The script:
1. Connects directly to the authoritative database (`calendar_events` table).
2. Executes the existing service layer function `refresh_calendar_events()` without duplicating provider logic.
3. Implements isolated provider error boundaries: individual provider failures do not discard stored data or block other providers.
4. Outputs a concise run summary with UTC and West Africa Time (WAT) timestamps.
5. Returns exit code `0` on normal completion (including partial provider failures where existing events are preserved) and exit code `1` only on fatal job/database connection errors.

---

## 2. Schedule and Timezone

- **Target Schedule**: Once daily at **06:00 West Africa Time (WAT)**.
- **Timezone Alignment**: Nigeria is UTC+1 year-round. In UTC-configured schedulers:
  - **UTC Time**: **05:00 UTC**
  - **Cron Expression**: `0 5 * * *`
- **Cadence Rationale**: Macro, central bank, and energy calendars publish dates on periodic schedules rather than minute-by-minute feeds; a single daily morning refresh at 05:00 UTC ensures all trading-day calendars are up to date before market open.

---

## 3. Deployment Scheduler Configuration

The deployment-native scheduler is defined in [`render.yaml`](../render.yaml):

```yaml
services:
  - type: cron
    name: forward-calendar-daily-refresh
    runtime: python
    rootDir: backend
    schedule: "0 5 * * *"
    buildCommand: pip install -r requirements.txt
    startCommand: python scripts/refresh_calendar.py
    envVars:
      - key: DATABASE_URL
        fromService:
          type: web
          name: daily-oil-risk-backend
      - key: SUPABASE_URL
        fromService:
          type: web
          name: daily-oil-risk-backend
      - key: SUPABASE_KEY
        fromService:
          type: web
          name: daily-oil-risk-backend
      - key: ENVIRONMENT
        value: production
```

### Architectural Guarantees
- **No In-Worker Loop**: Schedulers (e.g. APScheduler) are intentionally **NOT** loaded inside FastAPI worker processes. This prevents duplicate cron executions across multiple web workers or serverless restarts.
- **No Standalone Server Required**: Render Cron Jobs spin up an ephemeral container on the cron schedule, execute the script, and terminate, avoiding the cost and overhead of an always-running background server.
- **Direct Service Invocation**: Does not rely on unauthenticated HTTP requests or public endpoints.

---

## 4. Required Environment Variables (Names Only)

The scheduled job requires the same backend database configuration as the FastAPI application:

- `DATABASE_URL` — PostgreSQL connection string (Supabase transaction/session pooler or direct URI).
- `SUPABASE_URL` — Supabase project API URL.
- `SUPABASE_KEY` — Supabase service key.
- `ENVIRONMENT` — Runtime mode (`production`, `development`, or `test`).

*Never commit environment files or secret values into version control.*

---

## 5. How to Run Manually

### Local Development / Testing
From root:
```powershell
.\.venv\Scripts\python.exe backend\scripts\refresh_calendar.py
```

From backend:
```powershell
..\.venv\Scripts\python.exe scripts\refresh_calendar.py
```

### Via HTTP API (Controlled / Admin Trigger)
If the backend is running, the endpoint can also be triggered via HTTP:
```bash
curl -X POST http://localhost:8000/api/calendar/refresh
```

### Windows Task Scheduler (Local Fallback Only)
For local workstation testing, create a scheduled task:
- **Action**: Start a program
- **Program/script**: `C:\SOURCE CODES\ADE MARKET RISK\.venv\Scripts\python.exe`
- **Arguments**: `backend\scripts\refresh_calendar.py`
- **Start in**: `C:\SOURCE CODES\ADE MARKET RISK`
- **Trigger**: Daily at 06:00 (Local time)

*(Note: Production runs on the cloud host cron job so that workstation uptime is not required.)*

---

## 6. How to Diagnose a Failed Provider

When executed, the script logs a structured summary:
```text
============================================================
Forward Calendar Refresh
Timestamp: 2026-10-07T13:21:39Z / 2026-10-07 14:21:39 WAT (UTC+1)
============================================================
Calendar refresh completed
Providers requested: 8
Succeeded:           7
Failed:              1
Created:             0
Updated:             0
Unchanged:           160
============================================================
Warnings / Provider Failures:
  - [opec] OPEC Secretariat: Upstream HTTP 403 Forbidden
============================================================
```

### Troubleshooting Steps:
1. **Identify the Provider**: Check the `[provider_name]` in the warning section.
2. **Failure Isolation**: Verify in the dashboard that existing events from that provider remain displayed; the failure handler prevents deletion of previously verified rows.
3. **Inspect Upstream Provider**: Check `app/providers/calendar/<provider_name>.py` to see the source URL and parsing rules.
4. **Temporary Cloud Glitches**: If an official portal experiences intermittent network errors, the job logs the warning and exits cleanly without polluting the database. The next scheduled run will re-attempt ingestion.
