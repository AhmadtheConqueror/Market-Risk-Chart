from datetime import datetime, timezone
from typing import Any
from sqlalchemy import String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


def now():
    return datetime.now(timezone.utc)


class ShippingVessel(Base):
    __tablename__ = "shipping_vessels"
    mmsi: Mapped[str] = mapped_column(String(9), primary_key=True)
    imo: Mapped[int | None] = mapped_column(Integer)
    vessel_name: Mapped[str | None] = mapped_column(String(120))
    callsign: Mapped[str | None] = mapped_column(String(30))
    vessel_type_code: Mapped[int | None] = mapped_column(Integer)
    draught: Mapped[float | None] = mapped_column(Float)
    destination: Mapped[str | None] = mapped_column(String(120))
    eta_raw: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    latest_static_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(30), default="aisstream")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ShippingPosition(Base):
    __tablename__ = "shipping_positions"
    __table_args__ = (Index("ix_shipping_position_mmsi_received", "mmsi", "received_at"), Index("ix_shipping_position_received", "received_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mmsi: Mapped[str] = mapped_column(ForeignKey("shipping_vessels.mmsi"))
    dedupe_key: Mapped[str] = mapped_column(String(64), unique=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provider_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ais_utc_second: Mapped[int | None] = mapped_column(Integer)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    sog: Mapped[float | None] = mapped_column(Float)
    cog: Mapped[float | None] = mapped_column(Float)
    heading: Mapped[float | None] = mapped_column(Float)
    navigation_status: Mapped[int | None] = mapped_column(Integer)
    region: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(30), default="aisstream")
    raw_message_type: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ShippingWatchlist(Base):
    __tablename__ = "shipping_watchlist"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mmsi: Mapped[str] = mapped_column(String(9), unique=True)
    vessel_name: Mapped[str | None] = mapped_column(String(120))
    reason: Mapped[str | None] = mapped_column(String(400))
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ShippingEvent(Base):
    __tablename__ = "shipping_events"
    __table_args__ = (UniqueConstraint("mmsi", "event_type", name="uq_shipping_event_mmsi_type"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mmsi: Mapped[str] = mapped_column(String(9))
    event_type: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(20))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    observed_value: Mapped[float | None] = mapped_column(Float)
    threshold: Mapped[float | None] = mapped_column(Float)
    region: Mapped[str | None] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ShippingCollectorState(Base):
    __tablename__ = "shipping_collector_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(30))
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    compression_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    counters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_error: Mapped[str | None] = mapped_column(String(120))
