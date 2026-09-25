from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.models.macro import MacroIndicator
from app.models.market import MarketInstrument, MarketObservation
from app.models.risk import DashboardContent, RiskRegisterEntry


CANONICAL_INSTRUMENTS = [
    {
        "instrument_key": "brent",
        "display_name": "Dated Brent",
        "unit": "USD/bbl",
        "category": "crude",
        "provider": "oilpriceapi",
        "provider_symbol": "BRENT_CRUDE_USD",
    },
    {
        "instrument_key": "wti",
        "display_name": "WTI",
        "unit": "USD/bbl",
        "category": "crude",
        "provider": "oilpriceapi",
        "provider_symbol": "WTI_USD",
    },
    {
        "instrument_key": "forcados",
        "display_name": "Forcados",
        "unit": "USD/bbl",
        "category": "crude",
        "provider": "internal_excel",
        "provider_symbol": "PCABC00",
    },
    {
        "instrument_key": "naphtha",
        "display_name": "Naphtha Cargoes CIF NWE",
        "unit": "USD/mt",
        "category": "refined",
        "provider": "internal_excel",
        "provider_symbol": "PAAAM00",
    },
    {
        "instrument_key": "gasoil",
        "display_name": "Gasoil 0.1% Cargoes CIF NWE",
        "unit": "USD/mt",
        "category": "refined",
        "provider": "internal_excel",
        "provider_symbol": "AAVJI00",
    },
    {
        "instrument_key": "gasoline",
        "display_name": "Eurobob Non-Oxy Barges FOB Rdam",
        "unit": "USD/mt",
        "category": "refined",
        "provider": "internal_excel",
        "provider_symbol": "PGABM00",
    },
    {
        "instrument_key": "jet",
        "display_name": "Jet Aviation Fuel Cargoes CIF NWE",
        "unit": "USD/mt",
        "category": "refined",
        "provider": "internal_excel",
        "provider_symbol": "PJAAV00",
    },
]


def seed_canonical_instruments(session: Session) -> dict[str, MarketInstrument]:
    """Seeds the 7 canonical market instruments if they do not exist.

    Safe for both production/Supabase and local development.
    """
    instrument_map: dict[str, MarketInstrument] = {}
    for item in CANONICAL_INSTRUMENTS:
        existing = session.scalars(
            select(MarketInstrument).where(MarketInstrument.instrument_key == item["instrument_key"])
        ).first()
        if not existing:
            existing = MarketInstrument(
                instrument_key=item["instrument_key"],
                display_name=item["display_name"],
                unit=item["unit"],
                category=item["category"],
                provider=item["provider"],
                provider_symbol=item["provider_symbol"],
                enabled=True,
            )
            session.add(existing)
            session.flush()
        elif (
            existing.provider != item["provider"]
            or existing.provider_symbol != item["provider_symbol"]
        ):
            existing.provider = item["provider"]
            existing.provider_symbol = item["provider_symbol"]
        instrument_map[item["instrument_key"]] = existing

    session.commit()
    return instrument_map


def seed_development_demo_data(session: Session, instrument_map: dict[str, MarketInstrument]) -> None:
    """Explicit development-only test seed.

    All market observations are explicitly marked with provider='demo_dev_fixture'
    and provider_symbol='TEST_DEMO' to ensure they are never confused with live data.
    """
    now = datetime.now(timezone.utc)
    base_date = now.date()

    # Synthetic 90-day history for local dev testing only
    base_prices = {
        "brent": 73.50,
        "wti": 69.20,
        "forcados": 74.80,
        "naphtha": 625.00,
        "gasoil": 680.00,
        "gasoline": 710.00,
        "jet": 740.00,
    }

    for inst_key, inst in instrument_map.items():
        base_price = base_prices.get(inst_key, 70.0)
        unit = inst.unit

        for day_offset in range(90, -1, -1):
            obs_date = base_date - timedelta(days=day_offset)
            # deterministic slight variation for test statistics
            price = round(base_price + (math_offset := (day_offset % 7 - 3) * 0.4), 4)

            existing = session.scalars(
                select(MarketObservation).where(
                    MarketObservation.instrument_id == inst.id,
                    MarketObservation.assessment_date == obs_date,
                    MarketObservation.provider == "demo_dev_fixture",
                )
            ).first()

            if not existing:
                obs = MarketObservation(
                    instrument_id=inst.id,
                    assessment_date=obs_date,
                    value=price,
                    unit=unit,
                    provider="demo_dev_fixture",
                    provider_symbol="TEST_DEMO",
                    retrieved_at=now,
                    source_timestamp=now,
                )
                session.add(obs)

    # Simplified risk register entries
    sample_risks = [
        ("Crude Price Volatility", "Major", "increasing", "Head of Oil Trading", 1),
        ("Refined Product Crack Margins", "Moderate", "unchanged", "Refined Products Desk", 2),
        ("Counterparty Credit Exposure", "Moderate", "decreasing", "Credit Risk Officer", 3),
        ("Vessel Freight & Demurrage", "Low", "unchanged", "Operations Lead", 4),
        ("Sanctions & Compliance Exposure", "Catastrophic", "increasing", "Compliance Director", 5),
    ]

    for cat, mat, tr, owner, order in sample_risks:
        existing_risk = session.scalars(
            select(RiskRegisterEntry).where(RiskRegisterEntry.risk_category == cat)
        ).first()
        if not existing_risk:
            session.add(
                RiskRegisterEntry(
                    risk_category=cat,
                    materiality=mat,
                    trend=tr,
                    risk_owner=owner,
                    display_order=order,
                    active=True,
                )
            )

    # Illustrative macro indicators
    sample_macros = [
        ("DXY", "US Dollar Index", 102.45, "Index", "Daily", "Illustrative Fixture", None),
        ("US10Y", "US 10-Year Treasury Yield", 4.12, "%", "Daily", "Illustrative Fixture", None),
        ("BRENT_1M_SPREAD", "Brent 1M/2M Calendar Spread", 0.45, "USD/bbl", "Daily", "Illustrative Fixture", None),
    ]

    for key, name, val, unit, period, src, url in sample_macros:
        existing_macro = session.scalars(
            select(MacroIndicator).where(MacroIndicator.indicator_key == key)
        ).first()
        if not existing_macro:
            session.add(
                MacroIndicator(
                    indicator_key=key,
                    display_name=name,
                    value=val,
                    unit=unit,
                    reporting_period=period,
                    source=src,
                    source_url=url,
                    retrieved_at=now,
                )
            )

    # Illustrative dashboard content
    sample_content = [
        ("market_overview", "daily_summary", "Crude Market Briefing", "Brent trading in stable range pending OPEC+ review.", "info", 1),
        ("risk_advisor", "top_threat", "Geopolitical Watch", "Red Sea route disruptions continue to impact shipping.", "warning", 1),
    ]

    for sec, item, title, text_val, classification, order in sample_content:
        existing_content = session.scalars(
            select(DashboardContent).where(
                DashboardContent.section_key == sec,
                DashboardContent.item_key == item,
            )
        ).first()
        if not existing_content:
            session.add(
                DashboardContent(
                    section_key=sec,
                    item_key=item,
                    title=title,
                    content=text_val,
                    classification=classification,
                    metadata_json={"source": "development_fixture"},
                    display_order=order,
                    active=True,
                )
            )

    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed database for Daily Oil Trading Risk Dashboard")
    parser.add_argument(
        "--include-dev-demo",
        action="store_true",
        help="Explicitly populate development-only fixture observations and sample macro indicators.",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.database_url:
        print("DATABASE_URL is not set. Cannot run database seed.", file=sys.stderr)
        sys.exit(1)

    factory = get_session_factory()
    with factory() as session:
        print("Seeding canonical market instruments (brent, wti, forcados, naphtha, gasoil, gasoline, jet)...")
        inst_map = seed_canonical_instruments(session)
        print(f"Successfully verified/seeded {len(inst_map)} canonical instruments.")

        if args.include_dev_demo:
            print("Explicit --include-dev-demo specified. Seeding development-only fixture data...")
            seed_development_demo_data(session, inst_map)
            print("Development demo fixture seeded successfully.")
        else:
            print("Market observations left empty (awaiting live provider integration).")


if __name__ == "__main__":
    main()
