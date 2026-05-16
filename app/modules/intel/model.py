"""
SQLAlchemy 2.0 IntelArticle — GDELT-sourced Zimbabwe insurance news articles.
"""
from __future__ import annotations

from sqlalchemy import Float, Index, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class IntelArticle(Base):
    """One row per news article retrieved from GDELT."""

    __tablename__ = "intel_articles"

    id:              Mapped[str]         = mapped_column(String(64),  primary_key=True)  # sha256[:24]
    fetched_at:      Mapped[str]         = mapped_column(String(40),  nullable=False)
    published_at:    Mapped[str | None]  = mapped_column(String(40),  nullable=True)
    title:           Mapped[str | None]  = mapped_column(Text,        nullable=True)
    url:             Mapped[str]         = mapped_column(Text,        nullable=False)
    domain:          Mapped[str | None]  = mapped_column(String(120), nullable=True, index=True)
    source_country:  Mapped[str | None]  = mapped_column(String(60),  nullable=True)
    snippet:         Mapped[str | None]  = mapped_column(Text,        nullable=True)
    topics_json:     Mapped[str | None]  = mapped_column(Text,        nullable=True)  # JSON list
    raw_json:        Mapped[str | None]  = mapped_column(Text,        nullable=True)
    insurer_name:    Mapped[str | None]  = mapped_column(String(120), nullable=True, index=True)
    insurance_type:  Mapped[str | None]  = mapped_column(String(120), nullable=True, index=True)
    risk_label:      Mapped[str | None]  = mapped_column(String(60),  nullable=True, index=True)
    risk_confidence: Mapped[float | None] = mapped_column(Float,      nullable=True)

    __table_args__ = (
        Index("ix_intel_pub", "published_at"),
    )
