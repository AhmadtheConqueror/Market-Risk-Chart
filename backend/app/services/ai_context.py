from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dashboard import get_dashboard_snapshot
from app.models.market import MarketInstrument, MarketObservation
from app.services.news_ingestion import get_recent_news


def build_dashboard_ai_context(db: Session) -> dict[str, Any]:
    """Build analysis context from verified server-side dashboard state.

    Browser context is intentionally not accepted here. Market history is added
    from the same normalized observation records used by dashboard calculations.
    """
    snapshot = get_dashboard_snapshot(db)
    payload = snapshot.model_dump(mode="json")
    payload.pop("ai_analysis", None)

    stats_by_key = {item["instrument_id"]: item for item in payload.get("market_stats", [])}
    instruments = db.scalars(
        select(MarketInstrument).where(MarketInstrument.enabled.is_(True)).order_by(MarketInstrument.id)
    ).all()

    market_context: list[dict[str, Any]] = []
    for instrument in instruments:
        stat = dict(stats_by_key.get(instrument.instrument_key, {}))
        observations = db.scalars(
            select(MarketObservation)
            .where(MarketObservation.instrument_id == instrument.id)
            .order_by(MarketObservation.assessment_date.asc())
        ).all()
        valid_dates = [record.assessment_date for record in observations]
        latest_date = max(valid_dates) if valid_dates else None
        start_date = latest_date - timedelta(days=29) if latest_date else None
        history = [
            {
                "assessment_date": record.assessment_date.isoformat(),
                "value": float(record.value),
                "unit": record.unit,
                "provider": record.provider,
                "provider_symbol": record.provider_symbol,
                "source_timestamp": record.source_timestamp.isoformat() if record.source_timestamp else None,
                "retrieved_at": record.retrieved_at.isoformat() if record.retrieved_at else None,
            }
            for record in observations
            if start_date is not None and start_date <= record.assessment_date <= latest_date
        ]
        stat["history_30d"] = history
        stat["canonical_instrument_key"] = instrument.instrument_key
        stat["source_record_count"] = len(observations)
        market_context.append(stat)

    payload["market_stats"] = market_context
    payload["news"] = [
        {
            "title": item.title,
            "source": item.source_name,
            "source_key": item.source_key,
            "published_at": item.published_at.isoformat(),
            "region": item.region,
            "topic": item.topic,
            "snippet": item.snippet,
            "url": item.url,
        }
        for item in get_recent_news(db, limit=20)
    ]
    payload["analysis_rules"] = {
        "market_values_are_backend_authoritative": True,
        "missing_values": "preserve null/unavailable exactly; never fill or interpolate",
        "history_window": "30 calendar days where available; 90-day statistics are in market_stats",
        "provider_identity": "Use provider_display_name and provider_symbol exactly as supplied",
        "source_timestamps_are_audit_metadata": True,
        "news_is_sourced_context_only": True,
        "news_copyright_rule": "Use supplied headlines/snippets and links only; never reconstruct full articles.",
        "news_attribution_rule": "Attribute material news claims to the supplied source and distinguish fact from interpretation.",
    }
    return payload
