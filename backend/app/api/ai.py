from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.models.ai import AIAnalysis, MarketSnapshot
from app.providers.ai.factory import get_ai_provider
from app.schemas.ai import AIAnalysisOutput
from app.schemas.ai import (
    AILatestResponse,
    AIAnalyseRequest,
    AIAnalyseResponse,
    AIChatRequest,
    AIChatResponse,
)
from app.services.ai_context import build_dashboard_ai_context

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/analyse", response_model=AIAnalyseResponse)
async def analyse_dashboard(
    request: AIAnalyseRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AIAnalyseResponse:
    settings = get_settings()
    provider = get_ai_provider()
    context = build_dashboard_ai_context(db)
    result = await provider.analyse_dashboard(context)
    analysis = None
    if result.get("analysis") is not None:
        try:
            analysis = AIAnalysisOutput.model_validate(result["analysis"])
        except Exception:
            result = {
                **result,
                "status": "error",
                "message": "AI provider returned output that failed schema validation.",
                "analysis": None,
            }

    _persist_analysis(
        db=db,
        context=context,
        result=result,
        analysis=analysis,
        snapshot_date=context.get("snapshot_date"),
    )

    return AIAnalyseResponse(
        status=result.get("status", "unconfigured"),
        configured=result.get("configured", False),
        provider=result.get("provider", settings.ai_provider),
        model=result.get("model"),
        generated_at=datetime.now(timezone.utc).isoformat(),
        message=result.get(
            "message",
            "AI analysis is unavailable.",
        ),
        analysis=analysis,
    )


@router.get("/latest", response_model=AILatestResponse)
def latest_analysis(db: Annotated[Session, Depends(get_db)]) -> AILatestResponse:
    settings = get_settings()
    statement = (
        select(AIAnalysis)
        .where(
            AIAnalysis.analysis_type == "daily_dashboard_analysis",
            AIAnalysis.status == "completed",
            AIAnalysis.output_json.is_not(None),
        )
        .order_by(desc(AIAnalysis.generated_at), desc(AIAnalysis.id))
        .limit(1)
    )
    record = db.scalars(statement).first()
    if not record or not record.output_json:
        return AILatestResponse(
            status="unavailable",
            configured=bool(settings.gemini_api_key) if settings.ai_provider == "gemini" else bool(settings.openai_api_key),
            provider=settings.ai_provider,
            model=settings.gemini_model if settings.ai_provider == "gemini" else None,
            message="No completed AI analysis is available.",
        )

    try:
        analysis = AIAnalysisOutput.model_validate(record.output_json)
    except Exception:
        return AILatestResponse(
            status="unavailable",
            configured=True,
            provider=record.provider,
            model=record.model,
            message="The latest stored AI analysis failed schema validation.",
        )

    return AILatestResponse(
        status="completed",
        configured=True,
        provider=record.provider,
        model=record.model,
        generated_at=record.generated_at.isoformat() if record.generated_at else None,
        message="Latest completed AI analysis loaded.",
        analysis=analysis,
    )


@router.post("/chat", response_model=AIChatResponse)
async def chat(request: AIChatRequest) -> AIChatResponse:
    settings = get_settings()
    provider = get_ai_provider()
    result = await provider.chat(request.message, request.context)

    return AIChatResponse(
        status=result.get("status", "unconfigured"),
        configured=result.get("configured", False),
        provider=settings.ai_provider,
        message=result.get(
            "message",
            "AI chat service is in scaffold mode and has not been configured to make external API calls.",
        ),
        reply=result.get("reply"),
    )


def _persist_analysis(
    db: Session,
    context: dict,
    result: dict,
    analysis: AIAnalysisOutput | None,
    snapshot_date: str | None,
) -> None:
    """Persist both successful and failed attempts without replacing success."""
    try:
        parsed_snapshot_date = date.fromisoformat(snapshot_date) if snapshot_date else date.today()
        snapshot = MarketSnapshot(
            snapshot_date=parsed_snapshot_date,
            generated_at=datetime.now(timezone.utc),
            payload_json=context,
        )
        db.add(snapshot)
        db.flush()
        db.add(
            AIAnalysis(
                analysis_type="daily_dashboard_analysis",
                generated_at=datetime.now(timezone.utc),
                provider=result.get("provider"),
                model=result.get("model"),
                market_snapshot_id=snapshot.id,
                input_context_json=context,
                output_json=analysis.model_dump(mode="json") if analysis else None,
                status="completed" if analysis else result.get("status", "error"),
            )
        )
        db.commit()
    except (SQLAlchemyError, ValueError, TypeError):
        db.rollback()
