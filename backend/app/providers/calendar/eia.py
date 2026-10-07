from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Any

from app.providers.calendar.base import CalendarProvider

logger = logging.getLogger(__name__)

# Official EIA STEO release dates 2026 (typically 2nd Tuesday of each month)
# Source: https://www.eia.gov/outlooks/steo/
EIA_STEO_2026 = [
    ("2026-01-13", "EIA Short-Term Energy Outlook (STEO) — Jan 2026"),
    ("2026-02-10", "EIA Short-Term Energy Outlook (STEO) — Feb 2026"),
    ("2026-03-10", "EIA Short-Term Energy Outlook (STEO) — Mar 2026"),
    ("2026-04-07", "EIA Short-Term Energy Outlook (STEO) — Apr 2026"),
    ("2026-05-12", "EIA Short-Term Energy Outlook (STEO) — May 2026"),
    ("2026-06-09", "EIA Short-Term Energy Outlook (STEO) — Jun 2026"),
    ("2026-07-07", "EIA Short-Term Energy Outlook (STEO) — Jul 2026"),
    ("2026-08-11", "EIA Short-Term Energy Outlook (STEO) — Aug 2026"),
    ("2026-09-09", "EIA Short-Term Energy Outlook (STEO) — Sep 2026"),
    ("2026-10-13", "EIA Short-Term Energy Outlook (STEO) — Oct 2026"),
    ("2026-11-10", "EIA Short-Term Energy Outlook (STEO) — Nov 2026"),
    ("2026-12-08", "EIA Short-Term Energy Outlook (STEO) — Dec 2026"),
]

# Holidays that delay Wednesday EIA WPSR to Thursday (e.g. MLK day, Presidents Day, Memorial Day, Juneteenth, Labor Day)
MONDAY_FEDERAL_HOLIDAYS_2026 = {
    date(2026, 1, 19),  # MLK
    date(2026, 2, 16),  # Presidents Day
    date(2026, 5, 25),  # Memorial Day
    date(2026, 6, 19),  # Juneteenth (Fri, might shift)
    date(2026, 9, 7),   # Labor Day
}


def generate_eia_wpsr_dates(start_year: int = 2026, end_year: int = 2026) -> list[date]:
    """Generates the weekly EIA crude oil inventory release dates."""
    dates: list[date] = []
    # Start at first day of year
    curr = date(start_year, 1, 1)
    # Advance to first Wednesday
    while curr.weekday() != 2:  # 2 is Wednesday
        curr += timedelta(days=1)

    end_limit = date(end_year, 12, 31)
    while curr <= end_limit:
        release_date = curr
        # If the Monday prior was a federal holiday, EIA delays release to Thursday
        monday_prior = curr - timedelta(days=2)
        if monday_prior in MONDAY_FEDERAL_HOLIDAYS_2026:
            release_date = curr + timedelta(days=1)
        dates.append(release_date)
        curr += timedelta(days=7)

    return dates


class EiaCalendarProvider(CalendarProvider):
    name = "eia"
    source_name = "U.S. Energy Information Administration"
    source_url = "https://www.eia.gov/petroleum/supply/weekly/"

    async def get_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        # 1. Weekly Petroleum Status Report (WPSR)
        for release_dt in generate_eia_wpsr_dates(2026, 2026):
            date_str = release_dt.isoformat()
            events.append({
                "external_id": f"eia-wpsr-{date_str}",
                "provider": self.name,
                "event_date": date_str,
                "end_date": date_str,
                "title": "EIA Weekly Petroleum Status Report (Crude Inventories)",
                "category": "energy",
                "region": "USA",
                "country": "United States",
                "impact_level": "high",
                "description": "Weekly U.S. commercial crude oil inventories, Cushing hub stocks, gasoline and distillate inventories, and refinery utilization rates.",
                "source_name": self.source_name,
                "source_url": self.source_url,
                "source_type": "official",
            })

        # 2. Short-Term Energy Outlook (STEO)
        for date_str, title in EIA_STEO_2026:
            events.append({
                "external_id": f"eia-steo-{date_str}",
                "provider": self.name,
                "event_date": date_str,
                "end_date": date_str,
                "title": title,
                "category": "energy",
                "region": "Global",
                "country": None,
                "impact_level": "high",
                "description": "Monthly EIA global oil supply, demand, inventory and benchmark price forecasts (WTI, Brent).",
                "source_name": self.source_name,
                "source_url": "https://www.eia.gov/outlooks/steo/",
                "source_type": "official",
            })

        return events
