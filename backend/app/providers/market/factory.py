from __future__ import annotations

from app.config import get_settings
from app.providers.base import MarketDataProvider
from app.providers.market.oilpriceapi import OilPriceAPIProvider


def get_market_provider(provider_name: str | None = None) -> MarketDataProvider:
    settings = get_settings()
    name = (provider_name or settings.market_data_provider or "oilpriceapi").lower()

    if name == "oilpriceapi":
        return OilPriceAPIProvider(
            api_key=settings.oilpriceapi_key or settings.market_data_api_key,
            base_url=settings.market_data_base_url,
        )

    # Fallback default provider
    return OilPriceAPIProvider(
        api_key=settings.oilpriceapi_key or settings.market_data_api_key,
        base_url=settings.market_data_base_url,
    )
