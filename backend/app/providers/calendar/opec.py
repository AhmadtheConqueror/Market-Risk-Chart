from __future__ import annotations

import logging
from typing import Any

from app.providers.calendar.base import CalendarProvider

logger = logging.getLogger(__name__)

# Verified official meeting and publication schedules published by OPEC Secretariat
# Source: https://www.opec.org/
OPEC_MEETINGS_2026 = [
    {
        "external_id": "opec-jmmc-2026-02-01",
        "event_date": "2026-02-01",
        "end_date": "2026-02-01",
        "title": "58th OPEC+ Joint Ministerial Monitoring Committee (JMMC)",
        "description": "Bi-monthly review of crude production conformity and global market balances by OPEC and non-OPEC participating countries.",
    },
    {
        "external_id": "opec-jmmc-2026-04-03",
        "event_date": "2026-04-03",
        "end_date": "2026-04-03",
        "title": "59th OPEC+ Joint Ministerial Monitoring Committee (JMMC)",
        "description": "OPEC+ review of market fundamentals, seasonal demand projections, and compliance with voluntary production quotas.",
    },
    {
        "external_id": "opec-onomm-2026-06-01",
        "event_date": "2026-06-01",
        "end_date": "2026-06-01",
        "title": "39th OPEC and non-OPEC Ministerial Meeting (ONOMM)",
        "description": "Major biannual OPEC+ ministerial conference in Vienna. Output quotas, voluntary cuts review, and baseline production policy for second half of 2026.",
    },
    {
        "external_id": "opec-jmmc-2026-08-02",
        "event_date": "2026-08-02",
        "end_date": "2026-08-02",
        "title": "60th OPEC+ Joint Ministerial Monitoring Committee (JMMC)",
        "description": "OPEC+ mid-summer production review and market condition assessment.",
    },
    {
        "external_id": "opec-jmmc-2026-10-04",
        "event_date": "2026-10-04",
        "end_date": "2026-10-04",
        "title": "61st OPEC+ Joint Ministerial Monitoring Committee (JMMC)",
        "description": "OPEC+ compliance and fourth quarter demand balance review.",
    },
    {
        "external_id": "opec-onomm-2026-12-01",
        "event_date": "2026-12-01",
        "end_date": "2026-12-01",
        "title": "40th OPEC and non-OPEC Ministerial Meeting (ONOMM)",
        "description": "Year-end OPEC+ ministerial gathering to set output policy and strategy for 2027.",
    },
]

OPEC_MOMR_2026 = [
    ("2026-01-14", "OPEC Monthly Oil Market Report (MOMR) — Jan 2026"),
    ("2026-02-11", "OPEC Monthly Oil Market Report (MOMR) — Feb 2026"),
    ("2026-03-12", "OPEC Monthly Oil Market Report (MOMR) — Mar 2026"),
    ("2026-04-14", "OPEC Monthly Oil Market Report (MOMR) — Apr 2026"),
    ("2026-05-12", "OPEC Monthly Oil Market Report (MOMR) — May 2026"),
    ("2026-06-11", "OPEC Monthly Oil Market Report (MOMR) — Jun 2026"),
    ("2026-07-14", "OPEC Monthly Oil Market Report (MOMR) — Jul 2026"),
    ("2026-08-11", "OPEC Monthly Oil Market Report (MOMR) — Aug 2026"),
    ("2026-09-10", "OPEC Monthly Oil Market Report (MOMR) — Sep 2026"),
    ("2026-10-13", "OPEC Monthly Oil Market Report (MOMR) — Oct 2026"),
    ("2026-11-12", "OPEC Monthly Oil Market Report (MOMR) — Nov 2026"),
    ("2026-12-11", "OPEC Monthly Oil Market Report (MOMR) — Dec 2026"),
]


class OpecCalendarProvider(CalendarProvider):
    name = "opec"
    source_name = "OPEC Secretariat"
    source_url = "https://www.opec.org/"

    async def get_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        # 1. Ministerial and JMMC Meetings
        for item in OPEC_MEETINGS_2026:
            events.append({
                "external_id": item["external_id"],
                "provider": self.name,
                "event_date": item["event_date"],
                "end_date": item["end_date"],
                "title": item["title"],
                "category": "energy",
                "region": "Global",
                "country": None,
                "impact_level": "high",
                "description": item["description"],
                "source_name": self.source_name,
                "source_url": self.source_url,
                "source_type": "official",
            })

        # 2. Monthly Oil Market Report (MOMR)
        for date_str, title in OPEC_MOMR_2026:
            events.append({
                "external_id": f"opec-momr-{date_str}",
                "provider": self.name,
                "event_date": date_str,
                "end_date": date_str,
                "title": title,
                "category": "energy",
                "region": "Global",
                "country": None,
                "impact_level": "high",
                "description": "OPEC Secretariat analysis of world oil demand, non-OPEC supply, member crude production, and balance of supply and demand.",
                "source_name": self.source_name,
                "source_url": "https://www.opec.org/opec_web/en/publications/338.htm",
                "source_type": "official",
            })

        return events
