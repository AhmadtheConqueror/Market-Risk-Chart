from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from time import perf_counter
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
from app.services.calculations import PRODUCT_CONVERSIONS
from app.services.market_ingestion import ingest_latest_market_data
from app.services.excel_ingestion import EXCEL_PROVIDER, ExcelValidationError, parse_market_workbook
from app.services.market_ingestion import upsert_observation
from app.services.source_resolution import get_source_policy, resolve_observations

router = APIRouter(prefix="/market", tags=["market"])

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def observation_to_normalized(obs: MarketObservation, instrument_key: str) -> NormalizedObservation:
    val = float(obs.value)
    conversion_factor = PRODUCT_CONVERSIONS.get(instrument_key)
    converted_val = (val / conversion_factor) if conversion_factor and conversion_factor > 0 else None

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


@router.post("/import-excel", response_model=MarketImportSummary)
async def import_excel_market_data(
    workbook: UploadFile = File(...),
    db: Annotated[Session, Depends(get_db)] = None,
) -> MarketImportSummary:
    total_started = perf_counter()
    if not workbook.filename or not workbook.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .xlsx workbooks are accepted.")

    try:
        parse_started = perf_counter()
        observations, summary = parse_market_workbook(await workbook.read())
        parse_seconds = perf_counter() - parse_started
    except ExcelValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    instruments = {
        instrument.instrument_key: instrument
        for instrument in db.scalars(select(MarketInstrument).where(MarketInstrument.enabled.is_(True))).all()
    }
    # Keep existing instrument metadata aligned with the canonical source policy
    # so an upload repairs stale/null Excel mappings without creating a fallback.
    for instrument in instruments.values():
        policy = get_source_policy(instrument.instrument_key)
        if policy and policy.preferred_provider == EXCEL_PROVIDER:
            instrument.provider = policy.preferred_provider
            instrument.provider_symbol = policy.preferred_symbol

    stored = updated = rejected = 0
    errors = list(summary["errors"])
    uploaded_at = datetime.now(timezone.utc)
    affected: set[str] = set()
    records: list[dict[str, object]] = []
    record_keys: list[tuple[int, str, str, object]] = []

    for item in observations:
        instrument = instruments.get(item.instrument_key)
        policy = get_source_policy(item.instrument_key)
        if not instrument or not policy or policy.preferred_provider != EXCEL_PROVIDER:
            rejected += 1
            if len(errors) < 50:
                errors.append(f"{item.provider_symbol}: no configured Excel source policy or instrument.")
            continue

        records.append({
            "instrument_id": instrument.id,
            "assessment_date": item.assessment_date,
            "value": item.value,
            "unit": item.unit,
            "provider": EXCEL_PROVIDER,
            "provider_symbol": item.provider_symbol,
            "source_timestamp": datetime.combine(item.assessment_date, time.min, tzinfo=timezone.utc),
            "retrieved_at": uploaded_at,
            "benchmark_definition": item.benchmark_definition,
        })
        record_keys.append((instrument.id, EXCEL_PROVIDER, item.provider_symbol, item.assessment_date))
        affected.add(item.instrument_key)

    persistence_started = perf_counter()
    if records:
        existing_rows = db.scalars(
            select(MarketObservation).where(
                MarketObservation.provider == EXCEL_PROVIDER,
                MarketObservation.provider_symbol.in_({key[2] for key in record_keys}),
                MarketObservation.assessment_date.in_({key[3] for key in record_keys}),
            )
        ).all()
        existing_keys = {
            (row.instrument_id, row.provider, row.provider_symbol, row.assessment_date)
            for row in existing_rows
        }
        stored = sum(key not in existing_keys for key in record_keys)
        updated = sum(key in existing_keys for key in record_keys)

        dialect_name = db.get_bind().dialect.name
        if dialect_name == "postgresql":
            insert_statement = postgresql_insert(MarketObservation)
        elif dialect_name == "sqlite":
            insert_statement = sqlite_insert(MarketObservation)
        else:
            insert_statement = None

        if insert_statement is not None:
            statement = insert_statement.values(records)
            statement = statement.on_conflict_do_update(
                index_elements=[
                    "instrument_id",
                    "provider",
                    "provider_symbol",
                    "assessment_date",
                ],
                set_={
                    "value": statement.excluded.value,
                    "unit": statement.excluded.unit,
                    "source_timestamp": statement.excluded.source_timestamp,
                    "retrieved_at": statement.excluded.retrieved_at,
                    "benchmark_definition": statement.excluded.benchmark_definition,
                },
            )
            db.execute(statement)
        else:
            # Preserve the existing idempotent behavior for unsupported dialects.
            stored = updated = 0
            for item in observations:
                instrument = instruments.get(item.instrument_key)
                policy = get_source_policy(item.instrument_key)
                if not instrument or not policy or policy.preferred_provider != EXCEL_PROVIDER:
                    continue
                _, action = upsert_observation(
                    db,
                    instrument,
                    {
                        "raw_value": item.value,
                        "raw_unit": item.unit,
                        "assessment_date": item.assessment_date,
                        "provider": EXCEL_PROVIDER,
                        "provider_symbol": item.provider_symbol,
                        "source_timestamp": datetime.combine(item.assessment_date, time.min, tzinfo=timezone.utc),
                        "retrieved_at": uploaded_at,
                        "benchmark_definition": item.benchmark_definition,
                    },
                )
                if action == "stored":
                    stored += 1
                elif action == "updated":
                    updated += 1

    db.commit()
    persistence_seconds = perf_counter() - persistence_started
    total_seconds = perf_counter() - total_started
    logger.warning(
        "Excel import timings: rows=%d parse_seconds=%.3f persistence_seconds=%.3f total_seconds=%.3f",
        len(observations),
        parse_seconds,
        persistence_seconds,
        total_seconds,
    )
    return MarketImportSummary(
        rows_read=summary["rows_read"],
        rows_valid=summary["rows_valid"],
        rows_stored=stored,
        rows_updated=updated,
        rows_rejected=summary["rows_rejected"] + rejected,
        instruments_affected=sorted(affected),
        date_range=summary["date_range"],
        errors=errors,
        uploaded_at=uploaded_at.isoformat(),
    )
