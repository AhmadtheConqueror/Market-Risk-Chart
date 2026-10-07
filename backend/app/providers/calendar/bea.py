from __future__ import annotations

import logging
from typing import Any

from app.providers.calendar.base import CalendarProvider

logger = logging.getLogger(__name__)

# Verified official release schedules published by the U.S. Bureau of Economic Analysis (BEA)
# Source: https://www.bea.gov/news/schedule
BEA_GDP_2026 = [
    ("2026-01-29", "U.S. GDP (Advance Estimate) — Q4 2025", "First estimate of Q4 2025 gross domestic product annualized growth."),
    ("2026-02-26", "U.S. GDP (Second Estimate) — Q4 2025", "Revised estimate of Q4 2025 gross domestic product with updated source data."),
    ("2026-03-26", "U.S. GDP (Third Estimate) — Q4 2025", "Final release of Q4 2025 gross domestic product."),
    ("2026-04-30", "U.S. GDP (Advance Estimate) — Q1 2026", "First estimate of Q1 2026 gross domestic product annualized growth."),
    ("2026-05-28", "U.S. GDP (Second Estimate) — Q1 2026", "Revised estimate of Q1 2026 gross domestic product."),
    ("2026-06-25", "U.S. GDP (Third Estimate) — Q1 2026", "Final release of Q1 2026 gross domestic product."),
    ("2026-07-30", "U.S. GDP (Advance Estimate) — Q2 2026", "First estimate of Q2 2026 gross domestic product annualized growth."),
    ("2026-08-27", "U.S. GDP (Second Estimate) — Q2 2026", "Revised estimate of Q2 2026 gross domestic product."),
    ("2026-09-24", "U.S. GDP (Third Estimate) — Q2 2026", "Final release of Q2 2026 gross domestic product."),
    ("2026-10-29", "U.S. GDP (Advance Estimate) — Q3 2026", "First estimate of Q3 2026 gross domestic product annualized growth."),
    ("2026-11-25", "U.S. GDP (Second Estimate) — Q3 2026", "Revised estimate of Q3 2026 gross domestic product."),
    ("2026-12-23", "U.S. GDP (Third Estimate) — Q3 2026", "Final release of Q3 2026 gross domestic product."),
]


class BeaCalendarProvider(CalendarProvider):
    name = "bea"
    source_name = "U.S. Bureau of Economic Analysis"
    source_url = "https://www.bea.gov/news/schedule"

    async def get_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        for date_str, title, desc in BEA_GDP_2026:
            events.append({
                "external_id": f"bea-gdp-{date_str}",
                "provider": self.name,
                "event_date": date_str,
                "end_date": date_str,
                "title": title,
                "category": "macro",
                "region": "USA",
                "country": "United States",
                "impact_level": "high",
                "description": desc,
                "source_name": self.source_name,
                "source_url": self.source_url,
                "source_type": "official",
            })

        return events
