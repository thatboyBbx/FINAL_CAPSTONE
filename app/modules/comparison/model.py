"""
SQLAlchemy 2.0 model for document comparison results.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DocumentComparison(Base):
    """Stores the result of a clause-by-clause comparison between two documents."""

    __tablename__ = "document_comparisons"

    id:            Mapped[int]            = mapped_column(Integer, primary_key=True, index=True)
    document_a_id: Mapped[int]            = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=False, index=True
    )
    document_b_id: Mapped[int]            = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=False, index=True
    )

    # processing / complete / failed
    status:           Mapped[str]            = mapped_column(String(20), default="processing", nullable=False)

    # Aggregated summary counts
    summary:          Mapped[dict | None]    = mapped_column(JSON, nullable=True)

    # Categorised change lists
    coverage_changes:  Mapped[list]          = mapped_column(JSON, default=list, nullable=False)
    exclusion_changes: Mapped[list]          = mapped_column(JSON, default=list, nullable=False)
    high_risk_changes: Mapped[list]          = mapped_column(JSON, default=list, nullable=False)
    all_changes:       Mapped[list]          = mapped_column(JSON, default=list, nullable=False)

    overall_similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at:   Mapped[datetime]       = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
