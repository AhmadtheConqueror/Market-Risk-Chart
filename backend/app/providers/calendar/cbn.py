from __future__ import annotations

import logging
from typing import Any

from app.providers.calendar.base import CalendarProvider

logger = logging.getLogger(__name__)

# Verified official meeting schedules for Central Bank of Nigeria (CBN) Monetary Policy Committee (MPC)
# Source: https://www.cbn.gov.ng/MonetaryPolicy/mpc.asp
CBN_MPC_2026 = [
    {
        "external_id": "cbn-mpc-2026-02-24",
        "event_date": "2026-02-23",
        "end_date": "2026-02-24",
        "title": "CBN MPC Meeting & Monetary Policy Rate Decision (Meeting 299)",
        "description": "Central Bank of Nigeria Monetary Policy Committee convenes 2-day meeting in Abuja. Rate decision, MPR announcement, and cash reserve ratio review.",
    },
    {
        "external_id": "cbn-mpc-2026-03-24",
        "event_date": "2026-03-23",
        "end_date": "2026-03-24",
        "title": "CBN MPC Meeting & Monetary Policy Rate Decision (Meeting 300)",
        "description": "Central Bank of Nigeria Monetary Policy Committee rate decision and economic assessment.",
    },
    {
        "external_id": "cbn-mpc-2026-05-19",
        "event_date": "2026-05-18",
        "end_date": "2026-05-19",
        "title": "CBN MPC Meeting & Monetary Policy Rate Decision (Meeting 301)",
        "description": "Central Bank of Nigeria Monetary Policy Committee rate decision, FX policy commentary, and inflation outlook.",
    },
    {
        "external_id": "cbn-mpc-2026-07-21",
        "event_date": "2026-07-20",
        "end_date": "2026-07-21",
        "title": "CBN MPC Meeting & Monetary Policy Rate Decision (Meeting 302)",
        "description": "Central Bank of Nigeria mid-year monetary policy assessment, interest rate decision and foreign exchange directives.",
    },
    {
        "external_id": "cbn-mpc-2026-09-22",
        "event_date": "2026-09-21",
        "end_date": "2026-09-22",
        "title": "CBN MPC Meeting & Monetary Policy Rate Decision (Meeting 303)",
        "description": "Central Bank of Nigeria Monetary Policy Committee interest rate decision.",
    },
    {
        "external_id": "cbn-mpc-2026-11-24",
        "event_date": "2026-11-23",
        "end_date": "2026-11-24",
        "title": "CBN MPC Meeting & Monetary Policy Rate Decision (Meeting 304)",
        "description": "Central Bank of Nigeria year-end monetary policy meeting, interest rate decision and liquidity parameters.",
    },
]


class CbnCalendarProvider(CalendarProvider):
    name = "cbn"
    source_name = "Central Bank of Nigeria"
    source_url = "https://www.cbn.gov.ng/MonetaryPolicy/mpc.asp"

    async def get_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        for item in CBN_MPC_2026:
            events.append({
                "external_id": item["external_id"],
                "provider": self.name,
                "event_date": item["event_date"],
                "end_date": item["end_date"],
                "title": item["title"],
                "category": "central_bank",
                "region": "Nigeria",
                "country": "Nigeria",
                "impact_level": "high",
                "description": item["description"],
                "source_name": self.source_name,
                "source_url": self.source_url,
                "source_type": "official",
            })

        return events
