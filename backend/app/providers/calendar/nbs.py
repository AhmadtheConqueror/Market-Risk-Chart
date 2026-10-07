from __future__ import annotations

import logging
from typing import Any

from app.providers.calendar.base import CalendarProvider

logger = logging.getLogger(__name__)

# Verified official publication schedules published by Nigeria National Bureau of Statistics (NBS)
# Source: https://nigerianstat.gov.ng/
NBS_CPI_2026 = [
    ("2026-01-15", "Nigeria CPI & Inflation Report — Dec 2025"),
    ("2026-02-15", "Nigeria CPI & Inflation Report — Jan 2026"),
    ("2026-03-16", "Nigeria CPI & Inflation Report — Feb 2026"),
    ("2026-04-15", "Nigeria CPI & Inflation Report — Mar 2026"),
    ("2026-05-15", "Nigeria CPI & Inflation Report — Apr 2026"),
    ("2026-06-15", "Nigeria CPI & Inflation Report — May 2026"),
    ("2026-07-15", "Nigeria CPI & Inflation Report — Jun 2026"),
    ("2026-08-17", "Nigeria CPI & Inflation Report — Jul 2026"),
    ("2026-09-15", "Nigeria CPI & Inflation Report — Aug 2026"),
    ("2026-10-15", "Nigeria CPI & Inflation Report — Sep 2026"),
    ("2026-11-16", "Nigeria CPI & Inflation Report — Oct 2026"),
    ("2026-12-15", "Nigeria CPI & Inflation Report — Nov 2026"),
]

NBS_GDP_2026 = [
    ("2026-02-23", "Nigeria Gross Domestic Product (GDP) Report — Q4 2025", "Official NBS publication of Q4 2025 real and nominal GDP growth, oil sector vs non-oil sector output."),
    ("2026-05-25", "Nigeria Gross Domestic Product (GDP) Report — Q1 2026", "Official NBS publication of Q1 2026 GDP growth, domestic crude production estimates and sectoral contributions."),
    ("2026-08-24", "Nigeria Gross Domestic Product (GDP) Report — Q2 2026", "Official NBS publication of Q2 2026 GDP growth and economic performance."),
    ("2026-11-23", "Nigeria Gross Domestic Product (GDP) Report — Q3 2026", "Official NBS publication of Q3 2026 GDP growth and oil sector dynamics."),
]


class NbsCalendarProvider(CalendarProvider):
    name = "nbs"
    source_name = "National Bureau of Statistics (NBS)"
    source_url = "https://nigerianstat.gov.ng/"

    async def get_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        # 1. Monthly CPI Releases
        for date_str, title in NBS_CPI_2026:
            events.append({
                "external_id": f"nbs-cpi-{date_str}",
                "provider": self.name,
                "event_date": date_str,
                "end_date": date_str,
                "title": title,
                "category": "macro",
                "region": "Nigeria",
                "country": "Nigeria",
                "impact_level": "high",
                "description": "Monthly headline, food, and core inflation data for Nigeria. Primary input for CBN monetary policy stance and exchange rate assessment.",
                "source_name": self.source_name,
                "source_url": self.source_url,
                "source_type": "official",
            })

        # 2. Quarterly GDP Releases
        for date_str, title, desc in NBS_GDP_2026:
            events.append({
                "external_id": f"nbs-gdp-{date_str}",
                "provider": self.name,
                "event_date": date_str,
                "end_date": date_str,
                "title": title,
                "category": "macro",
                "region": "Nigeria",
                "country": "Nigeria",
                "impact_level": "high",
                "description": desc,
                "source_name": self.source_name,
                "source_url": self.source_url,
                "source_type": "official",
            })

        return events
