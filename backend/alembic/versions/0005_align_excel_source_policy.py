"""Align canonical Excel-backed instrument metadata.

Revision ID: 0005_align_excel_source_policy
Revises: 0004_news_items
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0005_align_excel_source_policy"
down_revision: Union[str, None] = "0004_news_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    instruments = sa.table(
        "market_instruments",
        sa.column("instrument_key", sa.String()),
        sa.column("provider", sa.String()),
        sa.column("provider_symbol", sa.String()),
    )
    source_map = {
        "forcados": "PCABC00",
        "naphtha": "PAAAM00",
        "gasoil": "AAVJI00",
        "gasoline": "PGABM00",
        "jet": "PJAAV00",
    }
    connection = op.get_bind()
    for instrument_key, provider_symbol in source_map.items():
        connection.execute(
            sa.update(instruments)
            .where(instruments.c.instrument_key == instrument_key)
            .values(provider="internal_excel", provider_symbol=provider_symbol)
        )


def downgrade() -> None:
    instruments = sa.table(
        "market_instruments",
        sa.column("instrument_key", sa.String()),
        sa.column("provider", sa.String()),
        sa.column("provider_symbol", sa.String()),
    )
    previous_map = {
        "forcados": (None, None),
        "naphtha": ("oilpriceapi", "NAPHTHA_USD"),
        "gasoil": ("oilpriceapi", "GASOIL_USD"),
        "gasoline": (None, None),
        "jet": (None, None),
    }
    connection = op.get_bind()
    for instrument_key, (provider, provider_symbol) in previous_map.items():
        connection.execute(
            sa.update(instruments)
            .where(instruments.c.instrument_key == instrument_key)
            .values(provider=provider, provider_symbol=provider_symbol)
        )
