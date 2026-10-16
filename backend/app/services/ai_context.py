from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.api.dashboard import get_dashboard_snapshot
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

    from app.services.historical_market import RISK_SCORING_KEYS
    # Additional monitored series are not new weighted Risk Advisor inputs.
    payload["market_stats"] = [s for s in payload.get("market_stats", []) if s["instrument_id"] in RISK_SCORING_KEYS]
    payload["outliers"] = [s for s in payload.get("outliers", []) if s["instrument_id"] in RISK_SCORING_KEYS]
    stats_by_key = {item["instrument_id"]: item for item in payload.get("market_stats", [])}
    from app.services.historical_market import load_historical_series
    from app.services.official_market import historical_observation
    grouped = load_historical_series(db)
    market_context: list[dict[str, Any]] = []
    for key, stat_item in stats_by_key.items():
        stat = dict(stat_item)
        stat.pop("history", None)  # Preserve the existing bounded 30D analysis context below.
        policy = get_source_policy(key)
        observations = grouped[key]
        latest_date = observations[-1].assessment_date if observations else None
        start_date = latest_date - timedelta(days=29) if latest_date else None
        stat["history_30d"] = [
            {"assessment_date": row.assessment_date.isoformat(), "value": float(row.native_value),
             "unit": row.native_unit, "provider": row.provider, "provider_symbol": row.provider_symbol,
             "source_timestamp": historical_observation(row).source_timestamp,
             "retrieved_at": row.imported_at.isoformat()}
            for row in observations if start_date and row.assessment_date >= start_date]
        stat.update(canonical_instrument_key=key, source_record_count=len(observations),
            source_provider=policy.preferred_provider, source_symbol=policy.preferred_symbol,
            benchmark_name=policy.benchmark_definition, benchmark_status=stat["benchmark_status"],
            canonical_unit=policy.canonical_unit, source_label=policy.source_label)
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
