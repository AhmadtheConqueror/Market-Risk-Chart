from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.db.session import get_session_factory
from app.models.market import MarketInstrument, MarketObservation
from app.providers.market.oilpriceapi import OilPriceAPIProvider
from app.services.market_ingestion import backfill_history, ingest_latest_market_data


async def run_discovery() -> None:
    print("=" * 60)
    print("OILPRICEAPI CONTROLLED LIVE DISCOVERY")
    print("=" * 60)

    provider = OilPriceAPIProvider()
    if not provider.is_configured:
        from app.config import get_settings
        settings = get_settings()
        key = settings.oilpriceapi_key or settings.market_data_api_key
        provider = OilPriceAPIProvider(api_key=key, base_url=settings.market_data_base_url)

    if not provider.is_configured:
        print("ERROR: OilPriceAPI key is not configured.", file=sys.stderr)
        sys.exit(1)

    # 1. Test BRENT_CRUDE_USD
    print("\n--- Step 1: Testing BRENT_CRUDE_USD ---")
    brent_obs = await provider.get_latest(["BRENT_CRUDE_USD"])
    if not brent_obs:
        print("Failed to retrieve BRENT_CRUDE_USD!")
        sys.exit(1)
    b0 = brent_obs[0]
    print(f"Code: {b0['provider_symbol']}")
    print(f"Price: {b0['raw_value']} {b0['currency']} ({b0['raw_unit']})")
    print(f"Assessment Date: {b0['assessment_date']}")
    print(f"Source Timestamp: {b0['source_timestamp']}")

    # 2. Test WTI_USD
    print("\n--- Step 2: Testing WTI_USD ---")
    wti_obs = await provider.get_latest(["WTI_USD"])
    if not wti_obs:
        print("Failed to retrieve WTI_USD!")
        sys.exit(1)
    w0 = wti_obs[0]
    print(f"Code: {w0['provider_symbol']}")
    print(f"Price: {w0['raw_value']} {w0['currency']} ({w0['raw_unit']})")
    print(f"Assessment Date: {w0['assessment_date']}")
    print(f"Source Timestamp: {w0['source_timestamp']}")

    # 3. Discover Commodities Catalog
    print("\n--- Step 3: Fetching /v1/commodities catalog ---")
    commodities = await provider.get_commodities()
    print(f"Total commodities returned: {len(commodities)}")

    # Search for keywords relevant to our instruments
    search_terms = ["brent", "wti", "crude", "forcados", "naphtha", "gasoil", "diesel", "gasoline", "petrol", "jet", "kerosene"]
    matched_commodities: list[dict[str, Any]] = []

    print("\nCommodity candidates related to oil & products:")
    for c in commodities:
        code = str(c.get("code") or c.get("commodity_code") or "").upper()
        name = str(c.get("name") or c.get("commodity_name") or "")
        unit = str(c.get("unit") or "")
        combined = f"{code} {name}".lower()
        if any(term in combined for term in search_terms):
            matched_commodities.append(c)
            print(f"  • Code: {code:<25} | Name: {name:<35} | Unit: {unit}")

    # 4. Test Historical Endpoints for Entitlement
    print("\n--- Step 4: Testing Historical Entitlements for BRENT_CRUDE_USD ---")
    for endpoint in ["past_week", "past_month", "past_year"]:
        try:
            hist = await provider.get_history("BRENT_CRUDE_USD", endpoint=endpoint)
            print(f"  • Endpoint '{endpoint}': {len(hist)} data points returned.")
            if hist:
                print(f"    Earliest: {hist[0]['assessment_date']} | Latest: {hist[-1]['assessment_date']}")
        except Exception as exc:
            print(f"  • Endpoint '{endpoint}': Error -> {exc}")

    # 5. Connect to Supabase and update mappings
    print("\n--- Step 5: Updating Supabase market_instruments ---")
    factory = get_session_factory()
    with factory() as session:
        # Check current instruments in DB
        instruments = session.scalars(select(MarketInstrument)).all()
        for inst in instruments:
            if inst.instrument_key == "brent":
                inst.provider = "oilpriceapi"
                inst.provider_symbol = "BRENT_CRUDE_USD"
                print(f"  Mapped {inst.instrument_key} -> {inst.provider_symbol}")
            elif inst.instrument_key == "wti":
                inst.provider = "oilpriceapi"
                inst.provider_symbol = "WTI_USD"
                print(f"  Mapped {inst.instrument_key} -> {inst.provider_symbol}")

        session.commit()

        # 6. Ingest latest market data
        print("\n--- Step 6: Ingesting latest prices into Supabase ---")
        summary = await ingest_latest_market_data(session, provider=provider)
        print(f"Ingest Summary: {summary}")

        # 7. Backfill history into Supabase
        print("\n--- Step 7: Controlled historical backfill for Brent & WTI ---")
        brent_inst = session.scalars(select(MarketInstrument).where(MarketInstrument.instrument_key == "brent")).first()
        if brent_inst:
            res_brent = await backfill_history(session, brent_inst, provider=provider, period="past_month")
            print(f"  Brent backfill: {res_brent}")

        wti_inst = session.scalars(select(MarketInstrument).where(MarketInstrument.instrument_key == "wti")).first()
        if wti_inst:
            res_wti = await backfill_history(session, wti_inst, provider=provider, period="past_month")
            print(f"  WTI backfill: {res_wti}")

        # Count total stored observations
        obs_count = session.scalars(select(MarketObservation)).all()
        print(f"\nTotal observations now stored in Supabase: {len(obs_count)}")


if __name__ == "__main__":
    asyncio.run(run_discovery())
