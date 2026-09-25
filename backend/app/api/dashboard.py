from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.ai import AIAnalysis
from app.models.macro import MacroIndicator
from app.models.market import MarketInstrument, MarketObservation
from app.models.risk import DashboardContent, RiskRegisterEntry
from app.schemas.dashboard import (
    DashboardContentItem,
    DashboardSnapshotResponse,
    MacroIndicatorItem,
    RiskRegisterItem,
)
from app.schemas.market import InstrumentStatsResponse, ProductSpreadItem
from app.services.calculations import (
    calculate_all_product_spreads,
    calculate_instrument_stats,
)
from app.services.macro_ingestion import get_latest_macro_indicators
from app.services.source_resolution import resolve_observations, source_unavailable_reason

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/snapshot", response_model=DashboardSnapshotResponse)
def get_dashboard_snapshot(db: Annotated[Session, Depends(get_db)]) -> DashboardSnapshotResponse:
    now = datetime.now(timezone.utc)
    today_str = now.date().isoformat()

    # 1. Market instruments & observations
    instruments = db.scalars(
        select(MarketInstrument).where(MarketInstrument.enabled.is_(True)).order_by(MarketInstrument.id)
    ).all()

    market_stats: list[InstrumentStatsResponse] = []
    outliers: list[InstrumentStatsResponse] = []
    latest_by_instrument: dict[str, dict[str, Any]] = {}

    for inst in instruments:
        obs_stmt = (
            select(MarketObservation)
            .where(MarketObservation.instrument_id == inst.id)
            .order_by(MarketObservation.assessment_date.asc())
        )
        obs_records = db.scalars(obs_stmt).all()
        selected_records, policy, resolution_status = resolve_observations(inst, obs_records)
        obs_dicts = [
            {
                "assessment_date": obs.assessment_date.isoformat(),
                "value": float(obs.value),
                "unit": obs.unit,
                "provider_symbol": obs.provider_symbol,
                "provider": obs.provider,
                "benchmark_definition": obs.benchmark_definition,
                "display_name": inst.display_name,
            }
            for obs in selected_records
        ]

        # Provider metadata and accurate naming
        provider_name = inst.provider
        provider_sym = inst.provider_symbol
        unit_val = inst.unit
        source_ts_str = None
        retrieved_at_str = None
        unavailable_msg = None
        latest_obs_record = selected_records[-1] if selected_records else None

        if not provider_sym:
            bench_status = "unavailable"
            fresh_status = "unavailable"
            prov_display_name = inst.display_name
            unavailable_msg = "No approved automated source configured"
        else:
            if policy and policy.preferred_provider == "internal_excel":
                prov_display_name = policy.benchmark_definition
                bench_status = "confirmed"
            elif inst.instrument_key == "brent":
                prov_display_name = "ICE Brent Crude Futures"
                bench_status = "confirmed"
            elif inst.instrument_key == "wti":
                prov_display_name = "WTI Crude Oil Futures"
                bench_status = "confirmed"
            elif inst.instrument_key == "naphtha":
                prov_display_name = "Naphtha"
                bench_status = "test_proxy"
            elif inst.instrument_key == "gasoil":
                prov_display_name = "ICE Low Sulphur Gasoil Rotterdam"
                bench_status = "test_proxy"
            else:
                prov_display_name = inst.display_name
                bench_status = "confirmed"

            if latest_obs_record:
                unit_val = latest_obs_record.unit
                ref_ts = (
                    latest_obs_record.source_timestamp
                    or latest_obs_record.retrieved_at
                    or latest_obs_record.created_at
                )
                if ref_ts:
                    if ref_ts.tzinfo is None:
                        ref_ts = ref_ts.replace(tzinfo=timezone.utc)
                    age_sec = max(0.0, (now - ref_ts).total_seconds())
                    fresh_status = "fresh" if age_sec <= 36 * 3600 else "stale"
                else:
                    fresh_status = "fresh"

                if latest_obs_record.source_timestamp:
                    source_ts_str = latest_obs_record.source_timestamp.isoformat()
                if latest_obs_record.retrieved_at:
                    retrieved_at_str = latest_obs_record.retrieved_at.isoformat()
            else:
                fresh_status = "unavailable"

        stats = calculate_instrument_stats(obs_dicts, window_days=90, min_history_points=60)
        benchmark_definition = (
            latest_obs_record.benchmark_definition if latest_obs_record else (policy.benchmark_definition if policy else None)
        )
        preferred_unavailable = resolution_status == "preferred_unavailable"
        if preferred_unavailable:
            stats = {
                **stats,
                "current_value": None,
                "previous_value": None,
                "change": None,
                "percent_change": None,
                "mean_90": None,
                "std_dev_90": None,
                "z_score": None,
                "window_count": 0,
                "history_status": "source_unavailable",
                "latest_date": None,
                "latest_observation": None,
            }
        stat_item = InstrumentStatsResponse(
            instrument_id=inst.instrument_key,
            display_name=inst.display_name,
            current_value=stats["current_value"],
            previous_value=stats["previous_value"],
            change=stats["change"],
            percent_change=stats["percent_change"],
            mean_90=stats["mean_90"],
            std_dev_90=stats["std_dev_90"],
            z_score=stats["z_score"],
            window_count=stats["window_count"],
            history_status=stats.get("history_status", "valid"),
            latest_date=stats["latest_date"],
            unit=latest_obs_record.unit if latest_obs_record else unit_val,
            provider=(latest_obs_record.provider if latest_obs_record else (policy.preferred_provider if policy else provider_name)),
            provider_symbol=(latest_obs_record.provider_symbol if latest_obs_record else (policy.preferred_symbol if policy else provider_sym)),
            provider_display_name=prov_display_name,
            benchmark_status=bench_status,
            freshness_status=fresh_status,
            source_timestamp=source_ts_str,
            retrieved_at=retrieved_at_str,
            unavailable_reason=(source_unavailable_reason(policy) if preferred_unavailable else unavailable_msg),
            benchmark_definition=benchmark_definition,
        )
        market_stats.append(stat_item)

        if stats["z_score"] is not None and abs(stats["z_score"]) >= 2.0:
            outliers.append(stat_item)

        if stats.get("latest_observation"):
            latest_by_instrument[inst.instrument_key] = stats["latest_observation"]

    # 2. Product spreads
    spreads_data = calculate_all_product_spreads(latest_by_instrument)
    product_spreads = [
        ProductSpreadItem(
            instrument_id=item["instrument_id"],
            display_name=item["display_name"],
            date=item["date"],
            original_price=item["original_price"],
            original_unit=item["original_unit"],
            barrels_per_mt=item["barrels_per_mt"],
            converted_price=item["converted_price"],
            brent_price=item["brent_price"],
            spread=item["spread"],
            is_comparable=item["is_comparable"],
        )
        for item in spreads_data
    ]

    # 3. Macro indicators (from verified official publisher records in database)
    latest_macros = get_latest_macro_indicators(db)
    macro_items = [
        MacroIndicatorItem(
            id=m.id,
            indicator_key=m.indicator_key,
            display_name=m.display_name,
            value=m.value,
            unit=m.unit,
            reporting_period=m.reporting_period,
            source=m.source,
            source_url=m.source_url,
            published_at=m.published_at,
            retrieved_at=m.retrieved_at,
            status=m.status,
            freshness_status=m.freshness_status,
            metadata_json=m.metadata_json or {},
        )
        for m in latest_macros
    ]

    # 4. Risk register (simplified fields)
    risk_stmt = (
        select(RiskRegisterEntry)
        .where(RiskRegisterEntry.active.is_(True))
        .order_by(RiskRegisterEntry.display_order, RiskRegisterEntry.id)
    )
    risks = db.scalars(risk_stmt).all()
    risk_items = [
        RiskRegisterItem(
            id=r.id,
            risk_category=r.risk_category,
            materiality=r.materiality,
            trend=r.trend,
            risk_owner=r.risk_owner,
            display_order=r.display_order,
            active=r.active,
        )
        for r in risks
    ]

    # 5. Dashboard content
    content_stmt = (
        select(DashboardContent)
        .where(DashboardContent.active.is_(True))
        .order_by(DashboardContent.section_key, DashboardContent.display_order, DashboardContent.id)
    )
    contents = db.scalars(content_stmt).all()
    content_items = [
        DashboardContentItem(
            id=c.id,
            section_key=c.section_key,
            item_key=c.item_key,
            title=c.title,
            content=c.content,
            classification=c.classification,
            metadata_json=c.metadata_json or {},
            display_order=c.display_order,
            active=c.active,
        )
        for c in contents
    ]

    # 6. Latest AI analysis
    ai_stmt = (
        select(AIAnalysis)
        .where(
            AIAnalysis.analysis_type == "daily_dashboard_analysis",
            AIAnalysis.status == "completed",
            AIAnalysis.output_json.is_not(None),
        )
        .order_by(desc(AIAnalysis.generated_at), desc(AIAnalysis.id))
        .limit(1)
    )
    latest_ai = db.scalars(ai_stmt).first()
    ai_analysis_dict = latest_ai.output_json if (latest_ai and latest_ai.output_json) else None

    return DashboardSnapshotResponse(
        snapshot_date=today_str,
        generated_at=now.isoformat(),
        market_stats=market_stats,
        outliers=outliers,
        product_spreads=product_spreads,
        macro_indicators=macro_items,
        risk_register=risk_items,
        dashboard_content=content_items,
        ai_analysis=ai_analysis_dict,
    )
