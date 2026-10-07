from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.models.market import MarketInstrument, MarketObservation


@dataclass(frozen=True)
class SourcePolicy:
    preferred_provider: str
    preferred_symbol: str
    source_label: str
    benchmark_definition: str
    # "confirmed" for direct benchmarks (Brent, WTI, Forcados)
    # "proxy"     for API generic series (Naphtha, Gasoil, Gasoline, Jet)
    benchmark_status: str = "confirmed"
    # Canonical unit string as returned by the provider (barrel, metric_ton, tonne, gallon)
    canonical_unit: str = "barrel"


SOURCE_POLICIES: dict[str, SourcePolicy] = {
    # ── Direct / confirmed benchmarks ──────────────────────────────────────────
    "brent": SourcePolicy(
        "oilpriceapi", "BRENT_CRUDE_USD",
        "OilPriceAPI",
        "ICE Brent Crude Futures",
        benchmark_status="confirmed",
        canonical_unit="barrel",
    ),
    "wti": SourcePolicy(
        "oilpriceapi", "WTI_USD",
        "OilPriceAPI",
        "WTI Crude Oil Futures",
        benchmark_status="confirmed",
        canonical_unit="barrel",
    ),
    "forcados": SourcePolicy(
        "internal_excel", "PCABC00",
        "Internal market workbook",
        "Forcados FOB Nigeria",
        benchmark_status="confirmed",
        canonical_unit="barrel",
    ),

    # ── API proxy series (switched from Excel physical assessments) ─────────────
    # Discovery confirmed 2026-09-30: all four codes accessible on this account.
    # Units returned by provider:
    #   NAPHTHA_USD  → metric_ton  (USD/metric ton: use ÷ 8.90 bbl/mt for spread)
    #   GASOIL_USD   → tonne       (USD/tonne:      use ÷ 7.44 bbl/mt for spread)
    #   GASOLINE_USD → gallon      (USD/gallon:     use × 42  gal/bbl for spread)
    #   JET_FUEL_USD → gallon      (USD/gallon:     use × 42  gal/bbl for spread)
    "naphtha": SourcePolicy(
        "oilpriceapi", "NAPHTHA_USD",
        "OilPriceAPI",
        "Naphtha — API market proxy",
        benchmark_status="proxy",
        canonical_unit="metric_ton",
    ),
    "gasoil": SourcePolicy(
        "oilpriceapi", "GASOIL_USD",
        "OilPriceAPI",
        "ICE Low Sulphur Gasoil — API proxy",
        benchmark_status="proxy",
        canonical_unit="tonne",
    ),
    "gasoline": SourcePolicy(
        "oilpriceapi", "GASOLINE_USD",
        "OilPriceAPI",
        "RBOB Gasoline — API proxy",
        benchmark_status="proxy",
        canonical_unit="gallon",
    ),
    "jet": SourcePolicy(
        "oilpriceapi", "JET_FUEL_USD",
        "OilPriceAPI",
        "Jet Fuel — API proxy",
        benchmark_status="proxy",
        canonical_unit="gallon",
    ),
}


def get_source_policy(instrument_key: str) -> SourcePolicy | None:
    return SOURCE_POLICIES.get(instrument_key)


def resolve_observations(
    instrument: MarketInstrument,
    observations: Iterable[MarketObservation],
) -> tuple[list[MarketObservation], SourcePolicy | None, str]:
    """Select exactly one configured source series; never cross-source merge."""
    records = list(observations)
    policy = get_source_policy(instrument.instrument_key)
    if policy:
        selected = [
            obs for obs in records
            if obs.provider == policy.preferred_provider
            and obs.provider_symbol.upper() == policy.preferred_symbol.upper()
        ]
        if selected:
            return selected, policy, "preferred_available"

        # Test fixtures are explicitly allowed to keep the deterministic suite
        # independent of live or uploaded source records.
        fixtures = [obs for obs in records if obs.provider.startswith("test_") or obs.provider == "demo_dev_fixture"]
        if fixtures:
            return fixtures, policy, "test_fixture"
        return [], policy, "preferred_unavailable"

    return records, policy, "instrument_source"


def source_unavailable_reason(policy: SourcePolicy | None) -> str:
    if not policy:
        return "No source policy is configured for this instrument."
    return f"Preferred source unavailable: {policy.source_label} ({policy.preferred_symbol}); fallback is disabled."
