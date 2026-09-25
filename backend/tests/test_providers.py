from __future__ import annotations

import pytest

from app.providers.ai.factory import get_ai_provider
from app.providers.ai.gemini import GeminiProvider
from app.providers.ai.openai import OpenAIProvider
from app.providers.market.factory import get_market_provider
from app.providers.market.oilpriceapi import OilPriceAPIProvider


@pytest.mark.anyio
async def test_oilpriceapi_provider_scaffold():
    provider = get_market_provider("oilpriceapi")
    assert isinstance(provider, OilPriceAPIProvider)
    # Empty symbols returns empty without network call
    latest = await provider.get_latest([])
    assert latest == []


@pytest.mark.anyio
async def test_gemini_provider_scaffold():
    provider = get_ai_provider("gemini")
    assert isinstance(provider, GeminiProvider)
    analysis = await provider.analyse_dashboard({})
    assert analysis["status"] == "unconfigured"
    assert analysis["configured"] is False

    chat = await provider.chat("test query")
    assert chat["status"] == "unconfigured"
    assert chat["configured"] is False


@pytest.mark.anyio
async def test_openai_provider_scaffold():
    provider = get_ai_provider("openai")
    assert isinstance(provider, OpenAIProvider)
    analysis = await provider.analyse_dashboard({})
    assert analysis["status"] == "unconfigured"
    assert analysis["configured"] is False

    chat = await provider.chat("test query")
    assert chat["status"] == "unconfigured"
    assert chat["configured"] is False
