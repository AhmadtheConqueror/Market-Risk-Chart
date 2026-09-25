from __future__ import annotations

from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class MarketInstrumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    instrument_key: str
    display_name: str
    provider: str | None = None
    provider_symbol: str | None = None
    unit: str
    category: str = "market"
    enabled: bool = True
    created_at: datetime
    updated_at: datetime


class NormalizedObservation(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    instrument_id: str = Field(..., alias="instrumentId")
    provider_symbol: str = Field(..., alias="providerSymbol")
    name: str
    value: float
    unit: str
    assessment_date: str = Field(..., alias="assessmentDate")
    retrieved_at: str = Field(..., alias="retrievedAt")
    provider: str
    source_type: str = Field("api", alias="sourceType")
    source_timestamp: str | None = Field(None, alias="sourceTimestamp")
    age_seconds: float | None = Field(None, alias="ageSeconds")
    freshness_status: str = Field("fresh", alias="freshnessStatus")
    barrels_per_mt: float | None = Field(None, alias="barrelsPerMT")
    converted_value: float | None = Field(None, alias="convertedValue")
    benchmark_definition: str | None = Field(None, alias="benchmarkDefinition")


class MarketLatestResponse(BaseModel):
    observations: list[NormalizedObservation]


class HistoryPoint(BaseModel):
    date: str
    value: float


class MarketHistoryResponse(BaseModel):
    instrument: str
    days: int
    total_observations: int
    history_status: str = "valid"
    observations: list[NormalizedObservation]
    history_points: list[HistoryPoint] = []


class InstrumentStatsResponse(BaseModel):
    instrument_id: str
    display_name: str
    current_value: float | None = None
    previous_value: float | None = None
    change: float | None = None
    percent_change: float | None = None
    mean_90: float | None = None
    std_dev_90: float | None = None
    z_score: float | None = None
    window_count: int = 0
    history_status: str = "valid"
    latest_date: str | None = None
    unit: str | None = None
    provider: str | None = None
    provider_symbol: str | None = None
    provider_display_name: str | None = None
    benchmark_status: str = "confirmed"
    freshness_status: str = "fresh"
    source_timestamp: str | None = None
    retrieved_at: str | None = None
    unavailable_reason: str | None = None
    benchmark_definition: str | None = None


class ProductSpreadItem(BaseModel):
    instrument_id: str
    display_name: str
    date: str | None = None
    original_price: float | None = None
    original_unit: str = "USD/mt"
    barrels_per_mt: float | None = None
    converted_price: float | None = None
    brent_price: float | None = None
    spread: float | None = None
    is_comparable: bool = False


class MarketRefreshResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider: str
    requested: int
    stored: int
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    refreshed_at: str = Field(..., alias="refreshedAt")
    instruments: list[str] = []
    message: str | None = None


class MarketImportSummary(BaseModel):
    rows_read: int
    rows_valid: int
    rows_stored: int
    rows_updated: int
    rows_rejected: int
    instruments_affected: list[str]
    date_range: dict[str, str] | None = None
    errors: list[str] = []
    provider: str = "internal_excel"
    uploaded_at: str
