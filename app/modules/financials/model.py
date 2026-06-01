"""
SQLAlchemy 2.0 FinancialSnapshot — per-insurer, per-period financial statement data.
Extended with the full IPEC/ZSE schema. Legacy columns (claims_reserves,
claims_paid, premiums_written, liquidity_ratio) are kept for backward compatibility.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Date, DateTime, Enum, Float, ForeignKey,
    Index, Integer, Numeric, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

_PERIOD_TYPE = Enum("quarterly", "annual", "half_year", name="financial_period_type")


class FinancialSnapshot(Base):
    """Per-insurer, per-period financial snapshot row."""

    __tablename__ = "financial_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Foreign key ──
    insurer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("insurers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── Period ──
    reporting_date: Mapped[date | None]  = mapped_column(Date, nullable=True, index=True)
    period_type:    Mapped[str | None]   = mapped_column(_PERIOD_TYPE, nullable=True)
    period_label:   Mapped[str | None]   = mapped_column(String(20), nullable=True)
    currency:       Mapped[str | None]   = mapped_column(String(5), nullable=True, default="USD")

    # ── Legacy columns (kept for existing code) ──
    claims_reserves:  Mapped[float | None] = mapped_column(Float, nullable=True)
    claims_paid:      Mapped[float | None] = mapped_column(Float, nullable=True)
    premiums_written: Mapped[float | None] = mapped_column(Float, nullable=True)
    liquidity_ratio:  Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Income statement ──
    total_revenue_usd:     Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    insurance_revenue_usd: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    profit_after_tax_usd:  Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    investment_income_usd: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)

    # ── Balance sheet ──
    total_assets_usd:                Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_liabilities_usd:           Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    capital_position_usd:            Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    minimum_capital_requirement_usd: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)

    # ── Ratios ──
    capital_adequacy_ratio: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    market_share_pct:       Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    prescribed_assets_pct:  Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    reinsurance_assets_pct: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    property_assets_pct:    Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    cash_and_bank_pct:      Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)

    # ── Provenance ──
    data_source:   Mapped[str | None] = mapped_column(String(200), nullable=True)
    scrape_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("scrape_runs.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # ── Relationships ──
    insurer = relationship("Insurer", back_populates="financial_snapshots")

    # ── Constraints / indexes ──
    __table_args__ = (
        UniqueConstraint("insurer_id", "period_label", "period_type",
                         name="uq_financial_insurer_period"),
        Index("ix_financial_insurer_date", "insurer_id", "reporting_date"),
    )


class InsurerFinancials(Base):
    """One row per insurer per FSR-1 reporting period (quarterly or annual). Used by CSP scoring."""

    __tablename__ = "insurer_financials"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    insurer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("insurers.id"), nullable=False, index=True
    )

    # ── Period ────────────────────────────────────────────────────────────────
    period_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="quarterly | annual"
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_quarter: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="1–4, NULL for annual"
    )

    # ── Solvency ──────────────────────────────────────────────────────────────
    total_assets_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    total_liabilities_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    solvency_margin_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    solvency_ratio_pct: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=0, comment="e.g. 187.5"
    )
    ipec_minimum_solvency_pct: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("150.0")
    )

    # ── Claims ────────────────────────────────────────────────────────────────
    gross_claims_paid_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    outstanding_claims_reserve: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    ibnr_reserve_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    total_claims_reserves_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=0, comment="outstanding + IBNR"
    )
    claims_ratio_pct: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0)

    # ── Liquidity ─────────────────────────────────────────────────────────────
    current_assets_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    current_liabilities_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    liquidity_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=0)
    liquid_assets_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=0, comment="Cash + short-term instruments only"
    )

    # ── Premiums ──────────────────────────────────────────────────────────────
    gross_premiums_written_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    net_premiums_earned_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)

    # ── Metadata ──────────────────────────────────────────────────────────────
    data_source: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="e.g. 'IPEC FSR-1 Q3 2024'"
    )
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extraction_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0,
        comment="1.0 = clean PDF table, 0.7 = OCR"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_insurer_financials_period", "insurer_id", "period_year", "period_quarter"),
    )
