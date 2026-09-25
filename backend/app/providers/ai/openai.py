from __future__ import annotations

from typing import Any
from app.providers.base import AIProvider


class OpenAIProvider(AIProvider):
    """Scaffold implementation for OpenAI provider.

    Does not make external API calls during Phase 2.
    """

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key=api_key)

    async def analyse_dashboard(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "unconfigured",
            "configured": False,
            "provider": "openai",
            "message": "OpenAI analysis provider is in scaffold mode for Phase 2.",
            "analysis": None,
        }

    async def chat(self, message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "status": "unconfigured",
            "configured": False,
            "provider": "openai",
            "message": "OpenAI chat provider is in scaffold mode for Phase 2.",
            "reply": None,
        }
