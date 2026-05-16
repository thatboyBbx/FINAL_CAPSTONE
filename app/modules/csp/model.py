"""
app/modules/csp/model.py
=========================
CSP Score table — computed Claims Settlement Power scores per insurer per financial snapshot.

Uses SQLAlchemy 2.0 Mapped[] / mapped_column() exclusively.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CSPScore(Base):
    """Computed CSP score for a single insurer financial snapshot."""

    __tablename__ = "csp_scores"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    insurer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("insurers.id"), nullable=False, index=True
    )
    financials_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("insurer_financials.id"), nullable=False, index=True
    )

    # ── WCS component scores (0–100) ──────────────────────────────────────────
    solvency_score: Mapped[float] = mapped_column(Float, nullable=False)
    settlement_capacity_score: Mapped[float] = mapped_column(Float, nullable=False)
    reserves_adequacy_score: Mapped[float] = mapped_column(Float, nullable=False)
    liquidity_score: Mapped[float] = mapped_column(Float, nullable=False)
    wcs_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    wcs_band: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Strong | Adequate | Marginal | Weak | Critical"
    )

    # ── XGBoost anomaly layer ─────────────────────────────────────────────────
    xgb_at_risk_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    xgb_at_risk_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    shap_values_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON: feature → SHAP contribution"
    )

    # ── NLG output ────────────────────────────────────────────────────────────
    natural_language_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    broker_recommendation: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # ── Metadata ──────────────────────────────────────────────────────────────
    scored_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    model_version: Mapped[str] = mapped_column(
        String(50), nullable=False, default="wcs_v1.0_xgb_v1.0"
    )
