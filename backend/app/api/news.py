from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.news import NewsItemResponse, NewsLatestResponse, NewsRefreshSummary
from app.services.news_ingestion import get_recent_news, refresh_news

router = APIRouter(prefix="/news", tags=["news"])


@router.post("/refresh", response_model=NewsRefreshSummary)
async def refresh_news_endpoint(db: Annotated[Session, Depends(get_db)]) -> NewsRefreshSummary:
    return await refresh_news(db)


@router.get("/latest", response_model=NewsLatestResponse)
def latest_news(
    region: Annotated[str | None, Query(pattern="^(international|africa|nigeria)$")] = None,
    topic: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 15,
    db: Annotated[Session, Depends(get_db)] = None,
) -> NewsLatestResponse:
    items = get_recent_news(db, region=region, topic=topic, limit=limit)
    return NewsLatestResponse(
        items=[NewsItemResponse.model_validate(item) for item in items],
        generated_at=datetime.now(timezone.utc),
    )
