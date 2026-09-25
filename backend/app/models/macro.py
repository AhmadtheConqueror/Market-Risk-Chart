from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Index, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MacroIndicator(Base):
    __tablename__ = "macro_indicators"
    __table_args__ = (
        UniqueConstraint(
            "indicator_key",
            "reporting_period",
            "source",
            name="uq_macro_indicators_key_period_source",
        ),
        Index("ix_macro_indicators_key_period", "indicator_key", "reporting_period"),
        Index("ix_macro_indicators_key", "indicator_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    indicator_key: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    reporting_period: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(160), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="published", server_default="published")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

