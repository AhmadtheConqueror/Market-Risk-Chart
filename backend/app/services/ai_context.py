from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dashboard import get_dashboard_snapshot
from app.models.market import MarketInstrument, MarketObservation
from app.services.calendar_ingestion import get_calendar_events_query
from app.services.news_ingestion import get_recent_news
from app.services.source_resolution import get_source_policy
from app.services.macro_ingestion import macro_geography


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
        policy = get_source_policy(instrument.instrument_key)
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

        # Enrich with source policy metadata so Gemini can correctly attribute
        # prices and avoid describing proxy API series as physical assessments.
        if policy:
            stat["source_provider"] = policy.preferred_provider
            stat["source_symbol"] = policy.preferred_symbol
            stat["benchmark_name"] = policy.benchmark_definition
            stat["benchmark_status"] = policy.benchmark_status  # "confirmed" | "proxy"
            stat["canonical_unit"] = policy.canonical_unit       # "barrel" | "metric_ton" | "tonne" | "gallon"
            stat["source_label"] = policy.source_label
        else:
            stat["source_provider"] = instrument.provider
            stat["source_symbol"] = instrument.provider_symbol
            stat["benchmark_name"] = instrument.display_name
            stat["benchmark_status"] = "unknown"
            stat["canonical_unit"] = instrument.unit
            stat["source_label"] = instrument.provider

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
    payload["macro"] = {"nigeria": [], "usa": [], "global": []}
    for item in payload.get("macro_indicators", []):
        geography = macro_geography(item["indicator_key"])
        payload["macro"][geography].append({
            "geography": geography, "indicator": item["indicator_key"],
            "value": item["value"], "unit": item["unit"],
            "reporting_period": item["reporting_period"], "source": item["source"],
            "source_url": item["source_url"], "freshness": item["freshness_status"],
            "published_at": item["published_at"], "retrieved_at": item["retrieved_at"],
            "metadata": item["metadata_json"],
        })

    today_dt = date.today()
    end_dt = today_dt + timedelta(days=14)
    cal_events = get_calendar_events_query(
        session=db,
        start_date=today_dt,
        end_date=end_dt,
        active=True,
        include_unscheduled=False,
    )
    payload["upcoming_calendar_events"] = [
        {
            "event_date": e.event_date.isoformat() if e.event_date else None,
            "title": e.title,
            "category": e.category,
            "region": e.region,
            "impact_level": e.impact_level,
            "source_name": e.source_name,
        }
        for e in cal_events
    ]

    payload["analysis_rules"] = {
        "macro_values_are_verified_backend_observations": True,
        "macro_forecasts": "Preserve reference year, edition and metric definition; never fabricate missing releases",
        "market_values_are_backend_authoritative": True,
        "missing_values": "preserve null/unavailable exactly; never fill or interpolate",
        "history_window": "30 calendar days where available; 90-day statistics are in market_stats",
        "provider_identity": "Use provider_display_name and provider_symbol exactly as supplied",
        "source_timestamps_are_audit_metadata": True,
        "news_is_sourced_context_only": True,
        "news_copyright_rule": "Use supplied headlines/snippets and links only; never reconstruct full articles.",
        "news_attribution_rule": "Attribute material news claims to the supplied source and distinguish fact from interpretation.",
        "proxy_disclosure_rule": (
            "Instruments with benchmark_status='proxy' are generic API market series, "
            "NOT the original physical FOB assessments. "
            "Do NOT describe NAPHTHA_USD as 'Naphtha FOB Rdam Barge', "
            "GASOIL_USD as 'Gasoil 0.1%S FOB Med Cargo', "
            "GASOLINE_USD as 'Gasoline Prem Unleaded 10ppmS FOB ARA', or "
            "JET_FUEL_USD as 'Jet FOB NWE Cargo'. "
            "Use the supplied benchmark_name field verbatim. "
            "Brent, WTI, and Forcados remain confirmed/direct benchmarks."
        ),
        "unit_routing_note": (
            "Gallon-based instruments (gasoline, jet) have been converted to USD/bbl via x42. "
            "MT-based instruments (naphtha, gasoil) via approved bbl/mt factors. "
            "Never mix these conversion paths."
        ),
    }
    return payload
