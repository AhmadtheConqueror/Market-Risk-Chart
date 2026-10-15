from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


Priority = Literal["low", "medium", "high"]
OverallPositionStatus = Literal["stable", "watch", "elevated", "high"]


class DailyBriefing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str
    summary: str
    key_points: list[str]


class PulseInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1, max_length=600)
    synthesis_card_ids: list[int] = Field(min_length=1, max_length=8)
    relationship: Literal["support", "context", "offset", "uncertainty", "background"]


class PulseInterpretationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interpretations: list[PulseInterpretation] = Field(max_length=4)


class RiskAdvisorView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    key_risks: list[str]
    watch_items: list[str]
    pulse_interpretations: list[PulseInterpretation] = Field(default_factory=list, max_length=4)


class PatternAndInference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    observations: list[str]


class ManagementAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    rationale: str
    priority: Priority


class ManagementActions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: list[ManagementAction]


class OverallPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OverallPositionStatus
    summary: str


class AIAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_briefing: DailyBriefing
    risk_advisor_view: RiskAdvisorView
    pattern_and_inference: PatternAndInference
    management_actions: ManagementActions
    overall_position: OverallPosition
    data_quality_notes: list[str]


class AIAnalyseRequest(BaseModel):
    force_refresh: bool = False
    # Kept for backwards compatibility. The API ignores browser context when
    # building the authoritative server-side analysis input.
    context: dict[str, Any] = Field(default_factory=dict)


class AIAnalyseResponse(BaseModel):
    status: str = "unconfigured"
    configured: bool = False
    provider: str | None = None
    model: str | None = None
    generated_at: str | None = None
    message: str = "AI service is in scaffold mode and has not been configured to make external API calls."
    analysis: AIAnalysisOutput | None = None
    pulse_provenance: dict[str, Any] | None = None


class AILatestResponse(BaseModel):
    status: str = "unavailable"
    configured: bool = False
    provider: str | None = None
    model: str | None = None
    generated_at: str | None = None
    message: str = "No completed AI analysis is available."
    analysis: AIAnalysisOutput | None = None
    pulse_provenance: dict[str, Any] | None = None


class AIChatRequest(BaseModel):
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class AIChatResponse(BaseModel):
    status: str = "unconfigured"
    configured: bool = False
    provider: str | None = None
    message: str = "AI chat service is in scaffold mode and has not been configured to make external API calls."
    reply: str | None = None


def saved_analysis_payload(output: dict[str, Any]) -> dict[str, Any]:
    """Read older saved interpretations without reviving the retired output block.

    Leave stored JSON untouched and retain every other section. New provider
    output still validates against the strict current AIAnalysisOutput schema.
    """
    return {key: value for key, value in output.items() if key != "trader_desk_pulse"}
