"""0002_macro_indicators_history

Revision ID: 0002_macro_indicators_history
Revises: 0001_initial_schema
Create Date: 2026-09-24 14:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_macro_indicators_history"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop old single-column unique constraint
    op.drop_constraint("uq_macro_indicators_indicator_key", "macro_indicators", type_="unique")

    # 2. Add new columns
    op.add_column("macro_indicators", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "macro_indicators",
        sa.Column("status", sa.String(length=40), nullable=False, server_default="published"),
    )
    op.add_column("macro_indicators", sa.Column("metadata_json", sa.JSON(), nullable=True))

    # 3. Add composite unique constraint for historical tracking
    op.create_unique_constraint(
        "uq_macro_indicators_key_period_source",
        "macro_indicators",
        ["indicator_key", "reporting_period", "source"],
    )

    # 4. Add helper indexes
    op.create_index("ix_macro_indicators_key", "macro_indicators", ["indicator_key"], unique=False)
    op.create_index(
        "ix_macro_indicators_key_period",
        "macro_indicators",
        ["indicator_key", "reporting_period"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_macro_indicators_key_period", table_name="macro_indicators")
    op.drop_index("ix_macro_indicators_key", table_name="macro_indicators")
    op.drop_constraint("uq_macro_indicators_key_period_source", "macro_indicators", type_="unique")
    op.drop_column("macro_indicators", "metadata_json")
    op.drop_column("macro_indicators", "status")
    op.drop_column("macro_indicators", "published_at")
    op.create_unique_constraint(
        "uq_macro_indicators_indicator_key",
        "macro_indicators",
        ["indicator_key"],
    )
