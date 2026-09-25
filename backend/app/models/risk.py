from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RiskRegisterEntry(Base):
    __tablename__ = "risk_register"
    __table_args__ = (
        CheckConstraint(
            "materiality IN ('Low', 'Moderate', 'Major', 'Catastrophic')",
            name="materiality_allowed",
        ),
        CheckConstraint(
            "trend IN ('increasing', 'unchanged', 'decreasing')",
            name="trend_allowed",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    risk_category: Mapped[str] = mapped_column(String(180), nullable=False)
    materiality: Mapped[str] = mapped_column(String(30), nullable=False)
    trend: Mapped[str] = mapped_column(String(30), nullable=False)
    risk_owner: Mapped[str] = mapped_column(String(120), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class DashboardContent(Base):
    __tablename__ = "dashboard_content"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    item_key: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str | None] = mapped_column(String(240), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


# Backwards compatibility alias
NarrativeContent = DashboardContent
