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


class RiskAdvisorView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    key_risks: list[str]
    watch_items: list[str]


class TraderDeskPulse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    market_signals: list[str]


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
    trader_desk_pulse: TraderDeskPulse
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


class AILatestResponse(BaseModel):
    status: str = "unavailable"
    configured: bool = False
    provider: str | None = None
    model: str | None = None
    generated_at: str | None = None
    message: str = "No completed AI analysis is available."
    analysis: AIAnalysisOutput | None = None


class AIChatRequest(BaseModel):
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class AIChatResponse(BaseModel):
    status: str = "unconfigured"
    configured: bool = False
    provider: str | None = None
    message: str = "AI chat service is in scaffold mode and has not been configured to make external API calls."
    reply: str | None = None
