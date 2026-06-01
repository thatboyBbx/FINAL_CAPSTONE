"""
SQLAlchemy 2.0 ScrapeRun — audit log for every scraper execution.
Records status, counts, and errors for observability and deduplication.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_STATUS = Enum("running", "success", "partial", "failed", name="scrape_run_status")


class ScrapeRun(Base):
    """One row per scraper execution run."""

    __tablename__ = "scrape_runs"

    id:               Mapped[int]            = mapped_column(Integer, primary_key=True, index=True)
    scraper_name:     Mapped[str]            = mapped_column(String(100), nullable=False, index=True)
    run_started_at:   Mapped[datetime]       = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    run_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status:           Mapped[str]            = mapped_column(_STATUS, nullable=False, default="running")
    records_inserted: Mapped[int]            = mapped_column(Integer, default=0, nullable=False)
    records_updated:  Mapped[int]            = mapped_column(Integer, default=0, nullable=False)
    error_message:    Mapped[str | None]     = mapped_column(Text, nullable=True)
    created_at:       Mapped[datetime]       = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_scrape_runs_status_time", "status", "run_started_at"),
    )
