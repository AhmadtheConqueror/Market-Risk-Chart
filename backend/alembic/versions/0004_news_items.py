"""Create normalized energy news storage."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_news_items"
down_revision: Union[str, None] = "0003_excel_source_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "news_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_key", sa.String(length=40), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("region", sa.String(length=30), nullable=False),
        sa.Column("topic", sa.String(length=40), nullable=False),
        sa.Column("relevance_status", sa.String(length=30), nullable=False, server_default="relevant"),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("url", name="uq_news_items_url"),
    )
    op.create_index("ix_news_items_source_key", "news_items", ["source_key"])
    op.create_index("ix_news_items_published_at", "news_items", ["published_at"])
    op.create_index("ix_news_items_region", "news_items", ["region"])
    op.create_index("ix_news_items_topic", "news_items", ["topic"])
    op.create_index("ix_news_items_region_published", "news_items", ["region", "published_at"])
    op.create_index("ix_news_items_topic_published", "news_items", ["topic", "published_at"])


def downgrade() -> None:
    op.drop_index("ix_news_items_topic_published", table_name="news_items")
    op.drop_index("ix_news_items_region_published", table_name="news_items")
    op.drop_index("ix_news_items_topic", table_name="news_items")
    op.drop_index("ix_news_items_region", table_name="news_items")
    op.drop_index("ix_news_items_published_at", table_name="news_items")
    op.drop_index("ix_news_items_source_key", table_name="news_items")
    op.drop_table("news_items")
