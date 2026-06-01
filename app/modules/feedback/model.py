"""
SQLAlchemy 2.0 models for the active learning feedback tables.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class EntityFeedback(Base):
    """Stores broker/expert corrections to NER entity extractions."""

    __tablename__ = "entity_feedback"

    id:                   Mapped[int]          = mapped_column(Integer, primary_key=True, index=True)
    document_id:          Mapped[int]          = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=False, index=True
    )
    # nullable — links to the specific analysis where the entity was extracted
    circular_analysis_id: Mapped[int | None]   = mapped_column(
        Integer, ForeignKey("circular_analyses.id"), nullable=True
    )

    original_value:  Mapped[str]  = mapped_column(Text, nullable=False)
    original_type:   Mapped[str]  = mapped_column(String(100), nullable=False)
    corrected_value: Mapped[str]  = mapped_column(Text, nullable=False)
    corrected_type:  Mapped[str]  = mapped_column(String(100), nullable=False)
    corrected_by:    Mapped[str]  = mapped_column(String(200), nullable=False)

    used_in_training: Mapped[bool]          = mapped_column(Boolean, default=False, nullable=False)
    used_at:          Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_entity_feedback_pending", "used_in_training", "created_at"),
    )


class RiskFlagFeedback(Base):
    """Stores corrections to risk flag classifications."""

    __tablename__ = "risk_flag_feedback"

    id:                   Mapped[int]  = mapped_column(Integer, primary_key=True, index=True)
    circular_analysis_id: Mapped[int]  = mapped_column(
        Integer, ForeignKey("circular_analyses.id"), nullable=False, index=True
    )

    flag_text:         Mapped[str]  = mapped_column(Text, nullable=False)
    original_severity: Mapped[str]  = mapped_column(String(50), nullable=False)
    correct_severity:  Mapped[str]  = mapped_column(String(50), nullable=False)
    is_false_positive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    corrected_by:      Mapped[str]  = mapped_column(String(200), nullable=False)

    used_in_training: Mapped[bool]           = mapped_column(Boolean, default=False, nullable=False)
    used_at:          Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_risk_flag_feedback_pending", "used_in_training", "created_at"),
    )
