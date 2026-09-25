from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict


class MacroIndicatorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    indicator_key: str
    display_name: str
    value: float | None = None
    unit: str
    reporting_period: str
    source: str
    source_url: str | None = None
    published_at: str | None = None
    retrieved_at: str | None = None
    status: str = "published"
    freshness_status: str = "fresh"
    metadata_json: dict[str, Any] = {}


class MacroRefreshSummary(BaseModel):
    requested: int
    stored: int
    updated: int
    unchanged: int
    failed: int
    indicators: list[MacroIndicatorResponse] = []
    errors: list[dict[str, str]] = []
