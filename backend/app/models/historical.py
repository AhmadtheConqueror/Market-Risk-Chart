from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, Integer, Numeric, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class HistoricalMarketObservation(Base):
    __tablename__ = "historical_market_observations"
    __table_args__ = (
        UniqueConstraint("instrument_key", "provider", "provider_symbol", "assessment_date", name="uq_historical_source_date"),
        Index("ix_historical_instrument_date", "instrument_key", "assessment_date"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(50))
    provider: Mapped[str] = mapped_column(String(80))
    provider_symbol: Mapped[str] = mapped_column(String(100))
    benchmark_definition: Mapped[str] = mapped_column(String(200))
    assessment_date: Mapped[date] = mapped_column(Date)
    native_value: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    native_unit: Mapped[str] = mapped_column(String(40))
    converted_value: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    conversion_factor: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    workbook_source: Mapped[str] = mapped_column(String(255))
    workbook_sha256: Mapped[str] = mapped_column(String(64))
    worksheet: Mapped[str] = mapped_column(String(100))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
