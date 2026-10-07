from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
import logging

logger = logging.getLogger(__name__)


class CalendarProvider(ABC):
    """Abstract base class for official Forward Calendar event providers."""

    name: str = "base"
    source_name: str = "Official Source"
    source_url: str = ""

    @abstractmethod
    async def get_events(self) -> list[dict[str, Any]]:
        """Retrieves normalized calendar event dictionaries from the source.

        Each dictionary must conform to CalendarEvent schema:
          - external_id: str
          - event_date: str (YYYY-MM-DD)
          - end_date: str | None (YYYY-MM-DD)
          - title: str
          - category: str (energy | central_bank | macro | election | public_holiday | bank_holiday | geopolitical)
          - region: str (Nigeria | USA | Africa | Global)
          - country: str | None
          - impact_level: str | None (low | moderate | high)
          - description: str | None
          - source_name: str
          - source_url: str
          - source_type: str ("official")
          - provider: str
        """
        pass
