"""0001_initial_schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-24 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. market_instruments
    op.create_table(
        "market_instruments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instrument_key", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("provider_symbol", sa.String(length=100), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False, server_default="market"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_market_instruments"),
        sa.UniqueConstraint("instrument_key", name="uq_market_instruments_instrument_key"),
    )

    # 2. market_observations
    op.create_table(
        "market_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("assessment_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("provider_symbol", sa.String(length=100), nullable=False),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["market_instruments.id"],
            name="fk_market_observations_instrument_id_market_instruments",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_market_observations"),
        sa.UniqueConstraint(
            "instrument_id",
            "provider",
            "provider_symbol",
            "assessment_date",
            name="uq_market_observation_source_date",
        ),
    )
    op.create_index(
        "ix_market_observation_instrument_date",
        "market_observations",
        ["instrument_id", "assessment_date"],
        unique=False,
    )

    # 3. market_snapshots
    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_market_snapshots"),
    )
    op.create_index(
        "ix_market_snapshots_snapshot_date",
        "market_snapshots",
        ["snapshot_date"],
        unique=False,
    )

    # 4. ai_analyses
    op.create_table(
        "ai_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_type", sa.String(length=80), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("market_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("input_context_json", sa.JSON(), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["market_snapshot_id"],
            ["market_snapshots.id"],
            name="fk_ai_analyses_market_snapshot_id_market_snapshots",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_analyses"),
    )
    op.create_index(
        "ix_ai_analyses_analysis_type",
        "ai_analyses",
        ["analysis_type"],
        unique=False,
    )

    # 5. macro_indicators
    op.create_table(
        "macro_indicators",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("indicator_key", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("value", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("reporting_period", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=160), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_macro_indicators"),
        sa.UniqueConstraint("indicator_key", name="uq_macro_indicators_indicator_key"),
    )

    # 6. risk_register (simplified)
    op.create_table(
        "risk_register",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("risk_category", sa.String(length=180), nullable=False),
        sa.Column("materiality", sa.String(length=30), nullable=False),
        sa.Column("trend", sa.String(length=30), nullable=False),
        sa.Column("risk_owner", sa.String(length=120), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "materiality IN ('Low', 'Moderate', 'Major', 'Catastrophic')",
            name="ck_risk_register_materiality_allowed",
        ),
        sa.CheckConstraint(
            "trend IN ('increasing', 'unchanged', 'decreasing')",
            name="ck_risk_register_trend_allowed",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_risk_register"),
    )

    # 7. dashboard_content
    op.create_table(
        "dashboard_content",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("section_key", sa.String(length=80), nullable=False),
        sa.Column("item_key", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(length=80), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_dashboard_content"),
    )
    op.create_index(
        "ix_dashboard_content_section_key",
        "dashboard_content",
        ["section_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("dashboard_content")
    op.drop_table("risk_register")
    op.drop_table("macro_indicators")
    op.drop_table("ai_analyses")
    op.drop_table("market_snapshots")
    op.drop_table("market_observations")
    op.drop_table("market_instruments")
