from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from app.config import get_settings
from app.providers.base import AIProvider
from app.schemas.ai import AIAnalysisOutput
from app.services.ai_prompt_service import AI_SYSTEM_INSTRUCTION, build_analysis_prompt

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """Google Gemini provider using the official ``google-genai`` SDK."""

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout_seconds: float | None = None) -> None:
        super().__init__(api_key=api_key)
        settings = get_settings()
        self.model = model or settings.gemini_model
        self.timeout_seconds = timeout_seconds or settings.ai_timeout_seconds

    async def analyse_dashboard(self, context: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured:
            return self._unconfigured_result()

        try:
            from google import genai
            from google.genai import types
        except ImportError:
            return self._error_result("Gemini SDK is not installed; analysis is unavailable.")

        try:
            client = genai.Client(api_key=self.api_key)
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=self.model,
                    contents=build_analysis_prompt(context),
                    config=types.GenerateContentConfig(
                        system_instruction=AI_SYSTEM_INSTRUCTION,
                        response_mime_type="application/json",
                        response_schema=_gemini_response_schema(),
                        temperature=0.2,
                    ),
                ),
                timeout=self.timeout_seconds,
            )
            raw_text = getattr(response, "text", None)
            if not raw_text:
                raise ValueError("Gemini returned an empty response.")
            parsed = AIAnalysisOutput.model_validate(json.loads(raw_text))
            return {
                "status": "completed",
                "configured": True,
                "provider": "gemini",
                "model": self.model,
                "message": "AI analysis completed.",
                "analysis": parsed.model_dump(mode="json"),
            }
        except asyncio.TimeoutError:
            return self._error_result("Gemini analysis timed out.")
        except Exception as exc:  # Provider errors must not expose secrets.
            status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            logger.warning(
                "Gemini dashboard analysis failed: exception_type=%s provider_status=%s message=%s",
                type(exc).__name__,
                status_code or "unknown",
                self._sanitized_error_message(exc),
            )
            return self._error_result(self._safe_error_message(exc))

    async def chat(self, message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "status": "unconfigured",
            "configured": False,
            "provider": "gemini",
            "message": "Gemini AI chat is intentionally unavailable until the chatbot phase.",
            "reply": None,
        }

    def _unconfigured_result(self) -> dict[str, Any]:
        return {
            "status": "unconfigured",
            "configured": False,
            "provider": "gemini",
            "model": self.model,
            "message": "Gemini AI provider is not configured; analysis remains in scaffold mode.",
            "analysis": None,
        }

    def _error_result(self, message: str) -> dict[str, Any]:
        return {
            "status": "error",
            "configured": True,
            "provider": "gemini",
            "model": self.model,
            "message": message,
            "analysis": None,
        }

    @staticmethod
    def _safe_error_message(exc: Exception) -> str:
        status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        if status_code in (401, 403):
            return "Gemini authentication or permission was rejected."
        if status_code == 429:
            return "Gemini rate limit reached; please try again later."
        try:
            if status_code and int(status_code) >= 500:
                return "Gemini service is temporarily unavailable."
        except (TypeError, ValueError):
            pass
        if isinstance(exc, (json.JSONDecodeError, ValueError)):
            return "Gemini returned malformed or incomplete structured output."
        return "Gemini analysis is temporarily unavailable."

    @staticmethod
    def _sanitized_error_message(exc: Exception) -> str:
        """Keep useful provider diagnostics while excluding keys and credentials."""
        message = str(exc).strip() or "No provider message."
        message = re.sub(r"AIza[0-9A-Za-z_-]{20,}", "[redacted-key]", message)
        message = re.sub(
            r"(?i)(api[-_ ]?key|authorization|bearer)(\s*[:=]\s*|\s+)[^,;\s]+",
            r"\1=[redacted]",
            message,
        )
        return message[:400]


def _gemini_response_schema() -> dict[str, Any]:
    """Return a Gemini-compatible inline schema while Pydantic remains authoritative."""
    document = AIAnalysisOutput.model_json_schema()
    definitions = document.get("$defs", {})
    allowed_keys = {"type", "enum", "items", "properties", "required", "description", "format", "nullable"}

    def expand(node: dict[str, Any]) -> dict[str, Any]:
        if "$ref" in node:
            reference = node["$ref"].rsplit("/", 1)[-1]
            return expand(definitions[reference])

        result: dict[str, Any] = {}
        for key, value in node.items():
            if key not in allowed_keys:
                continue
            if key == "properties":
                result[key] = {name: expand(child) for name, child in value.items()}
            elif key == "items":
                result[key] = expand(value)
            else:
                result[key] = value
        return result

    return expand(document)
