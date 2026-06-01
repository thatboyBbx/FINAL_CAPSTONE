"""
SQLAlchemy 2.0 models for clause deviation scoring.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class StandardClause(Base):
    """Library of standard/reference insurance clauses used for deviation scoring."""

    __tablename__ = "standard_clauses"

    id:           Mapped[int]    = mapped_column(Integer, primary_key=True, index=True)
    text:         Mapped[str]    = mapped_column(Text, nullable=False)
    clause_type:  Mapped[str]    = mapped_column(String(100), nullable=False, index=True)
    source:       Mapped[str]    = mapped_column(String(200), nullable=False)
    jurisdiction: Mapped[str]    = mapped_column(String(100), default="international", nullable=False)
    # MD5/SHA256 hash to prevent duplicate inserts
    text_hash:    Mapped[str]    = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at:   Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class ClauseDeviationScore(Base):
    """Stores the deviation score of each extracted clause against the standard library."""

    __tablename__ = "clause_deviation_scores"

    id:                         Mapped[int]          = mapped_column(Integer, primary_key=True, index=True)
    document_id:                Mapped[int]          = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=False, index=True
    )
    # Nullable — not all clauses have a matching extracted entity record
    circular_analysis_id:       Mapped[int | None]   = mapped_column(
        Integer, ForeignKey("circular_analyses.id"), nullable=True
    )

    clause_text:                Mapped[str]          = mapped_column(Text, nullable=False)
    clause_type:                Mapped[str]          = mapped_column(String(100), nullable=False)

    # 0.0 = identical to standard; 1.0 = completely different
    deviation_score:            Mapped[float | None] = mapped_column(Float, nullable=True)
    # standard / minor_deviation / material_deviation / significant_deviation
    deviation_label:            Mapped[str | None]   = mapped_column(String(50), nullable=True)

    closest_standard_clause_id: Mapped[int | None]   = mapped_column(
        Integer, ForeignKey("standard_clauses.id"), nullable=True
    )
    similarity_to_standard:     Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_implication:           Mapped[str | None]   = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
