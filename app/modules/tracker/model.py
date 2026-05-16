"""
SQLAlchemy 2.0 model for the policy expiry tracker.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PolicyTracker(Base):
    """Tracks policy periods and expiry dates extracted from uploaded documents."""

    __tablename__ = "policy_tracker"

    id:           Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id:  Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    portfolio_id:  Mapped[str | None]  = mapped_column(String(200), nullable=True, index=True)
    policy_number: Mapped[str | None]  = mapped_column(String(200), nullable=True)
    insured_name:  Mapped[str | None]  = mapped_column(Text, nullable=True)
    insurer_name:  Mapped[str | None]  = mapped_column(Text, nullable=True)

    policy_start_date: Mapped[date | None]  = mapped_column(Date, nullable=True)
    expiry_date:       Mapped[date | None]  = mapped_column(Date, nullable=True, index=True)
    days_until_expiry: Mapped[int | None]   = mapped_column(Integer, nullable=True)

    premium_amount_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    # active / expiring_soon / expired / renewed
    alert_status:  Mapped[str]            = mapped_column(String(30), default="active", nullable=False, index=True)
    last_notified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # FK to the renewal document when the policy is renewed
    renewal_document_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
