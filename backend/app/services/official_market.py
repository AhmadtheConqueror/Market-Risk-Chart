"""Platts-authoritative official KPIs; API/futures infrastructure is independent."""
from datetime import datetime, time, timedelta, timezone
import math
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import load_only
from app.models.historical import HistoricalMarketObservation as H
from app.schemas.market import InstrumentStatsResponse, NormalizedObservation, ProductSpreadItem
from app.services.calculations import calculate_instrument_stats
from app.services.historical_market import HISTORICAL_MAPPING


def historical_observation(row, now=None):
    now = now or datetime.now(timezone.utc)
    symbol, label, unit, factor, *_ = HISTORICAL_MAPPING[row.instrument_key]
    assessment = datetime.combine(row.assessment_date, time.min, tzinfo=timezone.utc)
    return NormalizedObservation(
        instrumentId=row.instrument_key, providerSymbol=symbol, name=label,
        value=float(row.native_value), unit=unit, assessmentDate=row.assessment_date.isoformat(),
        retrievedAt=row.imported_at.isoformat(), provider="platts_excel", sourceType="excel",
        sourceTimestamp=assessment.isoformat(), ageSeconds=max(0, (now-assessment).total_seconds()),
        freshnessStatus="stale" if (now.date()-row.assessment_date).days > 3 else "fresh",
        barrelsPerMT=factor, convertedValue=float(row.native_value)/factor if factor else float(row.native_value),
        benchmarkDefinition=label)


def load_snapshot_history(session):
    """Read only calculation windows, previous assessments and spread anchors.

    Full-history analytics uses the unchanged full-history reader. Aggregate
    counts/date anchors require seven rows, regardless of stored history size.
    """
    policy = or_(*(and_(H.instrument_key == key, H.provider_symbol == spec[0],
        func.upper(H.native_unit) == spec[2]) for key, spec in HISTORICAL_MAPPING.items()))
    ranked = select(H.id, H.instrument_key, H.assessment_date,
        func.row_number().over(partition_by=H.instrument_key,
            order_by=H.assessment_date.desc()).label("position")).where(
        H.provider == "platts_excel", policy).subquery()
    summaries = session.execute(select(ranked.c.instrument_key,
        func.max(ranked.c.assessment_date), func.count()).group_by(ranked.c.instrument_key)).all()
    windows = {key: latest - timedelta(days=89) for key, latest, count in summaries}
    product_dates = [latest for key, latest, count in summaries if HISTORICAL_MAPPING[key][3]]
    needed = or_(ranked.c.position <= 2, *(and_(ranked.c.instrument_key == key,
        ranked.c.assessment_date >= cutoff) for key, cutoff in windows.items()))
    if product_dates:
        needed = or_(needed, and_(ranked.c.instrument_key == "brent",
            ranked.c.assessment_date.in_(product_dates)))
    rows = session.scalars(select(H).join(ranked, H.id == ranked.c.id).where(needed)
        .options(load_only(H.instrument_key, H.provider, H.provider_symbol,
            H.assessment_date, H.native_value, H.native_unit, H.imported_at))
        .order_by(H.assessment_date)).all()
    grouped = {key: [] for key in HISTORICAL_MAPPING}
    for row in rows:
        grouped[row.instrument_key].append(row)
    return grouped


def official_market_snapshot(session):
    grouped = load_snapshot_history(session)
    stats, spreads = [], []
    now = datetime.now(timezone.utc)
    for key, (symbol, label, unit, factor, *_) in HISTORICAL_MAPPING.items():
        history = grouped[key]
        calculated = calculate_instrument_stats([
            {"assessment_date": row.assessment_date, "value": row.native_value} for row in history
        ], window_days=90, min_history_points=60)
        calculated.pop("latest_observation")
        latest = historical_observation(history[-1], now) if history else None
        stats.append(InstrumentStatsResponse(
            instrument_id=key, display_name=label, provider="platts_excel", provider_symbol=symbol,
            history=[historical_observation(row, now) for row in history
                if row.assessment_date >= history[-1].assessment_date - timedelta(days=89)],
            provider_display_name=label, benchmark_definition=label, unit=unit,
            benchmark_status="confirmed" if latest else "unavailable",
            freshness_status=latest.freshness_status if latest else "unavailable",
            source_timestamp=latest.source_timestamp if latest else None,
            retrieved_at=latest.retrieved_at if latest else None,
            unavailable_reason=None if latest else "Platts workbook assessment unavailable; upload the mapped workbook.",
            **calculated))
    brent = {r.assessment_date: float(r.native_value) for r in grouped["brent"]}
    for key, (symbol, label, unit, factor, *_) in HISTORICAL_MAPPING.items():
        if factor is None:
            continue
        latest = grouped[key][-1] if grouped[key] else None
        value = float(latest.native_value) if latest else None
        converted = value/factor if value is not None else None
        benchmark = brent.get(latest.assessment_date) if latest else None
        comparable = converted is not None and benchmark is not None
        spreads.append(ProductSpreadItem(instrument_id=key, display_name=label,
            date=latest.assessment_date.isoformat() if latest else None,
            original_price=value, original_unit=unit, barrels_per_mt=factor,
            converted_price=converted, brent_price=benchmark,
            spread=converted-benchmark if comparable else None, is_comparable=comparable,
            conversion_method="mt_to_bbl"))
    outliers = sorted((s for s in stats if s.window_count >= 60 and s.z_score is not None
        and math.isfinite(s.z_score) and abs(s.z_score) >= 2.0), key=lambda s: abs(s.z_score), reverse=True)
    return stats, outliers, spreads
