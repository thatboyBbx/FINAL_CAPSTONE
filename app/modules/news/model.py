"""
SQLAlchemy 2.0 NewsArticle — scraped news stories linked to an insurer.
Extended with VADER sentiment fields (sentiment_score, sentiment_label, keywords).
The `url` column doubles as `source_url` for deduplication.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, Float, ForeignKey,
    Index, Integer, JSON, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

_SENTIMENT_LABEL = Enum("positive", "neutral", "negative", name="sentiment_label_enum")


class NewsArticle(Base):
    """One scraped news article linked to an insurer."""

    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Foreign key ──
    insurer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("insurers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── Article metadata ──
    published_date: Mapped[date]        = mapped_column(Date, nullable=False, index=True)
    source:         Mapped[str | None]  = mapped_column(String(200), nullable=True)
    title:          Mapped[str]         = mapped_column(String(400), nullable=False)
    content:        Mapped[str]         = mapped_column(Text, nullable=False)
    url:            Mapped[str | None]  = mapped_column(String(500), nullable=True, unique=True)

    # ── Snippet (first 500 chars for display) ──
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Sentiment (populated by NewsScraper / manual update) ──
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_label: Mapped[str | None]   = mapped_column(_SENTIMENT_LABEL, nullable=True)
    keywords:        Mapped[list | None]  = mapped_column(JSON, default=list, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # ── Relationships ──
    insurer = relationship("Insurer", back_populates="news_articles")

    __table_args__ = (
        Index("ix_news_insurer_date", "insurer_id", "published_date"),
    )
