from __future__ import annotations

import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.providers.market.oilpriceapi import OilPriceAPIProvider


async def probe_candidates():
    from app.providers.market.factory import get_market_provider
    provider = get_market_provider("oilpriceapi")
    candidates = [
        "NAPHTHA_USD",
        "GASOIL_USD",
        "GASOLINE_USD",
        "GASOLINE_RBOB_USD",
        "JET_FUEL_USD",
        "SINGAPORE_JET_KEROSENE_USD",
    ]

    print("Probing candidate product codes with OilPriceAPI...")
    for code in candidates:
        try:
            res = await provider.get_latest([code])
            if res:
                item = res[0]
                print(f"[SUCCESS] {code:<25}: price={item['raw_value']}, unit={item['raw_unit']}, date={item['assessment_date']}")
            else:
                print(f"[EMPTY]   {code:<25}: No observation returned")
        except Exception as exc:
            print(f"[FAILED]  {code:<25}: Error -> {exc}")

if __name__ == "__main__":
    asyncio.run(probe_candidates())
