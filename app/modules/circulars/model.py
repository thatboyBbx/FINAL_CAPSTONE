"""
SQLAlchemy 2.0 model for circular analysis results.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CircularAnalysis(Base):
    """
    Stores the NLP + deep learning analysis results for an uploaded circular document.
    Linked to the Document record via document_id.
    """

    __tablename__ = "circular_analyses"

    id:           Mapped[int]            = mapped_column(Integer, primary_key=True, index=True)
    document_id:  Mapped[int]            = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=False, index=True, unique=True
    )

    # Extracted text
    extracted_text:     Mapped[str | None]   = mapped_column(Text, nullable=True)

    # DL classifier output
    risk_level:         Mapped[str | None]   = mapped_column(String(20), nullable=True, index=True)
    risk_class:         Mapped[int | None]   = mapped_column(Integer, nullable=True)
    prob_low:           Mapped[float | None] = mapped_column(Float, nullable=True)
    prob_moderate:      Mapped[float | None] = mapped_column(Float, nullable=True)
    prob_high:          Mapped[float | None] = mapped_column(Float, nullable=True)
    fused_risk_level:   Mapped[str | None]   = mapped_column(String(20), nullable=True)
    fused_risk_score:   Mapped[float | None] = mapped_column(Float, nullable=True)

    # NLP category
    predicted_category:  Mapped[str | None]   = mapped_column(String(80), nullable=True)
    category_confidence: Mapped[float | None]  = mapped_column(Float, nullable=True)
    nlp_risk_score:      Mapped[float | None]  = mapped_column(Float, nullable=True)

    # NLP risk signal counts
    compliance_signal:       Mapped[int] = mapped_column(Integer, default=0)
    financial_stress_signal: Mapped[int] = mapped_column(Integer, default=0)
    claims_signal:           Mapped[int] = mapped_column(Integer, default=0)
    regulatory_signal:       Mapped[int] = mapped_column(Integer, default=0)
    market_conduct_signal:   Mapped[int] = mapped_column(Integer, default=0)
    total_risk_signals:      Mapped[int] = mapped_column(Integer, default=0)

    # Entities (stored as pipe-delimited strings for simplicity)
    dates_found:            Mapped[str | None] = mapped_column(Text, nullable=True)
    monetary_values_found:  Mapped[str | None] = mapped_column(Text, nullable=True)
    regulatory_refs_found:  Mapped[str | None] = mapped_column(Text, nullable=True)
    insurer_mentions_found: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Model info
    model_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status:      Mapped[str]        = mapped_column(String(30), default="analysed", nullable=False, index=True)

    analysed_at: Mapped[datetime]   = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
