"""Separate Platts historical assessments and import provenance."""
from alembic import op
import sqlalchemy as sa
revision = "0008_historical_market"
down_revision = "0007_calendar_events"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("historical_market_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_key", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("provider_symbol", sa.String(100), nullable=False),
        sa.Column("benchmark_definition", sa.String(200), nullable=False),
        sa.Column("assessment_date", sa.Date(), nullable=False),
        sa.Column("native_value", sa.Numeric(20,8), nullable=False),
        sa.Column("native_unit", sa.String(40), nullable=False),
        sa.Column("converted_value", sa.Numeric(20,8), nullable=False),
        sa.Column("conversion_factor", sa.Numeric(12,6), nullable=True),
        sa.Column("workbook_source", sa.String(255), nullable=False),
        sa.Column("workbook_sha256", sa.String(64), nullable=False),
        sa.Column("worksheet", sa.String(100), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("instrument_key", "provider", "provider_symbol", "assessment_date", name="uq_historical_source_date"))
    op.create_index("ix_historical_instrument_date", "historical_market_observations", ["instrument_key", "assessment_date"])


def downgrade():
    op.drop_index("ix_historical_instrument_date", table_name="historical_market_observations")
    op.drop_table("historical_market_observations")
