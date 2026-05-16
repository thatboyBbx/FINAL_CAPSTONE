"""
SQLAlchemy 2.0 Insurer master data model — extended with full IPEC registry schema.
Keeps __tablename__ = "insurers" for FK compatibility with existing tables.
All new columns are nullable=True so old rows remain valid.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

# ── Enum types ─────────────────────────────────────────────────────────────

_CATEGORY = Enum(
    "short_term", "life_assurance", "reinsurer", "funeral_assurer",
    "microinsurer", "broker", "multiple_agent", "underwriting_agent",
    name="insurer_category",
)

_IPEC_STATUS = Enum(
    "active", "suspended", "cancelled", "under_curatorship",
    name="ipec_registration_status",
)


class Insurer(Base):
    """IPEC-registered insurer master record."""

    __tablename__ = "insurers"

    # ── Primary key ──
    id:   Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Names ──
    name:       Mapped[str]        = mapped_column(String(200), unique=True, nullable=False, index=True)
    short_name: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # ── Classification ──
    category:         Mapped[str | None] = mapped_column(_CATEGORY, nullable=True)
    industry_segment: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # ── ZSE information ──
    zse_listed: Mapped[bool]        = mapped_column(Boolean, default=False, nullable=False)
    zse_ticker: Mapped[str | None]  = mapped_column(String(10), nullable=True)

    # ── Corporate structure ──
    parent_group:        Mapped[str | None] = mapped_column(String(200), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── IPEC regulatory status ──
    ipec_registration_status: Mapped[str | None] = mapped_column(_IPEC_STATUS, default="active", nullable=True)

    # ── Contact / address ──
    head_office_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    head_office_city:    Mapped[str | None] = mapped_column(String(100), nullable=True, default="Harare")
    country:             Mapped[str | None] = mapped_column(String(80), nullable=True, default="Zimbabwe")
    phone:               Mapped[str | None] = mapped_column(String(50), nullable=True)
    email:               Mapped[str | None] = mapped_column(String(200), nullable=True)
    website:             Mapped[str | None] = mapped_column(String(300), nullable=True)

    # ── History / membership ──
    date_established: Mapped[date | None] = mapped_column(Date, nullable=True)
    icm_member:       Mapped[bool]        = mapped_column(Boolean, default=False, nullable=False)
    pool_participant: Mapped[bool]        = mapped_column(Boolean, default=False, nullable=False)

    # ── Notes ──
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Timestamps ──
    created_at: Mapped[datetime]       = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    # ── Relationships ──
    financial_snapshots = relationship(
        "FinancialSnapshot", back_populates="insurer", cascade="all, delete-orphan"
    )
    claims_metrics = relationship(
        "ClaimsMetrics", back_populates="insurer", cascade="all, delete-orphan"
    )
    news_articles = relationship(
        "NewsArticle", back_populates="insurer", cascade="all, delete-orphan"
    )
