from datetime import date, datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class IntelligenceSynthesisRun(Base):
    __tablename__ = "intelligence_synthesis_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    window_start: Mapped[date] = mapped_column(Date, index=True)
    window_end: Mapped[date] = mapped_column(Date, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String(20))
    model_version: Mapped[str] = mapped_column(String(120))
    input_hash: Mapped[str] = mapped_column(String(64))
    metrics: Mapped[dict] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(String(250))


class IntelligenceSynthesis(Base):
    __tablename__ = "intelligence_syntheses"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("intelligence_synthesis_runs.id", ondelete="CASCADE"), index=True)
    synthesis_type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    commodity: Mapped[str] = mapped_column(String(120))
    geography: Mapped[str] = mapped_column(String(120))
    signal_type: Mapped[str] = mapped_column(String(40))
    direction: Mapped[str] = mapped_column(String(40))
    time_horizon: Mapped[str] = mapped_column(String(120))
    confidence: Mapped[str] = mapped_column(String(10))
    confidence_basis: Mapped[dict] = mapped_column(JSON)
    evidence_count: Mapped[int] = mapped_column(Integer)


class IntelligenceSynthesisEvidence(Base):
    __tablename__ = "intelligence_synthesis_evidence"
    __table_args__ = (UniqueConstraint("synthesis_id", "finding_id", name="uq_synthesis_evidence"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    synthesis_id: Mapped[int] = mapped_column(ForeignKey("intelligence_syntheses.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("intelligence_findings.id", ondelete="CASCADE"), index=True)
    evidence_hash: Mapped[str] = mapped_column(String(64))
