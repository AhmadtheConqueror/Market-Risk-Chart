from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketInstrument(Base):
    __tablename__ = "market_instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider_symbol: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="market")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    observations: Mapped[list[MarketObservation]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class MarketObservation(Base):
    __tablename__ = "market_observations"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "provider",
            "provider_symbol",
            "assessment_date",
            name="uq_market_observation_source_date",
        ),
        Index("ix_market_observation_instrument_date", "instrument_id", "assessment_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("market_instruments.id", ondelete="CASCADE"), nullable=False
    )
    assessment_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    source_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    benchmark_definition: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    instrument: Mapped[MarketInstrument] = relationship(back_populates="observations")
