from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Region = Literal["international", "africa", "nigeria"]


class NewsItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_key: str
    source_name: str
    title: str
    url: str
    published_at: datetime
    retrieved_at: datetime
    snippet: str | None = None
    region: Region
    topic: str
    relevance_status: str
    active: bool = True


class NewsLatestResponse(BaseModel):
    items: list[NewsItemResponse] = Field(default_factory=list)
    generated_at: datetime
    last_refresh: dict | None = None


class NewsSourceResult(BaseModel):
    source_key: str
    status: str
    items_found: int = 0
    stored: int = 0
    updated: int = 0
    unchanged: int = 0
    error: str | None = None
    requests: list[dict] = Field(default_factory=list)
    candidates: int = 0
    rejected: int = 0
    rejection_reasons: dict[str, int] = Field(default_factory=dict)
    latest_publication: datetime | None = None
    latest_source_publication: datetime | None = None
    fresh_items: int = 0
    excluded_stale: int = 0
    duplicates: int = 0


class NewsRefreshSummary(BaseModel):
    sources_requested: int
    sources_succeeded: int
    items_found: int
    stored: int
    updated: int
    unchanged: int
    failed: int
    errors: list[str] = Field(default_factory=list)
    sources: list[NewsSourceResult] = Field(default_factory=list)
    retrieved_at: datetime
