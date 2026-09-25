from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MarketDataProvider(ABC):
    """Abstract base class for market data providers (e.g., OilPriceAPI, Argus, LSEG, S&P)."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @abstractmethod
    async def get_latest(self, symbols: list[str] | None = None) -> list[dict[str, Any]]:
        """Retrieves latest market observations for symbols."""
        pass

    @abstractmethod
    async def get_history(self, symbol: str, days: int = 90) -> list[dict[str, Any]]:
        """Retrieves historical market observations for a symbol over a day window."""
        pass


class AIProvider(ABC):
    """Abstract base class for AI reasoning and chatbot providers (e.g., Gemini, OpenAI)."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @abstractmethod
    async def analyse_dashboard(self, context: dict[str, Any]) -> dict[str, Any]:
        """Generates structured market risk briefing, threat scan, and management actions."""
        pass

    @abstractmethod
    async def chat(self, message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Generates conversational response to an analyst inquiry."""
        pass
