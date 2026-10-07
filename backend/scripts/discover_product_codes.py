"""Controlled provider discovery for 6 OilPriceAPI product codes.

Run from the backend directory:
    python scripts/discover_product_codes.py

Records for each candidate:
  - Returned canonical code
  - Price
  - Unit
  - Timestamp
  - Entitlement/access (success vs HTTP error code)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import get_settings
from app.providers.market.oilpriceapi import OilPriceAPIError, OilPriceAPIProvider


# Candidate codes to probe: instrument_key → list of candidate codes to try
CANDIDATES: dict[str, list[str]] = {
    "brent":    ["BRENT_CRUDE_USD"],
    "wti":      ["WTI_USD"],
    "naphtha":  ["NAPHTHA_USD"],
    "gasoil":   ["GASOIL_USD"],
    # Gasoline: test both known candidates — use whichever the account supports
    "gasoline": ["GASOLINE_USD", "GASOLINE_RBOB_USD", "RBOB_USD"],
    "jet":      ["JET_FUEL_USD", "JET_USD", "KEROSENE_USD"],
}


async def probe_code(provider: OilPriceAPIProvider, code: str) -> dict:
    """Attempt to fetch a single code. Returns result dict regardless of success/failure."""
    try:
        results = await provider.get_latest([code])
        if not results:
            return {
                "code_requested": code,
                "status": "no_data",
                "canonical_code": None,
                "price": None,
                "unit": None,
                "timestamp": None,
                "error": "Empty response from provider",
            }
        r = results[0]
        return {
            "code_requested": code,
            "status": "ok",
            "canonical_code": r.get("provider_symbol"),
            "price": r.get("raw_value"),
            "unit": r.get("raw_unit"),
            "timestamp": str(r.get("assessment_date")),
            "source_timestamp": str(r.get("source_timestamp")),
            "error": None,
        }
    except OilPriceAPIError as exc:
        return {
            "code_requested": code,
            "status": f"http_error_{exc.status_code or 'unknown'}",
            "canonical_code": None,
            "price": None,
            "unit": None,
            "timestamp": None,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "code_requested": code,
            "status": "error",
            "canonical_code": None,
            "price": None,
            "unit": None,
            "timestamp": None,
            "error": str(exc),
        }


async def main() -> None:
    settings = get_settings()
    api_key = settings.oilpriceapi_key or settings.market_data_api_key
    if not api_key:
        print("ERROR: OILPRICEAPI_KEY is not set in .env", file=sys.stderr)
        sys.exit(1)

    provider = OilPriceAPIProvider(
        api_key=api_key,
        base_url=settings.market_data_base_url,
    )

    print("=" * 72)
    print("CONTROLLED PROVIDER DISCOVERY — OilPriceAPI")
    print("=" * 72)

    discovery_results: dict[str, dict] = {}

    for instrument_key, codes in CANDIDATES.items():
        print(f"\n>> {instrument_key.upper()}")
        best: dict | None = None
        for code in codes:
            result = await probe_code(provider, code)
            status_icon = "[OK]" if result["status"] == "ok" else "[--]"
            print(f"  {status_icon} {code:<28}  status={result['status']}")
            if result["status"] == "ok":
                print(f"      canonical_code : {result['canonical_code']}")
                print(f"      price          : {result['price']}")
                print(f"      unit           : {result['unit']}")
                print(f"      date           : {result['timestamp']}")
                if best is None:
                    best = result
            else:
                print(f"      error          : {result['error']}")
        discovery_results[instrument_key] = best or {"status": "unavailable", "code_requested": codes}

    # --- Summary table ---
    print("\n\n" + "=" * 72)
    print("DISCOVERY SUMMARY")
    print("=" * 72)
    print(f"{'Instrument':<12} {'Code':<28} {'Price':>10} {'Unit':<15} {'Status':<12}")
    print("-" * 72)
    for instrument_key, result in discovery_results.items():
        if result.get("status") == "ok":
            print(
                f"{instrument_key:<12} "
                f"{result['canonical_code']:<28} "
                f"{result['price']:>10.2f} "
                f"{result['unit']:<15} "
                f"{'direct' if instrument_key in ('brent', 'wti') else 'proxy'}"
            )
        else:
            print(
                f"{instrument_key:<12} "
                f"{'N/A':<28} "
                f"{'N/A':>10} "
                f"{'N/A':<15} "
                f"UNAVAILABLE"
            )
    print(f"\n  forcados         PCABC00                  N/A        USD/bbl        internal_excel")

    # --- Recommended source_policy configuration ---
    print("\n\n" + "=" * 72)
    print("RECOMMENDED source_resolution.py SOURCE_POLICIES")
    print("=" * 72)
    for instrument_key, result in discovery_results.items():
        if result.get("status") == "ok":
            canonical = result["canonical_code"]
            unit = result["unit"]
            benchmark_type = "direct" if instrument_key in ("brent", "wti") else "proxy"
            benchmark_status = "confirmed" if instrument_key in ("brent", "wti") else "proxy"
            print(
                f'  "{instrument_key}": SourcePolicy("oilpriceapi", "{canonical}", "OilPriceAPI", '
                f'"...", benchmark_status="{benchmark_status}", unit="{unit}"),'
            )
        else:
            print(f'  # "{instrument_key}": NOT ACCESSIBLE on this account')


if __name__ == "__main__":
    asyncio.run(main())
