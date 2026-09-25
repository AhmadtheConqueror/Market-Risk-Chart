from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class MacroObservation:
    indicator_key: str
    display_name: str
    value: Decimal
    unit: str
    reporting_period: str
    source: str
    source_url: str | None = None
    published_at: datetime | None = None
    status: str = "published"
    metadata_json: dict[str, Any] = field(default_factory=dict)
    retrieved_at: datetime = field(default_factory=utc_now)


class MacroDataProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider / source organization."""
        pass

    @abstractmethod
    async def fetch_latest(self) -> list[MacroObservation]:
        """Fetch latest verified macro observations from the official publisher."""
        pass
