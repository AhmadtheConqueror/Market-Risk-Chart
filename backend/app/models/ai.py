from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    analyses: Mapped[list[AIAnalysis]] = relationship(back_populates="market_snapshot")


# Backwards compatibility alias
DashboardSnapshot = MarketSnapshot


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    market_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("market_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    input_context_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    market_snapshot: Mapped[MarketSnapshot | None] = relationship(back_populates="analyses")
