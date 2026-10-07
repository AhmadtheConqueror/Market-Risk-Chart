from __future__ import annotations

import logging
from typing import Any

from app.providers.calendar.base import CalendarProvider

logger = logging.getLogger(__name__)

# Verified official release schedules published by the U.S. Bureau of Labor Statistics (BLS)
# Source: https://www.bls.gov/schedule/news_release/
BLS_CPI_2026 = [
    ("2026-01-14", "U.S. Consumer Price Index (CPI) — Dec 2025"),
    ("2026-02-11", "U.S. Consumer Price Index (CPI) — Jan 2026"),
    ("2026-03-11", "U.S. Consumer Price Index (CPI) — Feb 2026"),
    ("2026-04-10", "U.S. Consumer Price Index (CPI) — Mar 2026"),
    ("2026-05-12", "U.S. Consumer Price Index (CPI) — Apr 2026"),
    ("2026-06-10", "U.S. Consumer Price Index (CPI) — May 2026"),
    ("2026-07-14", "U.S. Consumer Price Index (CPI) — Jun 2026"),
    ("2026-08-12", "U.S. Consumer Price Index (CPI) — Jul 2026"),
    ("2026-09-11", "U.S. Consumer Price Index (CPI) — Aug 2026"),
    ("2026-10-14", "U.S. Consumer Price Index (CPI) — Sep 2026"),
    ("2026-11-12", "U.S. Consumer Price Index (CPI) — Oct 2026"),
    ("2026-12-10", "U.S. Consumer Price Index (CPI) — Nov 2026"),
]

BLS_NFP_2026 = [
    ("2026-01-09", "U.S. Employment Situation (Non-Farm Payrolls) — Dec 2025"),
    ("2026-02-06", "U.S. Employment Situation (Non-Farm Payrolls) — Jan 2026"),
    ("2026-03-06", "U.S. Employment Situation (Non-Farm Payrolls) — Feb 2026"),
    ("2026-04-03", "U.S. Employment Situation (Non-Farm Payrolls) — Mar 2026"),
    ("2026-05-08", "U.S. Employment Situation (Non-Farm Payrolls) — Apr 2026"),
    ("2026-06-05", "U.S. Employment Situation (Non-Farm Payrolls) — May 2026"),
    ("2026-07-02", "U.S. Employment Situation (Non-Farm Payrolls) — Jun 2026"),
    ("2026-08-07", "U.S. Employment Situation (Non-Farm Payrolls) — Jul 2026"),
    ("2026-09-04", "U.S. Employment Situation (Non-Farm Payrolls) — Aug 2026"),
    ("2026-10-02", "U.S. Employment Situation (Non-Farm Payrolls) — Sep 2026"),
    ("2026-11-06", "U.S. Employment Situation (Non-Farm Payrolls) — Oct 2026"),
    ("2026-12-04", "U.S. Employment Situation (Non-Farm Payrolls) — Nov 2026"),
]


class BlsCalendarProvider(CalendarProvider):
    name = "bls"
    source_name = "U.S. Bureau of Labor Statistics"
    source_url = "https://www.bls.gov/schedule/news_release/"

    async def get_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        for date_str, title in BLS_CPI_2026:
            events.append({
                "external_id": f"bls-cpi-{date_str}",
                "provider": self.name,
                "event_date": date_str,
                "end_date": date_str,
                "title": title,
                "category": "macro",
                "region": "USA",
                "country": "United States",
                "impact_level": "high",
                "description": "Monthly headline and core inflation statistics. Major market mover for interest rate expectations and USD valuation.",
                "source_name": self.source_name,
                "source_url": self.source_url,
                "source_type": "official",
            })

        for date_str, title in BLS_NFP_2026:
            events.append({
                "external_id": f"bls-nfp-{date_str}",
                "provider": self.name,
                "event_date": date_str,
                "end_date": date_str,
                "title": title,
                "category": "macro",
                "region": "USA",
                "country": "United States",
                "impact_level": "high",
                "description": "U.S. monthly job growth, unemployment rate, and average hourly earnings. Key indicator of labor market tightness and economic trajectory.",
                "source_name": self.source_name,
                "source_url": self.source_url,
                "source_type": "official",
            })

        return events
