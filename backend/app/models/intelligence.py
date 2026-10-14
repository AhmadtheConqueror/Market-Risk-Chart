from datetime import date, datetime, timezone
from typing import Any
from sqlalchemy import String, Integer, Text, Date, DateTime, JSON, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


def now(): return datetime.now(timezone.utc)


class IntelligenceDocument(Base):
    __tablename__ = "intelligence_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_organisation: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(255))
    report_date: Mapped[date | None] = mapped_column(Date)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_hash: Mapped[str] = mapped_column(String(64), unique=True)
    storage_path: Mapped[str] = mapped_column(String(150))
    processing_status: Mapped[str] = mapped_column(String(20), default="uploaded")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(String(500))
    extraction_limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(Text)
    findings_rejected: Mapped[int] = mapped_column(Integer, default=0)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IntelligenceChunk(Base):
    __tablename__ = "intelligence_chunks"
    __table_args__ = (UniqueConstraint("document_id","sequence",name="uq_intelligence_chunk_sequence"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("intelligence_documents.id",ondelete="CASCADE"), index=True)
    chunk_type: Mapped[str] = mapped_column(String(30))
    page_number: Mapped[int | None] = mapped_column(Integer)
    sheet_name: Mapped[str | None] = mapped_column(String(100))
    section_name: Mapped[str | None] = mapped_column(String(255))
    source_locator: Mapped[str] = mapped_column(String(500))
    text_content: Mapped[str] = mapped_column(Text)
    structured_data: Mapped[dict[str,Any] | None] = mapped_column(JSON)
    sequence: Mapped[int] = mapped_column(Integer)


class IntelligenceFinding(Base):
    __tablename__ = "intelligence_findings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("intelligence_documents.id",ondelete="CASCADE"), index=True)
    commodity: Mapped[str] = mapped_column(String(120))
    geography: Mapped[str] = mapped_column(String(120))
    signal_type: Mapped[str] = mapped_column(String(40))
    direction: Mapped[str] = mapped_column(String(20))
    time_horizon: Mapped[str] = mapped_column(String(120))
    key_fact: Mapped[str] = mapped_column(Text)
    relevant_numbers: Mapped[list[str]] = mapped_column(JSON)
    driver: Mapped[str] = mapped_column(Text)
    risk_implication: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(10))
    source_chunk_id: Mapped[int] = mapped_column(ForeignKey("intelligence_chunks.id",ondelete="CASCADE"))
    source_locator: Mapped[str] = mapped_column(String(500))
    evidence_excerpt: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
