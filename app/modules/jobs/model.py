"""
SQLAlchemy models for the async job queue subsystem.

Three tables:
  queued_jobs       — raw queue entries (enqueued, claimed, complete, failed)
  document_job_steps — per-document per-step status for API visibility
  dead_letter_jobs  — jobs that exhausted all retry attempts
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class QueuedJob(Base):
    """One unit of work in the async queue."""

    __tablename__ = "queued_jobs"

    id:            Mapped[int]           = mapped_column(Integer, primary_key=True, index=True)
    queue:         Mapped[str]           = mapped_column(String(50), nullable=False, index=True)
    fn_name:       Mapped[str]           = mapped_column(String(100), nullable=False)
    payload:       Mapped[str]           = mapped_column(Text, nullable=False)  # JSON kwargs

    # Status: queued | claimed | processing | complete | failed | dead_letter
    status:        Mapped[str]           = mapped_column(String(20), default="queued", nullable=False, index=True)
    attempt:       Mapped[int]           = mapped_column(Integer, default=0, nullable=False)
    max_attempts:  Mapped[int]           = mapped_column(Integer, default=3, nullable=False)

    # Optional link to a document (used by dead-letter and step tracking)
    document_id:   Mapped[int | None]    = mapped_column(Integer, nullable=True, index=True)
    step_name:     Mapped[str | None]    = mapped_column(String(100), nullable=True)

    # Timing
    scheduled_for: Mapped[datetime]      = mapped_column(DateTime, nullable=False, index=True)
    claimed_at:    Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at:  Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    worker_id:     Mapped[str | None]    = mapped_column(String(100), nullable=True)
    error_msg:     Mapped[str | None]    = mapped_column(Text, nullable=True)
    created_at:    Mapped[datetime]      = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class DocumentJobStep(Base):
    """
    Per-document per-step status record — updated by workers as they progress.
    Written on enqueue; updated through processing → complete/failed/dead_letter.
    Used by /api/admin/jobs/steps/{document_id} for progress visibility.
    """

    __tablename__ = "document_job_steps"

    id:           Mapped[int]            = mapped_column(Integer, primary_key=True, index=True)
    document_id:  Mapped[int]            = mapped_column(Integer, nullable=False, index=True)
    batch_id:     Mapped[int | None]     = mapped_column(Integer, nullable=True, index=True)
    queue:        Mapped[str]            = mapped_column(String(50), nullable=False)
    step_name:    Mapped[str]            = mapped_column(String(100), nullable=False)

    # Status: queued | claimed | processing | complete | failed | dead_letter
    status:       Mapped[str]            = mapped_column(String(20), default="queued", nullable=False, index=True)
    attempt:      Mapped[int]            = mapped_column(Integer, default=1, nullable=False)
    max_attempts: Mapped[int]            = mapped_column(Integer, default=3, nullable=False)
    error_msg:    Mapped[str | None]     = mapped_column(String(2000), nullable=True)

    queued_at:    Mapped[datetime]       = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    started_at:   Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    worker_id:    Mapped[str | None]     = mapped_column(String(100), nullable=True)

    # Linked QueuedJob (informational; no FK constraint to avoid migration chain impact)
    queued_job_id: Mapped[int | None]   = mapped_column(Integer, nullable=True)


class DeadLetterJob(Base):
    """Jobs that exhausted all retry attempts. Retained for audit and re-drive."""

    __tablename__ = "dead_letter_jobs"

    id:            Mapped[int]           = mapped_column(Integer, primary_key=True, index=True)
    queue:         Mapped[str]           = mapped_column(String(50), nullable=False, index=True)
    fn_name:       Mapped[str]           = mapped_column(String(100), nullable=False)
    document_id:   Mapped[int | None]    = mapped_column(Integer, nullable=True, index=True)
    job_payload:   Mapped[str]           = mapped_column(Text, nullable=False)   # JSON
    error_msg:     Mapped[str]           = mapped_column(Text, nullable=False)
    error_type:    Mapped[str]           = mapped_column(String(200), nullable=False)
    attempt_count: Mapped[int]           = mapped_column(Integer, nullable=False)
    failed_at:     Mapped[datetime]      = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    redriven:      Mapped[bool]          = mapped_column(Boolean, default=False, nullable=False)
    redriven_at:   Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
