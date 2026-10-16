from __future__ import annotations

from datetime import datetime, timezone
import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.news import NewsItemResponse, NewsLatestResponse, NewsRefreshSummary
from app.services.news_ingestion import get_recent_news, get_last_news_refresh, refresh_news

router = APIRouter(prefix="/news", tags=["news"])


@router.post("/refresh", response_model=NewsRefreshSummary)
def refresh_news_endpoint(db: Annotated[Session, Depends(get_db)]) -> NewsRefreshSummary:
    # Run provider collection/persistence in FastAPI's worker pool, not its event loop.
    return asyncio.run(refresh_news(db))


@router.get("/latest", response_model=NewsLatestResponse)
def latest_news(
    region: Annotated[str | None, Query(pattern="^(international|africa|nigeria)$")] = None,
    topic: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 15,
    db: Annotated[Session, Depends(get_db)] = None,
) -> NewsLatestResponse:
    items = get_recent_news(db, region=region, topic=topic, limit=limit)
    audit = get_last_news_refresh(db)
    return NewsLatestResponse(
        items=[NewsItemResponse.model_validate(item) for item in items],
        generated_at=datetime.now(timezone.utc),
        last_refresh=audit,
        diagnostics={"refresh_attempted": audit is not None,
            "empty_reason": None if items else "no_recent_articles" if audit else "refresh_not_attempted",
            "visible_items": len(items),
            "provider_unavailable": [s["source_key"] for s in (audit or {}).get("sources", []) if s.get("status") == "failed"],
            "irrelevant_rejected": sum(s.get("rejection_reasons", {}).get("not_energy_relevant", 0) for s in (audit or {}).get("sources", [])),
            "audit_scope": "all_providers"},
    )
