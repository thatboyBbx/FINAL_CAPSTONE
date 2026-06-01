"""
app/modules/csp/schemas.py
===========================
Pydantic v2 schemas for the CSP module.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CSPScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    insurer_id: int
    financials_id: str

    solvency_score: float
    settlement_capacity_score: float
    reserves_adequacy_score: float
    liquidity_score: float
    wcs_score: float
    wcs_band: str

    xgb_at_risk_probability: float
    xgb_at_risk_flag: bool
    shap_values_json: str | None = None

    natural_language_summary: str
    broker_recommendation: str

    scored_at: datetime
    model_version: str
