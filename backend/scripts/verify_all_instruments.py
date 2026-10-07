"""Controlled live refresh: ingest latest data for all 7 instruments and produce verification report."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.config import get_settings
from app.db.session import get_session_factory
from app.models.market import MarketInstrument, MarketObservation
from app.providers.market.oilpriceapi import OilPriceAPIProvider, OilPriceAPIError
from app.services.market_ingestion import ingest_latest_market_data
from app.services.source_resolution import get_source_policy


async def main() -> None:
    settings = get_settings()
    api_key = settings.oilpriceapi_key or settings.market_data_api_key
    if not api_key:
        print("ERROR: OILPRICEAPI_KEY not set.", file=sys.stderr)
        sys.exit(1)

    provider = OilPriceAPIProvider(api_key=api_key, base_url=settings.market_data_base_url)
    factory = get_session_factory()

    print("=" * 72)
    print("CONTROLLED LIVE REFRESH - ALL 7 INSTRUMENTS")
    print("=" * 72)

    with factory() as session:
        # Ingest all 6 OilPriceAPI instruments in one multi-code call
        summary = await ingest_latest_market_data(session, provider=provider)
        print(f"\nRefresh summary: {summary}")

        # Verification report
        print("\n" + "=" * 72)
        print("VERIFICATION REPORT")
        print("=" * 72)
        print(f"{'Instrument':<12} {'Code':<24} {'Price':>10} {'Unit':<14} {'Date':<12} {'Provider':<16} {'Class':<10}")
        print("-" * 88)

        instruments = session.scalars(
            select(MarketInstrument).where(MarketInstrument.enabled.is_(True)).order_by(MarketInstrument.id)
        ).all()

        for inst in instruments:
            policy = get_source_policy(inst.instrument_key)

            # Get latest observation for this instrument from its preferred source
            if policy:
                latest_obs = session.scalars(
                    select(MarketObservation)
                    .where(
                        MarketObservation.instrument_id == inst.id,
                        MarketObservation.provider == policy.preferred_provider,
                        MarketObservation.provider_symbol.ilike(policy.preferred_symbol),
                    )
                    .order_by(MarketObservation.assessment_date.desc())
                    .limit(1)
                ).first()
            else:
                latest_obs = session.scalars(
                    select(MarketObservation)
                    .where(MarketObservation.instrument_id == inst.id)
                    .order_by(MarketObservation.assessment_date.desc())
                    .limit(1)
                ).first()

            if latest_obs:
                bench_class = (policy.benchmark_status if policy else "unknown").upper()
                print(
                    f"{inst.instrument_key:<12} "
                    f"{latest_obs.provider_symbol:<24} "
                    f"{float(latest_obs.value):>10.2f} "
                    f"{latest_obs.unit:<14} "
                    f"{str(latest_obs.assessment_date):<12} "
                    f"{latest_obs.provider:<16} "
                    f"{bench_class:<10}"
                )
            else:
                source = policy.source_label if policy else "unknown"
                expected_sym = policy.preferred_symbol if policy else inst.provider_symbol or "N/A"
                print(
                    f"{inst.instrument_key:<12} "
                    f"{expected_sym:<24} "
                    f"{'N/A':>10} "
                    f"{'N/A':<14} "
                    f"{'N/A':<12} "
                    f"{source:<16} "
                    f"{'NO DATA':<10}"
                )

        print("\nLegend: CONFIRMED = direct live benchmark, PROXY = generic API series")
        print("Forcados (internal_excel) requires manual Excel upload.")


if __name__ == "__main__":
    asyncio.run(main())
