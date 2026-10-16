from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.market import MarketInstrument, MarketObservation
from app.schemas.market import (
    HistoryPoint,
    MarketHistoryResponse,
    MarketInstrumentResponse,
    MarketLatestResponse,
    MarketImportSummary,
    MarketRefreshResponse,
    NormalizedObservation,
)
from app.services.calculations import PRODUCT_CONVERSIONS, is_gallon_unit
from app.services.market_ingestion import (
    backfill_all_instruments,
    backfill_history,
)
from app.services.excel_ingestion import EXCEL_PROVIDER, ExcelValidationError, parse_market_workbook

router = APIRouter(prefix="/market", tags=["market"])

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def observation_to_normalized(obs: MarketObservation, instrument_key: str) -> NormalizedObservation:
    val = float(obs.value)
    conversion_factor = PRODUCT_CONVERSIONS.get(instrument_key)
    normalized_unit = obs.unit.lower().replace(" ", "")
    if is_gallon_unit(obs.unit):
        converted_val = val * 42
        conversion_factor = None
    elif normalized_unit in {"barrel", "bbl", "usd/bbl", "usd/barrel", "$/bbl"}:
        converted_val = val
        conversion_factor = None
    elif normalized_unit in {"metric_ton", "tonne", "mt", "usd/mt", "usd/tonne", "usd/metricton", "$/mt"}:
        converted_val = val / conversion_factor if conversion_factor else None
    else:
        converted_val = None
        conversion_factor = None

    now = datetime.now(timezone.utc)
    ref_ts = obs.source_timestamp or obs.retrieved_at or obs.created_at
    if ref_ts.tzinfo is None:
        ref_ts = ref_ts.replace(tzinfo=timezone.utc)

    age_sec = max(0.0, (now - ref_ts).total_seconds())
    # 36 hours accounts for normal daily market close and standard weekend gaps
    freshness = "fresh" if age_sec <= 36 * 3600 else "stale"

    return NormalizedObservation(
        instrumentId=instrument_key,
        providerSymbol=obs.provider_symbol,
        name=obs.instrument.display_name if obs.instrument else instrument_key.title(),
        value=val,
        unit=obs.unit,
        assessmentDate=obs.assessment_date.isoformat(),
        retrievedAt=obs.retrieved_at.isoformat() if obs.retrieved_at else obs.created_at.isoformat(),
        provider=obs.provider,
        sourceType="excel" if obs.provider == EXCEL_PROVIDER else "api",
        sourceTimestamp=obs.source_timestamp.isoformat() if obs.source_timestamp else None,
        ageSeconds=round(age_sec, 1),
        freshnessStatus=freshness,
        barrelsPerMT=conversion_factor,
        convertedValue=converted_val,
        benchmarkDefinition=obs.benchmark_definition,
    )


@router.get("/instruments", response_model=list[MarketInstrumentResponse])
def get_instruments(db: Annotated[Session, Depends(get_db)]) -> list[MarketInstrumentResponse]:
    stmt = (
        select(MarketInstrument)
        .where(MarketInstrument.enabled.is_(True))
        .order_by(MarketInstrument.id)
    )
    instruments = db.scalars(stmt).all()
    from app.services.historical_market import HISTORICAL_MAPPING
    records = {inst.instrument_key: inst for inst in instruments}
    return [(MarketInstrumentResponse.model_validate(records[key]) if key in records
        else MarketInstrumentResponse(instrument_key=key, display_name=spec[1], unit=spec[2]))
        .model_copy(update={"display_name": spec[1], "provider": "platts_excel",
            "provider_symbol": spec[0], "unit": spec[2]})
        for key, spec in HISTORICAL_MAPPING.items()]



@router.get("/latest", response_model=MarketLatestResponse)
def get_latest_market_data(db: Annotated[Session, Depends(get_db)]) -> MarketLatestResponse:
    from app.services.historical_market import load_historical_series
    from app.services.official_market import historical_observation
    grouped = load_historical_series(db)
    return MarketLatestResponse(observations=[historical_observation(rows[-1])
        for rows in grouped.values() if rows])


@router.get("/history", response_model=MarketHistoryResponse)
def get_market_history(
    instrument: Annotated[str, Query(description="Canonical instrument key, e.g. brent")],
    days: Annotated[int, Query(ge=1, le=1000, description="Calendar day window")] = 90,
    db: Annotated[Session, Depends(get_db)] = None,
) -> MarketHistoryResponse:
    inst_key = instrument.strip().lower()
    if inst_key.startswith("mr_"):
        inst_key = inst_key.removeprefix("mr_")

    from app.services.historical_market import HISTORICAL_MAPPING, load_historical_series
    from app.services.official_market import historical_observation
    if inst_key not in HISTORICAL_MAPPING:
        raise HTTPException(status_code=404, detail=f"Instrument '{instrument}' not found.")
    history = load_historical_series(db)[inst_key]
    latest_date = history[-1].assessment_date if history else None
    selected = [row for row in history if row.assessment_date >= latest_date - timedelta(days=days-1)] if history else []
    return MarketHistoryResponse(instrument=inst_key, days=days, total_observations=len(selected),
        history_status="unavailable" if not selected else "sufficient" if len(selected)>=min(60,days*0.7) else "insufficient_history",
        observations=[historical_observation(row) for row in selected],
        history_points=[HistoryPoint(date=row.assessment_date.isoformat(), value=float(row.native_value)) for row in selected])


@router.post("/refresh", response_model=MarketRefreshResponse)
async def refresh_market_data(db: Annotated[Session, Depends(get_db)]) -> MarketRefreshResponse:
    """Reload official persisted assessments; collection requires an Admin workbook upload."""
    from app.services.historical_market import HISTORICAL_MAPPING
    return MarketRefreshResponse(provider="platts_excel", requested=0, stored=0,
        skipped=7, refreshedAt=datetime.now(timezone.utc).isoformat(),
        instruments=list(HISTORICAL_MAPPING),
        message="Platts assessments reloaded. Upload a refreshed workbook in Admin to update them.")


@router.post("/backfill")
async def backfill_market_history(
    days: int = Query(90, ge=1, le=365, description="Number of days to backfill"),
    period: str = Query("past_year", description="Historical period endpoint"),
    instrument: str | None = Query(None, description="Optional specific instrument key"),
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict[str, Any]:
    """Backfills historical market data using past_year to ensure sufficient coverage for 90-day requests."""
    if instrument:
        inst_key = instrument.strip().lower()
        inst = db.scalars(select(MarketInstrument).where(MarketInstrument.instrument_key == inst_key)).first()
        if not inst:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Instrument '{instrument}' not found.")
        return await backfill_history(db, inst, period=period, days=days)
    return await backfill_all_instruments(db, period=period, days=days)


@router.get("/historical")
def get_historical_analytics(db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    from app.services.historical_market import historical_analytics
    return historical_analytics(db)


@router.post("/import-excel", response_model=MarketImportSummary)
async def import_excel_market_data(
    workbook: UploadFile = File(...),
    db: Annotated[Session, Depends(get_db)] = None,
) -> MarketImportSummary:
    from app.services.historical_market import persist_history
    if not workbook.filename or not workbook.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx workbooks are accepted.")
    file_bytes = await workbook.read()
    try:
        observations, summary = parse_market_workbook(file_bytes)
    except ExcelValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    uploaded_at = datetime.now(timezone.utc)
    stored, updated = persist_history(db, observations, file_bytes, workbook.filename, uploaded_at)
    # The historical table is now the canonical current + historical store for all seven.
    db.commit()
    return MarketImportSummary(provider="platts_excel",
        historical_rows_inserted=stored, historical_rows_updated_or_unchanged=updated,
        latest_historical_assessment_date=summary["date_range"]["to"],
        mapped_historical_instruments=summary["instruments_affected"],
        rows_read=summary["rows_read"],rows_valid=summary["rows_valid"],
        rows_stored=stored,rows_updated=updated,rows_rejected=summary["rows_rejected"],
        instruments_affected=summary["instruments_affected"],date_range=summary["date_range"],
        errors=summary["errors"],uploaded_at=uploaded_at.isoformat())
