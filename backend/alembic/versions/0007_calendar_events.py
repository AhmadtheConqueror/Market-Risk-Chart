"""Create calendar_events table.

Revision ID: 0007_calendar_events
Revises: 0006_refined_to_oilpriceapi
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0007_calendar_events"
down_revision: Union[str, None] = "0006_refined_to_oilpriceapi"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("external_id", sa.String(length=120), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("legacy_date", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("region", sa.String(length=50), nullable=False, server_default="Global"),
        sa.Column("country", sa.String(length=80), nullable=True),
        sa.Column("impact_level", sa.String(length=20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_name", sa.String(length=150), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("source_type", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_calendar_events_external_id", "calendar_events", ["external_id"])
    op.create_index("ix_calendar_events_provider", "calendar_events", ["provider"])
    op.create_index("ix_calendar_events_event_date", "calendar_events", ["event_date"])
    op.create_index("ix_calendar_events_category", "calendar_events", ["category"])
    op.create_index("ix_calendar_events_active", "calendar_events", ["active"])
    op.create_index("ix_calendar_events_provider_external", "calendar_events", ["provider", "external_id"])
    op.create_index("ix_calendar_events_date_category", "calendar_events", ["event_date", "category"])


def downgrade() -> None:
    op.drop_table("calendar_events")
