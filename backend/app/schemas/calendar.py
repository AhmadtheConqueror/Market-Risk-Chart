from __future__ import annotations

from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class CalendarEventItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str | None = None
    provider: str = "manual"
    event_date: str | None = None
    end_date: str | None = None
    legacy_date: str | None = None
    title: str
    category: str
    region: str = "Global"
    country: str | None = None
    impact_level: str | None = None
    description: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    source_type: str = "manual"
    verified_at: str | None = None
    active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class CalendarEventCreate(BaseModel):
    title: str = Field(..., min_length=1)
    event_date: str | None = None
    end_date: str | None = None
    legacy_date: str | None = None
    category: str = "macro"
    region: str = "Global"
    country: str | None = None
    impact_level: str | None = None
    description: str | None = None
    source_name: str | None = "Manual entry"
    source_url: str | None = None
    active: bool = True


class CalendarEventUpdate(BaseModel):
    title: str | None = None
    event_date: str | None = None
    end_date: str | None = None
    category: str | None = None
    region: str | None = None
    country: str | None = None
    impact_level: str | None = None
    description: str | None = None
    active: bool | None = None


class ProviderRefreshResult(BaseModel):
    name: str
    source: str
    status: str
    events_found: int = 0
    created: int = 0
    updated: int = 0
    error: str | None = None


class CalendarRefreshResponse(BaseModel):
    sources_requested: int
    sources_succeeded: int
    sources_failed: int
    events_created: int
    events_updated: int
    events_unchanged: int
    provider_results: list[ProviderRefreshResult] = []


class CalendarMigrationRequest(BaseModel):
    events: list[dict[str, Any]] = []


class CalendarMigrationResponse(BaseModel):
    migrated: int
    skipped: int
    total_submitted: int
