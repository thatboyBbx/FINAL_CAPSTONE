"""
SQLAlchemy 2.0 model for batch document processing jobs.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProcessingBatch(Base):
    """Tracks a batch upload job containing multiple documents."""

    __tablename__ = "processing_batches"

    id:               Mapped[int]            = mapped_column(Integer, primary_key=True, index=True)
    portfolio_id:     Mapped[str]            = mapped_column(String(200), nullable=False, index=True)
    uploaded_by:      Mapped[str | None]     = mapped_column(String(200), nullable=True)

    total_documents:  Mapped[int]            = mapped_column(Integer, default=0, nullable=False)
    completed_count:  Mapped[int]            = mapped_column(Integer, default=0, nullable=False)
    failed_count:     Mapped[int]            = mapped_column(Integer, default=0, nullable=False)

    # queued / processing / complete / partial_failure
    status:           Mapped[str]            = mapped_column(String(30), default="queued", nullable=False)

    created_at:       Mapped[datetime]       = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    completed_at:     Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
