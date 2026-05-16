"""
SQLAlchemy 2.0 ClaimsMetrics — per-insurer, per-period claims and operational metrics.
Populated by the IPEC scraper; also supports manual entry.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class ClaimsMetrics(Base):
    """Per-insurer, per-period claims and operational KPIs."""

    __tablename__ = "claims_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Foreign key ──
    insurer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("insurers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── Period ──
    period_label:    Mapped[str]        = mapped_column(String(20), nullable=False)
    period_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ── Policy counts ──
    total_policies_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_policies_count:   Mapped[int | None] = mapped_column(Integer, nullable=True)
    policy_exits_count:   Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Complaints ──
    complaints_count:          Mapped[int | None]   = mapped_column(Integer, nullable=True)
    complaints_resolved_count: Mapped[int | None]   = mapped_column(Integer, nullable=True)
    complaints_resolution_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Risk flags ──
    claims_instalment_flag:   Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    working_capital_negative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Liquidity ──
    current_ratio:   Mapped[float | None] = mapped_column(Float, nullable=True)
    liquidity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── ML output ──
    settlement_power_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Provenance ──
    data_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at:  Mapped[datetime]   = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # ── Relationships ──
    insurer = relationship("Insurer", back_populates="claims_metrics")

    # ── Constraints ──
    __table_args__ = (
        UniqueConstraint("insurer_id", "period_label", name="uq_claims_insurer_period"),
    )
