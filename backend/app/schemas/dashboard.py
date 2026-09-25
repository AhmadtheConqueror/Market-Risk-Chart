from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict
from app.schemas.market import InstrumentStatsResponse, NormalizedObservation, ProductSpreadItem


class RiskRegisterItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    risk_category: str
    materiality: str
    trend: str
    risk_owner: str
    display_order: int = 0
    active: bool = True


class MacroIndicatorItem(BaseModel):
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


class DashboardContentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    section_key: str
    item_key: str
    title: str | None = None
    content: str
    classification: str | None = None
    metadata_json: dict[str, Any] = {}
    display_order: int = 0
    active: bool = True


class DashboardSnapshotResponse(BaseModel):
    snapshot_date: str
    generated_at: str
    market_stats: list[InstrumentStatsResponse] = []
    outliers: list[InstrumentStatsResponse] = []
    product_spreads: list[ProductSpreadItem] = []
    macro_indicators: list[MacroIndicatorItem] = []
    risk_register: list[RiskRegisterItem] = []
    dashboard_content: list[DashboardContentItem] = []
    ai_analysis: dict[str, Any] | None = None
