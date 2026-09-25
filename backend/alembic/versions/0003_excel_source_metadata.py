"""Add benchmark definition metadata to market observations."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_excel_source_metadata"
down_revision: Union[str, None] = "0002_macro_indicators_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("market_observations", sa.Column("benchmark_definition", sa.String(length=240), nullable=True))


def downgrade() -> None:
    op.drop_column("market_observations", "benchmark_definition")
