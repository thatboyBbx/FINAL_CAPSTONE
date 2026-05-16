"""
Hybrid Risk Score Fusion
=========================
Combines three risk signal sources into a single unified risk score:

  1. ML Settlement-Risk Score  (from GBDT/MLP tabular model)
  2. News Risk Score           (from NLP keyword analysis)
  3. Circular Risk Score       (from DL text classifier on regulatory circulars)

Each signal is time-decay weighted (more recent = higher weight).
The fused score is a weighted sum normalised to [0, 1].

Weights (configurable):
  ml_weight:       0.50  ← core financial + news ML model
  news_weight:     0.20  ← current news sentiment
  circular_weight: 0.30  ← regulatory environment signal
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.modules.scoring.time_decay import apply_decay_to_scores


# ---------------------------------------------------------------------------
# Fusion weights
# ---------------------------------------------------------------------------
ML_WEIGHT       = 0.50
NEWS_WEIGHT     = 0.20
CIRCULAR_WEIGHT = 0.30

RISK_CLASS_TO_SCORE = {"low": 0.15, "moderate": 0.55, "high": 0.90}
SCORE_TO_LABEL = [(0.35, "low"), (0.65, "moderate"), (1.01, "high")]


@dataclass
class FusedRiskResult:
    insurer_id:            int
    fused_score:           float         # 0-1 continuous
    fused_label:           str           # low / moderate / high
    ml_score:              float
    news_score_normalised: float
    circular_score_normalised: float
    ml_weight_used:        float
    news_weight_used:      float
    circular_weight_used:  float
    details:               dict[str, Any]


def fuse_risk_scores(
    insurer_id: int,
    ml_prediction: dict,
    news_risk_score: float,
    circular_risk_score: float,
    reference_date: date | None = None,
    ml_data_date: date | None = None,
    news_data_date: date | None = None,
    circular_data_date: date | None = None,
    settlement_power_score: float | None = None,
) -> FusedRiskResult:
    """
    Fuse ML + news + circular risk signals into a unified risk score.

    Args:
        insurer_id:           Insurer being scored
        ml_prediction:        Output from MLPredictor.predict()
        news_risk_score:      Aggregate news NLP risk score (0–∞, normalised internally)
        circular_risk_score:  Aggregate circular DL risk score (0–10)
        reference_date:       'Now' (defaults to today)
        *_data_date:          Date of the underlying data for time-decay
    """
    ref = reference_date or date.today()

    # ---- ML score (from probabilities) ----
    probs = ml_prediction.get("probabilities", {})
    ml_raw = (
        0.0 * (probs.get("low") or 0.0) +
        0.5 * (probs.get("moderate") or 0.0) +
        1.0 * (probs.get("high") or 0.0)
    )
    ml_score = _decay_single(ml_raw, ref, ml_data_date, half_life=90)

    # ---- News score (normalise 0-25 → 0-1) ----
    news_norm  = min(news_risk_score / 25.0, 1.0)
    news_score = _decay_single(news_norm, ref, news_data_date, half_life=30)

    # ---- Circular score (normalise 0-10 → 0-1) ----
    circ_norm  = min(circular_risk_score / 10.0, 1.0)
    circ_score = _decay_single(circ_norm, ref, circular_data_date, half_life=180)

    # ---- Insurer financial risk factor (weight 15%) ----
    # Uses settlement_power_score: lower score = higher risk
    # Rescales existing weights when this factor is present
    insurer_fin_risk = 0.0
    if settlement_power_score is not None:
        insurer_fin_risk = (100.0 - float(settlement_power_score)) / 100.0 * 0.15
        ml_w    = ML_WEIGHT       * 0.85
        news_w  = NEWS_WEIGHT     * 0.85
        circ_w  = CIRCULAR_WEIGHT * 0.85
    else:
        ml_w    = ML_WEIGHT
        news_w  = NEWS_WEIGHT
        circ_w  = CIRCULAR_WEIGHT

    # ---- Weighted fusion ----
    fused = (
        ml_w    * ml_score +
        news_w  * news_score +
        circ_w  * circ_score +
        insurer_fin_risk
    )
    fused = round(min(max(fused, 0.0), 1.0), 4)

    # ---- Label ----
    label = "low"
    for threshold, lbl in SCORE_TO_LABEL:
        if fused < threshold:
            label = lbl
            break

    return FusedRiskResult(
        insurer_id=insurer_id,
        fused_score=fused,
        fused_label=label,
        ml_score=round(ml_score, 4),
        news_score_normalised=round(news_score, 4),
        circular_score_normalised=round(circ_score, 4),
        ml_weight_used=ML_WEIGHT,
        news_weight_used=NEWS_WEIGHT,
        circular_weight_used=CIRCULAR_WEIGHT,
        details={
            "ml_raw_score":       round(ml_raw, 4),
            "news_raw_score":     round(news_risk_score, 4),
            "circular_raw_score": round(circular_risk_score, 4),
            "ml_prediction_class": ml_prediction.get("prediction_class"),
        },
    )


def _decay_single(
    score: float,
    ref: date,
    data_date: date | None,
    half_life: int,
) -> float:
    """Apply time decay to a single score given its data date."""
    if data_date is None:
        return score
    pairs = [(score, data_date)]
    return apply_decay_to_scores(pairs, ref, half_life)


# ---------------------------------------------------------------------------
# Convenience: compute full fused score from DB
# ---------------------------------------------------------------------------

def compute_fused_risk(
    db: Session,
    insurer_id: int,
    profile: str = "demo",
    days: int = 90,
) -> FusedRiskResult:
    """
    High-level helper: pulls ML prediction + news + circular signals from DB
    and returns a fused risk result.
    """
    from datetime import date as date_type
    from app.modules.ml.predictor import MLPredictor
    from app.modules.news.repo import NewsRepo
    from app.modules.news.features import NewsFeatureEngineer
    from app.modules.financials.repo import FinancialRepo
    from app.modules.circulars.model import CircularAnalysis

    ref = date_type.today()

    # ML prediction
    try:
        predictor = MLPredictor()
        ml_result = predictor.predict(db=db, insurer_id=insurer_id, profile=profile, days=days)
    except Exception:
        ml_result = {"prediction_class": "low", "probabilities": {"low": 1.0, "moderate": 0.0, "high": 0.0}}

    # Latest financial date
    fin_repo = FinancialRepo()
    latest_fin = fin_repo.latest(db, insurer_id)
    fin_date = latest_fin.reporting_date if latest_fin else None

    # News features
    news_date = None
    news_risk_score = 0.0
    try:
        news_repo = NewsRepo()
        end = fin_date or ref
        start = end - timedelta(days=days)
        articles = news_repo.list_by_range(db, insurer_id, start=start, end=end)
        news_features = NewsFeatureEngineer(articles).compute()
        news_risk_score = float(news_features.get("news_risk_score", 0.0))
        if articles:
            news_date = max(a.published_date for a in articles)
    except Exception:
        pass

    # Circular risk (system-wide aggregate)
    circular_risk_score = 0.0
    circular_date = None
    try:
        analyses = (
            db.query(CircularAnalysis)
            .filter(CircularAnalysis.status == "analysed")
            .all()
        )
        if analyses:
            scores = [a.fused_risk_score or 0.0 for a in analyses]
            circular_risk_score = round(sum(scores) / len(scores) * 10.0, 4)  # normalised to 0-10
            circular_date = max(a.analysed_at.date() for a in analyses)
    except Exception:
        pass

    return fuse_risk_scores(
        insurer_id=insurer_id,
        ml_prediction=ml_result,
        news_risk_score=news_risk_score,
        circular_risk_score=circular_risk_score,
        reference_date=ref,
        ml_data_date=fin_date,
        news_data_date=news_date,
        circular_data_date=circular_date,
    )
