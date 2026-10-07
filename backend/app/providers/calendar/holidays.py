from __future__ import annotations

import logging
from typing import Any

from app.providers.calendar.base import CalendarProvider

logger = logging.getLogger(__name__)

# Official U.S. Federal Bank & Market Holidays 2026
# Source: Federal Reserve Board / SIFMA market holiday schedule
US_HOLIDAYS_2026 = [
    ("2026-01-01", "New Year's Day (U.S. Bank Holiday)", "U.S. banks and financial markets closed."),
    ("2026-01-19", "Martin Luther King Jr. Day (U.S. Bank Holiday)", "U.S. banks and financial markets closed; delayed EIA inventory release."),
    ("2026-02-16", "Presidents' Day / Washington's Birthday (U.S. Bank Holiday)", "U.S. financial markets closed; delayed EIA inventory release."),
    ("2026-05-25", "Memorial Day (U.S. Bank Holiday)", "U.S. financial markets and banks closed; delayed EIA inventory release."),
    ("2026-06-19", "Juneteenth National Independence Day (U.S. Bank Holiday)", "U.S. federal holiday; banks and equity/bond markets closed."),
    ("2026-07-03", "Independence Day (Observed) (U.S. Bank Holiday)", "U.S. financial markets closed in observance of July 4."),
    ("2026-09-07", "Labor Day (U.S. Bank Holiday)", "U.S. financial markets closed; delayed EIA inventory release."),
    ("2026-10-12", "Columbus Day / Indigenous Peoples' Day (U.S. Bank Holiday)", "U.S. bond markets and banks closed; stock exchanges open."),
    ("2026-11-11", "Veterans Day (U.S. Bank Holiday)", "U.S. bond markets and banks closed."),
    ("2026-11-26", "Thanksgiving Day (U.S. Bank Holiday)", "U.S. financial markets closed."),
    ("2026-12-25", "Christmas Day (U.S. Bank Holiday)", "U.S. financial markets closed."),
]

# Official Nigerian Public Holidays 2026
# Source: Federal Ministry of Interior / Central Bank of Nigeria
NIGERIA_HOLIDAYS_2026 = [
    ("2026-01-01", "New Year's Day (Nigeria Public Holiday)", "Public holiday across Nigeria; commercial banks and government agencies closed."),
    ("2026-03-20", "Eid al-Fitr (Nigeria Public Holiday)", "Islamic celebration marking the end of Ramadan; public holiday."),
    ("2026-03-21", "Eid al-Fitr Holiday (Day 2) (Nigeria Public Holiday)", "Public holiday across Nigeria."),
    ("2026-04-03", "Good Friday (Nigeria Public Holiday)", "Christian religious holiday; commercial banks and markets closed."),
    ("2026-04-06", "Easter Monday (Nigeria Public Holiday)", "Public holiday across Nigeria."),
    ("2026-05-01", "Workers' Day / May Day (Nigeria Public Holiday)", "National holiday celebrating labor and workforce."),
    ("2026-05-27", "Eid al-Adha (Nigeria Public Holiday)", "Feast of the Sacrifice; public holiday across Nigeria."),
    ("2026-05-28", "Eid al-Adha Holiday (Day 2) (Nigeria Public Holiday)", "Public holiday across Nigeria."),
    ("2026-06-12", "Democracy Day (Nigeria Public Holiday)", "National public holiday commemorating Nigeria's democratic transition."),
    ("2026-08-26", "Mawlid / Eid al-Mawlid (Nigeria Public Holiday)", "Celebration of the Prophet's birthday; public holiday."),
    ("2026-10-01", "Independence Day (Nigeria National Holiday)", "Nigeria National Day celebrating sovereignty; public holiday."),
    ("2026-12-25", "Christmas Day (Nigeria Public Holiday)", "Public holiday across Nigeria."),
    ("2026-12-26", "Boxing Day (Nigeria Public Holiday)", "Public holiday across Nigeria."),
]


class HolidaysCalendarProvider(CalendarProvider):
    name = "holidays"
    source_name = "Official Holiday Schedules"
    source_url = "https://www.federalreserve.gov/aboutthefed/k8.htm"

    async def get_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        # 1. US Bank & Market Holidays
        for date_str, title, desc in US_HOLIDAYS_2026:
            events.append({
                "external_id": f"us-holiday-{date_str}",
                "provider": self.name,
                "event_date": date_str,
                "end_date": date_str,
                "title": title,
                "category": "bank_holiday",
                "region": "USA",
                "country": "United States",
                "impact_level": "low",
                "description": desc,
                "source_name": "Federal Reserve Board",
                "source_url": "https://www.federalreserve.gov/aboutthefed/k8.htm",
                "source_type": "official",
            })

        # 2. Nigerian Public Holidays
        for date_str, title, desc in NIGERIA_HOLIDAYS_2026:
            events.append({
                "external_id": f"ng-holiday-{date_str}",
                "provider": self.name,
                "event_date": date_str,
                "end_date": date_str,
                "title": title,
                "category": "public_holiday",
                "region": "Nigeria",
                "country": "Nigeria",
                "impact_level": "low",
                "description": desc,
                "source_name": "Federal Ministry of Interior",
                "source_url": "https://interior.gov.ng/",
                "source_type": "official",
            })

        return events
