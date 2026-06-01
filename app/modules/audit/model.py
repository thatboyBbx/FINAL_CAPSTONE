"""
SQLAlchemy 2.0 model for the audit log.
No FK constraints on document_id / analysis_id so audit records survive
deletion of the referenced entities.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Index, Integer, JSON, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AuditLog(Base):
    """One row per auditable action in the system."""

    __tablename__ = "audit_log"

    id:           Mapped[int]            = mapped_column(Integer, primary_key=True, index=True)
    event_type:   Mapped[str]            = mapped_column(String(100), nullable=False, index=True)
    actor:        Mapped[str]            = mapped_column(String(200), nullable=False, index=True)

    # Nullable references — no FK so records survive document/analysis deletion
    document_id:  Mapped[int | None]     = mapped_column(Integer, nullable=True)
    analysis_id:  Mapped[int | None]     = mapped_column(Integer, nullable=True)

    # IPv4/IPv6 as string (SQLite has no INET type)
    ip_address:   Mapped[str | None]     = mapped_column(String(45), nullable=True)

    # Arbitrary details dict (error codes, request paths, etc.)
    details:      Mapped[dict]           = mapped_column(JSON, default=dict, nullable=False)

    created_at:   Mapped[datetime]       = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Composite indexes for common query patterns
    __table_args__ = (
        Index("ix_audit_doc_created", "document_id", "created_at"),
        Index("ix_audit_actor_created", "actor", "created_at"),
        Index("ix_audit_event_created", "event_type", "created_at"),
    )
