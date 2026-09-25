from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.market import MarketInstrument, MarketObservation
from app.providers.market.factory import get_market_provider
from app.providers.market.oilpriceapi import OilPriceAPIProvider
from app.services.source_resolution import get_source_policy

logger = logging.getLogger(__name__)


def parse_date(val: Any) -> date | None:
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str) and val.strip():
        try:
            return datetime.fromisoformat(val.strip().replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return datetime.strptime(val.strip()[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
    return None


def upsert_observation(
    session: Session,
    instrument: MarketInstrument,
    raw_obs: dict[str, Any],
) -> tuple[MarketObservation | None, str]:
    """Idempotently inserts or updates an observation for the daily assessment model.

    Preserves raw provider value and unit without premature conversions.
    Returns (observation, action) where action is 'stored', 'updated', or 'skipped'.
    """
    raw_val = raw_obs.get("raw_value")
    if raw_val is None:
        return None, "skipped"

    assessment_dt = parse_date(raw_obs.get("assessment_date"))
    if assessment_dt is None:
        return None, "skipped"

    provider = raw_obs.get("provider") or instrument.provider or "oilpriceapi"
    provider_symbol = raw_obs.get("provider_symbol") or instrument.provider_symbol or instrument.instrument_key.upper()
    unit = raw_obs.get("raw_unit") or instrument.unit
    source_ts = raw_obs.get("source_timestamp")
    retrieved_at = raw_obs.get("retrieved_at") or datetime.now(timezone.utc)

    # Check for existing observation for the same (instrument, provider, provider_symbol, assessment_date)
    existing = session.scalars(
        select(MarketObservation).where(
            MarketObservation.instrument_id == instrument.id,
            MarketObservation.provider == provider,
            MarketObservation.provider_symbol == provider_symbol,
            MarketObservation.assessment_date == assessment_dt,
        )
    ).first()

    if existing:
        # Same-day refresh: update existing record with newest provider value and timestamps
        existing.value = Decimal(str(raw_val))
        existing.unit = unit
        if source_ts:
            existing.source_timestamp = source_ts
        existing.retrieved_at = retrieved_at
        if raw_obs.get("benchmark_definition"):
            existing.benchmark_definition = raw_obs["benchmark_definition"]
        return existing, "updated"
    else:
        new_obs = MarketObservation(
            instrument_id=instrument.id,
            assessment_date=assessment_dt,
            value=Decimal(str(raw_val)),
            unit=unit,
            provider=provider,
            provider_symbol=provider_symbol,
            source_timestamp=source_ts,
            retrieved_at=retrieved_at,
            benchmark_definition=raw_obs.get("benchmark_definition"),
        )
        session.add(new_obs)
        return new_obs, "stored"


async def ingest_latest_market_data(
    session: Session,
    provider: OilPriceAPIProvider | None = None,
) -> dict[str, Any]:
    """Ingests latest observations for all enabled instruments with a configured provider_symbol."""
    refreshed_at = datetime.now(timezone.utc)
    if provider is None:
        provider = get_market_provider()

    # Query instruments with provider_symbol set
    stmt = (
        select(MarketInstrument)
        .where(
            MarketInstrument.enabled.is_(True),
            MarketInstrument.provider_symbol.isnot(None),
        )
        .order_by(MarketInstrument.id)
    )
    instruments = [
        instrument
        for instrument in session.scalars(stmt).all()
        if (
            (policy := get_source_policy(instrument.instrument_key)) is None
            or policy.preferred_provider == "oilpriceapi"
        )
    ]

    if not instruments:
        return {
            "provider": "oilpriceapi",
            "requested": 0,
            "stored": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "refreshedAt": refreshed_at.isoformat(),
            "instruments": [],
            "message": "No instruments configured with provider symbols.",
        }

    symbol_to_inst: dict[str, MarketInstrument] = {
        inst.provider_symbol: inst for inst in instruments if inst.provider_symbol
    }
    symbols_to_request = list(symbol_to_inst.keys())

    summary = {
        "provider": "oilpriceapi",
        "requested": len(symbols_to_request),
        "stored": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "refreshedAt": refreshed_at.isoformat(),
        "instruments": [],
    }

    try:
        raw_observations = await provider.get_latest(symbols_to_request)
    except Exception as exc:
        logger.error("Failed to fetch latest observations from provider: %s", exc)
        summary["failed"] = len(symbols_to_request)
        summary["error"] = str(exc)
        return summary

    for raw_obs in raw_observations:
        symbol = raw_obs.get("provider_symbol")
        inst = symbol_to_inst.get(symbol)
        if not inst:
            # Fallback by case-insensitive check
            for sym, i in symbol_to_inst.items():
                if sym.upper() == str(symbol).upper():
                    inst = i
                    break

        if not inst:
            summary["skipped"] += 1
            continue

        try:
            _, action = upsert_observation(session, inst, raw_obs)
            if action == "stored":
                summary["stored"] += 1
                summary["instruments"].append(inst.instrument_key)
            elif action == "updated":
                summary["updated"] += 1
                summary["instruments"].append(inst.instrument_key)
            else:
                summary["skipped"] += 1
        except Exception as exc:
            logger.error("Error upserting observation for %s: %s", inst.instrument_key, exc)
            summary["failed"] += 1

    session.commit()
    return summary


async def backfill_history(
    session: Session,
    instrument: MarketInstrument,
    provider: OilPriceAPIProvider | None = None,
    period: str = "past_month",
) -> dict[str, Any]:
    """Persists available historical records for an instrument from OilPriceAPI into Supabase."""
    policy = get_source_policy(instrument.instrument_key)
    if policy and policy.preferred_provider != "oilpriceapi":
        return {
            "instrument": instrument.instrument_key,
            "stored": 0,
            "status": "source_managed_elsewhere",
            "source": policy.source_label,
        }

    if not instrument.provider_symbol:
        return {"instrument": instrument.instrument_key, "stored": 0, "status": "unmapped"}

    if provider is None:
        provider = get_market_provider()

    try:
        history_points = await provider.get_history(instrument.provider_symbol, endpoint=period)
    except Exception as exc:
        logger.warning("History backfill failed for %s (%s): %s", instrument.instrument_key, period, exc)
        return {"instrument": instrument.instrument_key, "stored": 0, "status": "failed", "error": str(exc)}

    stored_count = 0
    updated_count = 0
    for pt in history_points:
        _, action = upsert_observation(session, instrument, pt)
        if action == "stored":
            stored_count += 1
        elif action == "updated":
            updated_count += 1

    session.commit()
    return {
        "instrument": instrument.instrument_key,
        "symbol": instrument.provider_symbol,
        "period": period,
        "pointsReceived": len(history_points),
        "stored": stored_count,
        "updated": updated_count,
        "status": "success",
    }
