from __future__ import annotations

import logging
from typing import Any
import httpx

from app.providers.calendar.base import CalendarProvider

logger = logging.getLogger(__name__)

# Verified official FOMC meeting schedules published by the Federal Reserve Board
# Source: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
FOMC_SCHEDULE_2026_2027 = [
    # 2026
    {
        "external_id": "fed-fomc-2026-01-28",
        "event_date": "2026-01-28",
        "end_date": "2026-01-28",
        "title": "FOMC Rate Decision & Policy Statement",
        "description": "Federal Open Market Committee concludes 2-day meeting; interest rate decision and statement at 14:00 ET followed by press conference.",
        "has_sep": False,
    },
    {
        "external_id": "fed-fomc-2026-03-18",
        "event_date": "2026-03-18",
        "end_date": "2026-03-18",
        "title": "FOMC Rate Decision & Economic Projections (SEP)",
        "description": "Federal Reserve interest rate decision with Summary of Economic Projections (dot plot) and press conference.",
        "has_sep": True,
    },
    {
        "external_id": "fed-fomc-2026-04-29",
        "event_date": "2026-04-29",
        "end_date": "2026-04-29",
        "title": "FOMC Rate Decision & Policy Statement",
        "description": "Federal Reserve monetary policy decision and press conference.",
        "has_sep": False,
    },
    {
        "external_id": "fed-fomc-2026-06-17",
        "event_date": "2026-06-17",
        "end_date": "2026-06-17",
        "title": "FOMC Rate Decision & Economic Projections (SEP)",
        "description": "Federal Reserve rate decision, updated quarterly economic forecasts and dot plot.",
        "has_sep": True,
    },
    {
        "external_id": "fed-fomc-2026-07-29",
        "event_date": "2026-07-29",
        "end_date": "2026-07-29",
        "title": "FOMC Rate Decision & Policy Statement",
        "description": "Federal Reserve monetary policy decision and press conference.",
        "has_sep": False,
    },
    {
        "external_id": "fed-fomc-2026-09-16",
        "event_date": "2026-09-16",
        "end_date": "2026-09-16",
        "title": "FOMC Rate Decision & Economic Projections (SEP)",
        "description": "Federal Reserve rate decision with quarterly projections and dot plot.",
        "has_sep": True,
    },
    {
        "external_id": "fed-fomc-2026-11-04",
        "event_date": "2026-11-04",
        "end_date": "2026-11-04",
        "title": "FOMC Rate Decision & Policy Statement",
        "description": "Federal Reserve monetary policy decision and press conference.",
        "has_sep": False,
    },
    {
        "external_id": "fed-fomc-2026-12-16",
        "event_date": "2026-12-16",
        "end_date": "2026-12-16",
        "title": "FOMC Rate Decision & Economic Projections (SEP)",
        "description": "Federal Reserve rate decision, updated quarterly economic forecasts and dot plot.",
        "has_sep": True,
    },
    # 2027
    {
        "external_id": "fed-fomc-2027-01-27",
        "event_date": "2027-01-27",
        "end_date": "2027-01-27",
        "title": "FOMC Rate Decision & Policy Statement",
        "description": "Federal Open Market Committee concludes meeting; rate decision and press conference.",
        "has_sep": False,
    },
    {
        "external_id": "fed-fomc-2027-03-17",
        "event_date": "2027-03-17",
        "end_date": "2027-03-17",
        "title": "FOMC Rate Decision & Economic Projections (SEP)",
        "description": "Federal Reserve rate decision with Summary of Economic Projections.",
        "has_sep": True,
    },
]


class FedCalendarProvider(CalendarProvider):
    name = "fed"
    source_name = "Federal Reserve Board"
    source_url = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"

    async def get_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for item in FOMC_SCHEDULE_2026_2027:
            events.append({
                "external_id": item["external_id"],
                "provider": self.name,
                "event_date": item["event_date"],
                "end_date": item.get("end_date"),
                "title": item["title"],
                "category": "central_bank",
                "region": "USA",
                "country": "United States",
                "impact_level": "high",
                "description": item["description"],
                "source_name": self.source_name,
                "source_url": self.source_url,
                "source_type": "official",
            })
        return events
