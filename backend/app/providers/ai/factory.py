from __future__ import annotations

from app.config import get_settings
from app.providers.ai.gemini import GeminiProvider
from app.providers.ai.openai import OpenAIProvider
from app.providers.base import AIProvider


def get_ai_provider(provider_name: str | None = None) -> AIProvider:
    settings = get_settings()
    name = (provider_name or settings.ai_provider or "gemini").lower()

    if name == "openai":
        return OpenAIProvider(api_key=settings.openai_api_key)

    # Default to Gemini. Never let test runs use a developer's real key.
    return GeminiProvider(
        api_key=None if settings.environment == "test" else settings.gemini_api_key,
        model=settings.gemini_model,
        timeout_seconds=settings.ai_timeout_seconds,
    )
