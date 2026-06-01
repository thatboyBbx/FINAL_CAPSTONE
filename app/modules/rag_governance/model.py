"""
app/modules/rag_governance/model.py
=====================================
RetrievalAuditLog — immutable event log for every governed RAG query.

Records: who asked what, which chunks were retrieved, per-query confidence
scores, hallucination flags raised, and whether an answer was actually returned.
Enables post-hoc quality auditing and model-version accountability.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class RetrievalAuditLog(Base):
    __tablename__ = "retrieval_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    queried_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    document_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_method: Mapped[str] = mapped_column(String(50), default="semantic", nullable=False)

    chunks_retrieved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunks_above_threshold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    top_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    embedding_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    chunk_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    hallucination_flags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    filters_applied_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    answer_returned: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("ix_ral_document_id", "document_id"),
        Index("ix_ral_queried_at", "queried_at"),
    )
