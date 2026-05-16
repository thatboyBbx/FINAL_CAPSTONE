"""
Text-based Risk Feature Extractor for ML pipeline integration.

Converts CircularAnalysis records for a given insurer into a numeric
feature vector that can be appended to the main tabular training features.

This bridges the deep-learning circular NLP output with the tabular ML model.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.circulars.model import CircularAnalysis
from app.modules.documents.model import Document


# Feature names contributed by circular NLP (must match order used in trainer)
CIRCULAR_FEATURE_NAMES = [
    "circular_count",
    "circular_high_count",
    "circular_moderate_count",
    "circular_avg_risk_score",
    "circular_max_risk_score",
    "circular_compliance_signals",
    "circular_financial_stress_signals",
    "circular_claims_signals",
    "circular_total_risk_signals",
]


class CircularFeatureExtractor:
    """
    Aggregates circular analysis results across all circulars uploaded for
    the same insurer (matched by insurer name in document notes/category).

    Since circulars are not directly linked to insurers in the DB, we use
    all analysed circulars for a simplified aggregate (suitable for demo mode).
    In production, you would link Document → insurer_id.
    """

    def compute(self, analyses: list[CircularAnalysis]) -> dict[str, float]:
        if not analyses:
            return {name: 0.0 for name in CIRCULAR_FEATURE_NAMES}

        total = len(analyses)
        high_count = sum(1 for a in analyses if a.fused_risk_level == "high")
        mod_count  = sum(1 for a in analyses if a.fused_risk_level == "moderate")

        risk_scores = [a.fused_risk_score or 0.0 for a in analyses]
        nlp_scores  = [a.nlp_risk_score or 0.0 for a in analyses]

        all_scores = [max(r, n) for r, n in zip(risk_scores, nlp_scores)]

        avg_score = round(sum(all_scores) / total, 4)
        max_score = round(max(all_scores), 4)

        compliance_total      = sum(a.compliance_signal or 0 for a in analyses)
        fin_stress_total      = sum(a.financial_stress_signal or 0 for a in analyses)
        claims_total          = sum(a.claims_signal or 0 for a in analyses)
        total_risk_signals    = sum(a.total_risk_signals or 0 for a in analyses)

        return {
            "circular_count":                  float(total),
            "circular_high_count":             float(high_count),
            "circular_moderate_count":         float(mod_count),
            "circular_avg_risk_score":         avg_score,
            "circular_max_risk_score":         max_score,
            "circular_compliance_signals":     float(compliance_total),
            "circular_financial_stress_signals": float(fin_stress_total),
            "circular_claims_signals":         float(claims_total),
            "circular_total_risk_signals":     float(total_risk_signals),
        }


def get_circular_features(db: Session) -> dict[str, float]:
    """
    Compute aggregate circular features from all analysed circulars in the DB.
    In the current architecture (circulars not linked per-insurer), this returns
    system-wide circular risk signal aggregates, which represent the regulatory
    environment each insurer operates in.
    """
    analyses = (
        db.query(CircularAnalysis)
        .filter(CircularAnalysis.status == "analysed")
        .all()
    )
    return CircularFeatureExtractor().compute(analyses)
