"""
SQLAlchemy 2.0 model for QA sessions — stores every question asked against a document
and the generated answer with citations.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class QASession(Base):
    """One row per question asked against a document via the RAG Q&A endpoint."""

    __tablename__ = "qa_sessions"

    id:          Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id"), nullable=False, index=True)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer:   Mapped[str] = mapped_column(Text, nullable=False)

    # Cited chunks: list of {chunk_index, text, char_start, char_end}
    citations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # 0.0–1.0 confidence score derived from retrieval distance
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # How many chunks were retrieved for context
    retrieved_chunks: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Model name used to generate the answer (e.g. claude-sonnet-4-20250514)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
