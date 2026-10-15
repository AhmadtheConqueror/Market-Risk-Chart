from __future__ import annotations

import sys
import types
import asyncio
from datetime import date

import pytest

from app.providers.ai.gemini import GeminiProvider
from app.schemas.ai import AIAnalysisOutput
from app.services.ai_context import build_dashboard_ai_context


@pytest.fixture
def anyio_backend():
    # GeminiProvider and its SDK operate on asyncio, matching the ASGI runtime.
    return "asyncio"


VALID_ANALYSIS = {
    "daily_briefing": {
        "headline": "Market conditions require monitoring.",
        "summary": "The verified snapshot shows mixed signals.",
        "key_points": ["Brent is available from the approved provider."],
    },
    "risk_advisor_view": {
        "summary": "Watch volatility and data freshness.",
        "key_risks": ["History may be insufficient."],
        "watch_items": ["Confirm the next provider refresh."],
    },
    "pattern_and_inference": {
        "summary": "Recent observations do not establish a persistent pattern.",
        "observations": ["Do not infer missing observations."],
    },
    "management_actions": {
        "actions": [
            {
                "action": "Review exposure limits",
                "rationale": "Keep limits aligned with current volatility.",
                "priority": "medium",
            }
        ]
    },
    "overall_position": {
        "status": "watch",
        "summary": "Maintain a watch posture pending more history.",
    },
    "data_quality_notes": ["Some instruments have insufficient history."],
}


def install_fake_gemini(monkeypatch, response_text: str):
    captured: dict = {}

    class GenerateContentConfig:
        def __init__(self, **kwargs):
            captured["config"] = kwargs

    class FakeModels:
        async def generate_content(self, **kwargs):
            captured["request"] = kwargs
            return types.SimpleNamespace(text=response_text)

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.aio = types.SimpleNamespace(models=FakeModels())

    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.genai")
    genai_module.Client = FakeClient
    types_module = types.ModuleType("google.genai.types")
    types_module.GenerateContentConfig = GenerateContentConfig
    google_module.genai = genai_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_module)
    return captured


@pytest.mark.anyio
async def test_gemini_provider_validates_structured_output_and_keeps_key_out_of_prompt(monkeypatch):
    captured = install_fake_gemini(monkeypatch, __import__("json").dumps(VALID_ANALYSIS))
    provider = GeminiProvider(api_key="test-secret", model="test-model", timeout_seconds=2)

    result = await provider.analyse_dashboard({"provider_symbol": "BRENT_CRUDE_USD", "value": 80.0})

    assert result["status"] == "completed"
    assert AIAnalysisOutput.model_validate(result["analysis"])
    assert captured["client"]["api_key"] == "test-secret"
    assert "test-secret" not in captured["request"]["contents"]
    assert captured["request"]["model"] == "test-model"
    assert captured["config"]["response_mime_type"] == "application/json"
    schema_text = __import__("json").dumps(captured["config"]["response_schema"])
    assert "additionalProperties" not in schema_text
    assert '"$ref"' not in schema_text
    assert '"$defs"' not in schema_text


@pytest.mark.anyio
async def test_gemini_provider_rejects_malformed_or_missing_sections(monkeypatch):
    install_fake_gemini(monkeypatch, "{}")
    provider = GeminiProvider(api_key="test-secret", timeout_seconds=2)

    result = await provider.analyse_dashboard({})

    assert result["status"] == "error"
    assert result["analysis"] is None
    assert "structured output" in result["message"]


@pytest.mark.anyio
async def test_gemini_provider_timeout_is_bounded(monkeypatch):
    class SlowModels:
        async def generate_content(self, **kwargs):
            await asyncio.sleep(0.05)

    class SlowClient:
        def __init__(self, **kwargs):
            self.aio = types.SimpleNamespace(models=SlowModels())

    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.genai")
    genai_module.Client = SlowClient
    types_module = types.ModuleType("google.genai.types")
    types_module.GenerateContentConfig = lambda **kwargs: kwargs
    google_module.genai = genai_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_module)

    result = await GeminiProvider(api_key="test-secret", timeout_seconds=0.001).analyse_dashboard({})

    assert result["status"] == "error"
    assert "timed out" in result["message"]


def test_gemini_provider_classifies_provider_status_errors():
    for code, expected in (
        (401, "authentication"),
        (403, "permission"),
        (429, "rate limit"),
        (500, "temporarily unavailable"),
    ):
        error = types.SimpleNamespace(status_code=code)
        assert expected in GeminiProvider._safe_error_message(error).lower()


def test_ai_context_is_server_built_and_contains_history(seed_test_data, db_session):
    context = build_dashboard_ai_context(db_session)

    brent = next(item for item in context["market_stats"] if item["instrument_id"] == "brent")
    assert brent["provider_symbol"] == "TEST_BRENT"
    assert brent["history_30d"]
    assert brent["history_30d"][0]["assessment_date"] == date(2026, 8, 26).isoformat()
    assert context["analysis_rules"]["market_values_are_backend_authoritative"] is True
    assert "api_key" not in str(context).lower()


def test_ai_endpoint_persists_success_and_latest(client, seed_test_data, db_session, monkeypatch):
    class FakeProvider:
        async def analyse_dashboard(self, context):
            assert context["market_stats"]
            assert "browser" not in str(context).lower()
            return {
                "status": "completed",
                "configured": True,
                "provider": "gemini",
                "model": "test-model",
                "message": "AI analysis completed.",
                "analysis": VALID_ANALYSIS,
            }

    monkeypatch.setattr("app.api.ai.get_ai_provider", lambda: FakeProvider())
    response = client.post("/api/ai/analyse", json={"force_refresh": True, "context": {"value": 999999}})

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["analysis"]["overall_position"]["status"] == "watch"

    latest = client.get("/api/ai/latest")
    assert latest.status_code == 200
    assert latest.json()["status"] == "completed"
    assert latest.json()["analysis"]["daily_briefing"]["headline"] == VALID_ANALYSIS["daily_briefing"]["headline"]


def test_current_ai_contract_drops_retired_output_but_keeps_strict_validation():
    from pydantic import ValidationError
    assert "trader_desk_pulse" not in AIAnalysisOutput.model_json_schema()["properties"]
    assert "risk_advisor_view" in AIAnalysisOutput.model_fields
    with pytest.raises(ValidationError):
        AIAnalysisOutput.model_validate({**VALID_ANALYSIS,"trader_desk_pulse":{"summary":"Retired"}})


def test_saved_payload_projection_preserves_all_other_sections_and_original_record():
    from copy import deepcopy
    from app.schemas.ai import saved_analysis_payload
    original={**deepcopy(VALID_ANALYSIS),"trader_desk_pulse":{"summary":"Retired synthetic interpretation"}}
    cleaned=saved_analysis_payload(original)
    assert cleaned==VALID_ANALYSIS
    assert "trader_desk_pulse" in original


def test_old_saved_analysis_remains_available_without_retired_api_fields(client,db_session,seed_test_data):
    from app.models.ai import AIAnalysis
    original={**VALID_ANALYSIS,"trader_desk_pulse":{"summary":"Retired synthetic interpretation","market_signals":[]}}
    record=AIAnalysis(analysis_type="daily_dashboard_analysis",provider="gemini",model="synthetic",status="completed",input_context_json={},output_json=original)
    db_session.add(record);db_session.commit()
    latest=client.get("/api/ai/latest")
    assert latest.status_code==200 and latest.json()["status"]=="completed"
    assert latest.json()["analysis"]==VALID_ANALYSIS
    snapshot=client.get("/api/dashboard/snapshot")
    assert snapshot.status_code==200 and snapshot.json()["ai_analysis"]==VALID_ANALYSIS
    db_session.refresh(record)
    assert "trader_desk_pulse" in record.output_json


def test_verified_context_keeps_source_data_and_does_not_add_report_integration(db_session,seed_test_data):
    context=build_dashboard_ai_context(db_session)
    assert context["market_stats"] and "news" in context and "macro" in context
    assert "risk_register" in context and "upcoming_calendar_events" in context
    assert "traderDesk" not in context and "trader_desk_pulse" not in context
    assert "intelligence_findings" not in context and "intelligence_syntheses" not in context
