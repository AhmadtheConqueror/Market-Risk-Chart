from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
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
    ingest_latest_market_data,
)
from app.services.excel_ingestion import EXCEL_PROVIDER, ExcelValidationError, parse_market_workbook
from app.services.source_resolution import get_source_policy, resolve_observations

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
    return [MarketInstrumentResponse.model_validate(inst) for inst in instruments]


@router.get("/latest", response_model=MarketLatestResponse)
def get_latest_market_data(db: Annotated[Session, Depends(get_db)]) -> MarketLatestResponse:
    instruments = db.scalars(select(MarketInstrument).where(MarketInstrument.enabled.is_(True))).all()

    observations: list[NormalizedObservation] = []
    for inst in instruments:
        stmt = (
            select(MarketObservation)
            .where(MarketObservation.instrument_id == inst.id)
            .order_by(desc(MarketObservation.assessment_date), desc(MarketObservation.id))
            .limit(1)
        )
        records = db.scalars(
            select(MarketObservation)
            .where(MarketObservation.instrument_id == inst.id)
            .order_by(MarketObservation.assessment_date.asc(), MarketObservation.id.asc())
        ).all()
        selected, _, _ = resolve_observations(inst, records)
        latest_obs = selected[-1] if selected else None
        if latest_obs:
            observations.append(observation_to_normalized(latest_obs, inst.instrument_key))

    return MarketLatestResponse(observations=observations)


@router.get("/history", response_model=MarketHistoryResponse)
def get_market_history(
    instrument: Annotated[str, Query(description="Canonical instrument key, e.g. brent")],
    days: Annotated[int, Query(ge=1, le=1000, description="Calendar day window")] = 90,
    db: Annotated[Session, Depends(get_db)] = None,
) -> MarketHistoryResponse:
    inst_key = instrument.strip().lower()
    if inst_key.startswith("mr_"):
        inst_key = inst_key.removeprefix("mr_")

    stmt = select(MarketInstrument).where(MarketInstrument.instrument_key == inst_key)
    inst = db.scalars(stmt).first()
    if not inst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instrument '{instrument}' not found.",
        )

    records = db.scalars(
        select(MarketObservation)
        .where(MarketObservation.instrument_id == inst.id)
        .order_by(MarketObservation.assessment_date.asc(), MarketObservation.id.asc())
    ).all()
    selected, _, resolution_status = resolve_observations(inst, records)
    latest_date = selected[-1].assessment_date if selected else None

    if not latest_date:
        return MarketHistoryResponse(
            instrument=inst_key,
            days=days,
            total_observations=0,
            history_status="unavailable" if resolution_status != "preferred_unavailable" else "source_unavailable",
            observations=[],
            history_points=[],
        )

    start_date = latest_date - timedelta(days=days - 1)
    observations = [
        obs for obs in selected
        if start_date <= obs.assessment_date <= latest_date
    ]

    norm_obs = [observation_to_normalized(obs, inst_key) for obs in observations]
    history_pts = [HistoryPoint(date=obs.assessment_date.isoformat(), value=float(obs.value)) for obs in observations]

    # Evaluate sufficiency for the requested days
    history_status = "sufficient" if len(observations) >= min(60, days * 0.7) else "insufficient_history"

    return MarketHistoryResponse(
        instrument=inst_key,
        days=days,
        total_observations=len(norm_obs),
        history_status=history_status,
        observations=norm_obs,
        history_points=history_pts,
    )


@router.post("/refresh", response_model=MarketRefreshResponse)
async def refresh_market_data(db: Annotated[Session, Depends(get_db)]) -> MarketRefreshResponse:
    """Refreshes market observations from the active provider for all mapped instruments.

    Idempotently upserts daily assessments in Supabase.
    """
    summary = await ingest_latest_market_data(db)
    return MarketRefreshResponse.model_validate(summary)


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
    # Forcados alone retains the approved current workbook-backed continuity.
    instrument = db.scalars(select(MarketInstrument).where(MarketInstrument.instrument_key=="forcados", MarketInstrument.enabled.is_(True))).first()
    if instrument:
        instrument.provider = EXCEL_PROVIDER
        instrument.provider_symbol = "PCABC00"
        records = [{"instrument_id":instrument.id,"assessment_date":item.assessment_date,
            "value":item.value,"unit":item.unit,"provider":EXCEL_PROVIDER,
            "provider_symbol":item.provider_symbol,
            "source_timestamp":datetime.combine(item.assessment_date,time.min,tzinfo=timezone.utc),
            "retrieved_at":uploaded_at,"benchmark_definition":"Forcados FOB Nigeria"}
            for item in observations if item.instrument_key=="forcados"]
        insert = postgresql_insert if db.get_bind().dialect.name=="postgresql" else sqlite_insert
        for offset in range(0,len(records),100):
            statement = insert(MarketObservation).values(records[offset:offset+100])
            statement = statement.on_conflict_do_update(
                index_elements=["instrument_id","provider","provider_symbol","assessment_date"],
                set_={key:getattr(statement.excluded,key) for key in records[0]
                    if key not in {"instrument_id","provider","provider_symbol","assessment_date"}})
            db.execute(statement)
    db.commit()
    return MarketImportSummary(provider="platts_excel",rows_read=summary["rows_read"],rows_valid=summary["rows_valid"],
        rows_stored=stored,rows_updated=updated,rows_rejected=summary["rows_rejected"],
        instruments_affected=summary["instruments_affected"],date_range=summary["date_range"],
        errors=summary["errors"],uploaded_at=uploaded_at.isoformat())
