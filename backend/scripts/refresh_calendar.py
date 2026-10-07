from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
import logging
from pathlib import Path
import sys
from typing import Any

# Ensure backend root is on sys.path regardless of where script is invoked
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import get_session_factory
from app.services.calendar_ingestion import refresh_calendar_events

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("refresh_calendar")

WAT = timezone(timedelta(hours=1), name="WAT")


def format_summary(summary: dict[str, Any], utc_dt: datetime) -> str:
    wat_dt = utc_dt.astimezone(WAT)
    utc_str = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    wat_str = wat_dt.strftime("%Y-%m-%d %H:%M:%S WAT (UTC+1)")

    lines = [
        "============================================================",
        "Forward Calendar Refresh",
        f"Timestamp: {utc_str} / {wat_str}",
        "============================================================",
        "Calendar refresh completed",
        f"Providers requested: {summary.get('sources_requested', 0)}",
        f"Succeeded:           {summary.get('sources_succeeded', 0)}",
        f"Failed:              {summary.get('sources_failed', 0)}",
        f"Created:             {summary.get('events_created', 0)}",
        f"Updated:             {summary.get('events_updated', 0)}",
        f"Unchanged:           {summary.get('events_unchanged', 0)}",
        "============================================================",
    ]

    provider_results = summary.get("provider_results", [])
    failed_providers = [p for p in provider_results if p.get("status") == "failed"]
    if failed_providers:
        lines.append("Warnings / Provider Failures:")
        for fp in failed_providers:
            lines.append(f"  - [{fp.get('name')}] {fp.get('source')}: {fp.get('error')}")
        lines.append("============================================================")

    return "\n".join(lines)


def run_refresh() -> int:
    """Executes the daily calendar refresh job directly against the service layer.

    Returns:
        0 on acceptable completion (including isolated partial provider failures)
        1 on fatal job-level or database failure
    """
    now_utc = datetime.now(timezone.utc)
    try:
        session_factory = get_session_factory()
    except Exception as exc:
        logger.error("FATAL: Failed to initialize database session factory: %s", exc)
        return 1

    try:
        with session_factory() as session:
            summary = asyncio.run(refresh_calendar_events(session))
    except Exception as exc:
        logger.error("FATAL: Calendar refresh job encountered an unhandled error: %s", exc, exc_info=True)
        return 1

    output = format_summary(summary, now_utc)
    print(output)

    # Note: Isolated provider failures do not fail the overall job; stored events remain intact.
    # The job returns 0 when the service layer completes its run normally.
    return 0


def main() -> int:
    return run_refresh()


if __name__ == "__main__":
    sys.exit(main())
