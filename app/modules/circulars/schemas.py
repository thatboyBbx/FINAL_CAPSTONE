from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CircularAnalysisRead(BaseModel):
    id:           int
    document_id:  int

    risk_level:          str | None
    risk_class:          int | None
    prob_low:            float | None
    prob_moderate:       float | None
    prob_high:           float | None
    fused_risk_level:    str | None
    fused_risk_score:    float | None

    predicted_category:   str | None
    category_confidence:  float | None
    nlp_risk_score:       float | None

    compliance_signal:       int
    financial_stress_signal: int
    claims_signal:           int
    regulatory_signal:       int
    market_conduct_signal:   int
    total_risk_signals:      int

    dates_found:           str | None
    monetary_values_found: str | None
    regulatory_refs_found: str | None
    insurer_mentions_found: str | None

    model_label: str | None
    status:      str
    analysed_at: datetime

    model_config = {"from_attributes": True}


class CircularTrainResponse(BaseModel):
    status:       str
    n_samples:    int | None = None
    architecture: str | None = None
    model_file:   str | None = None
    error:        str | None = None


class CircularAnalyseRequest(BaseModel):
    document_id: int
