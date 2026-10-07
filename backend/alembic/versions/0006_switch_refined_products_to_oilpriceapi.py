"""Switch naphtha, gasoil, gasoline, jet from internal_excel to OilPriceAPI proxy series.

Revision ID: 0006_switch_refined_products_to_oilpriceapi
Revises: 0005_align_excel_source_policy

Discovery confirmation (2026-09-30):
  NAPHTHA_USD  → unit: metric_ton,  price: ~797  → proxy
  GASOIL_USD   → unit: tonne,       price: ~1464 → proxy
  GASOLINE_USD → unit: gallon,      price: ~3.31 → proxy
  JET_FUEL_USD → unit: gallon,      price: ~4.35 → proxy

IMPORTANT:
  - Old Excel physical-assessment observations are PRESERVED (not deleted).
    The unique constraint (instrument_id, provider, provider_symbol, assessment_date)
    prevents them from interfering with the new API series.
  - Forcados remains internal_excel / PCABC00 (unchanged).
  - Display names are updated to reflect proxy status accurately.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0006_refined_to_oilpriceapi"
down_revision: Union[str, None] = "0005_align_excel_source_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    instruments = sa.table(
        "market_instruments",
        sa.column("instrument_key", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("provider", sa.String()),
        sa.column("provider_symbol", sa.String()),
        sa.column("unit", sa.String()),
    )
    connection = op.get_bind()

    # naphtha: switch to OilPriceAPI proxy; unit is USD/metric_ton from provider
    connection.execute(
        sa.update(instruments)
        .where(instruments.c.instrument_key == "naphtha")
        .values(
            provider="oilpriceapi",
            provider_symbol="NAPHTHA_USD",
            display_name="Naphtha — API market proxy",
            unit="USD/mt",
        )
    )

    # gasoil: switch to OilPriceAPI proxy; unit is USD/tonne from provider
    connection.execute(
        sa.update(instruments)
        .where(instruments.c.instrument_key == "gasoil")
        .values(
            provider="oilpriceapi",
            provider_symbol="GASOIL_USD",
            display_name="ICE Low Sulphur Gasoil — API proxy",
            unit="USD/mt",
        )
    )

    # gasoline: switch to OilPriceAPI proxy; unit is USD/gallon from provider
    connection.execute(
        sa.update(instruments)
        .where(instruments.c.instrument_key == "gasoline")
        .values(
            provider="oilpriceapi",
            provider_symbol="GASOLINE_USD",
            display_name="RBOB Gasoline — API proxy",
            unit="USD/gal",
        )
    )

    # jet: switch to OilPriceAPI proxy; unit is USD/gallon from provider
    connection.execute(
        sa.update(instruments)
        .where(instruments.c.instrument_key == "jet")
        .values(
            provider="oilpriceapi",
            provider_symbol="JET_FUEL_USD",
            display_name="Jet Fuel — API proxy",
            unit="USD/gal",
        )
    )


def downgrade() -> None:
    instruments = sa.table(
        "market_instruments",
        sa.column("instrument_key", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("provider", sa.String()),
        sa.column("provider_symbol", sa.String()),
        sa.column("unit", sa.String()),
    )
    connection = op.get_bind()

    # Restore Excel-backed physical assessment configurations
    revert_map = {
        "naphtha": ("internal_excel", "PAAAM00", "Naphtha Cargoes CIF NWE", "USD/mt"),
        "gasoil": ("internal_excel", "AAVJI00", "Gasoil 0.1% Cargoes CIF NWE", "USD/mt"),
        "gasoline": ("internal_excel", "PGABM00", "Eurobob Non-Oxy Barges FOB Rdam", "USD/mt"),
        "jet": ("internal_excel", "PJAAV00", "Jet Aviation Fuel Cargoes CIF NWE", "USD/mt"),
    }
    for key, (provider, symbol, display, unit) in revert_map.items():
        connection.execute(
            sa.update(instruments)
            .where(instruments.c.instrument_key == key)
            .values(provider=provider, provider_symbol=symbol, display_name=display, unit=unit)
        )
