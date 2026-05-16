"""
SQLAlchemy 2.0 model for document language analysis results.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DocumentLanguageAnalysis(Base):
    """Stores per-document language detection and translation results."""

    __tablename__ = "document_language_analysis"

    id:          Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    primary_language:    Mapped[str | None] = mapped_column(String(10), nullable=True)  # e.g. "en", "sn"
    is_mixed_language:   Mapped[bool]        = mapped_column(Boolean, default=False, nullable=False)
    shona_segment_count: Mapped[int]         = mapped_column(Integer, default=0, nullable=False)
    shona_pct:           Mapped[float]       = mapped_column(Float, default=0.0, nullable=False)

    # Non-English segments: [{segment_index, text, language_code, confidence, char_start, char_end}]
    segments_json:     Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # Translations: [{original, translated, source_lang, target_lang, model}]
    translations_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
