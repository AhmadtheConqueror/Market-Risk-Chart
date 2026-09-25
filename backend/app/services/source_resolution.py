from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.models.market import MarketInstrument, MarketObservation


@dataclass(frozen=True)
class SourcePolicy:
    preferred_provider: str
    preferred_symbol: str
    source_label: str
    benchmark_definition: str


SOURCE_POLICIES: dict[str, SourcePolicy] = {
    "brent": SourcePolicy("oilpriceapi", "BRENT_CRUDE_USD", "OilPriceAPI", "ICE Brent Crude Futures"),
    "wti": SourcePolicy("oilpriceapi", "WTI_USD", "OilPriceAPI", "WTI Crude Oil Futures"),
    "forcados": SourcePolicy("internal_excel", "PCABC00", "Internal market workbook", "Forcados FOB Nigeria physical assessment"),
    "naphtha": SourcePolicy("internal_excel", "PAAAM00", "Internal market workbook", "Naphtha FOB Rdam Barge physical assessment"),
    "gasoil": SourcePolicy("internal_excel", "AAVJI00", "Internal market workbook", "Gasoil 0.1%S FOB Med Cargo physical assessment"),
    "gasoline": SourcePolicy("internal_excel", "PGABM00", "Internal market workbook", "Gasoline Prem Unleaded 10ppmS FOB AR Barge physical assessment"),
    "jet": SourcePolicy("internal_excel", "PJAAV00", "Internal market workbook", "Jet FOB NWE Cargo physical assessment"),
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
