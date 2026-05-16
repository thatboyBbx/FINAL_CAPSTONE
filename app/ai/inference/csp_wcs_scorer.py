"""
CSP Weighted Composite Scorer.

Methodology Note (Chapter 3 — Model Design):

The Claims Settlement Power (CSP) model uses a Weighted Composite Score (WCS) as
its primary mechanism, supplemented by an XGBoost binary classifier for anomaly
detection.

WCS was selected over black-box alternatives for three reasons: (1) data volume
constraints — Zimbabwe's ~25 active insurers produce insufficient observations for
deep learning generalisation (Goodfellow et al., 2016); (2) interpretability
requirements — broker-facing advisory output must be fully explainable per
regulatory advisory standards; (3) regulatory grounding — normalization anchors
are derived directly from Zimbabwe's Insurance Act Chapter 24:07 and IPEC
supervisory directives, giving the model's thresholds formal regulatory validity.

Weight derivation: The 35/30/20/15 allocation across solvency, settlement capacity,
reserves adequacy, and liquidity was calibrated via leave-one-out ablation on IPEC's
historical distressed insurer register (insurers under curatorship 2015–2024). The
weight combination minimising mean absolute prediction error on known distress events
was selected as the production configuration, consistent with the ablation study
methodology described in Chapter 4.

XGBoost was selected for the anomaly layer because gradient boosting handles class
imbalance through iterative sample reweighting (Chen & Guestrin, 2016), and its
native SHAP integration (Lundberg & Lee, 2017) enables per-prediction feature
attribution, directly supporting the platform's explainability requirements.

All normalization anchors are grounded in regulatory thresholds where available
(IPEC minimum solvency 150%) and actuarial practice standards where regulatory
benchmarks are absent (e.g. 2-month liquid asset coverage adapted from Lloyd's
minimum liquidity requirements for the Zimbabwean context).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.ai.inference.csp_normalizer import (
    score_liquidity,
    score_reserves_adequacy,
    score_settlement_capacity,
    score_solvency,
)

# ─────────────────────────── Weights ─────────────────────────────────────────

WCS_WEIGHTS: dict[str, float] = {
    "solvency": 0.35,
    "settlement": 0.30,
    "reserves": 0.20,
    "liquidity": 0.15,
}

# ─────────────────────────── Band thresholds ─────────────────────────────────

WCS_BANDS: list[tuple[int, int, str]] = [
    (85, 100, "Strong"),
    (65, 84, "Adequate"),
    (45, 64, "Marginal"),
    (25, 44, "Weak"),
    (0, 24, "Critical"),
]


# ─────────────────────────── Data model ──────────────────────────────────────

@dataclass
class CSPComponentScores:
    """Fully computed CSP scores for a single insurer financial snapshot."""

    solvency_ratio_pct: float
    settlement_months: float
    reserves_ratio: float
    liquidity_ratio: float

    solvency_score: float
    settlement_capacity_score: float
    reserves_adequacy_score: float
    liquidity_score: float

    wcs_score: float
    wcs_band: str


# ─────────────────────────── Scorer ──────────────────────────────────────────

class WCSScorer:
    """Computes the Weighted Composite Score for a given insurer financial snapshot."""

    def score(
        self,
        solvency_ratio_pct: float,
        liquid_assets_usd: float,
        gross_claims_paid_usd: float,
        total_claims_reserves_usd: float,
        current_assets_usd: float,
        current_liabilities_usd: float,
    ) -> CSPComponentScores:
        sol_score = score_solvency(solvency_ratio_pct)
        set_score = score_settlement_capacity(liquid_assets_usd, gross_claims_paid_usd)
        res_score = score_reserves_adequacy(total_claims_reserves_usd, gross_claims_paid_usd)
        liq_score = score_liquidity(current_assets_usd, current_liabilities_usd)

        wcs = (
            WCS_WEIGHTS["solvency"] * sol_score
            + WCS_WEIGHTS["settlement"] * set_score
            + WCS_WEIGHTS["reserves"] * res_score
            + WCS_WEIGHTS["liquidity"] * liq_score
        )
        wcs = round(wcs, 2)

        band = self._assign_band(wcs)

        settlement_months = (
            liquid_assets_usd / (gross_claims_paid_usd / 12.0)
            if gross_claims_paid_usd > 0
            else 0.0
        )
        reserves_ratio = (
            total_claims_reserves_usd / gross_claims_paid_usd
            if gross_claims_paid_usd > 0
            else 0.0
        )
        liquidity_ratio_val = (
            current_assets_usd / current_liabilities_usd
            if current_liabilities_usd > 0
            else 0.0
        )

        return CSPComponentScores(
            solvency_ratio_pct=solvency_ratio_pct,
            settlement_months=round(settlement_months, 2),
            reserves_ratio=round(reserves_ratio, 2),
            liquidity_ratio=round(liquidity_ratio_val, 2),
            solvency_score=sol_score,
            settlement_capacity_score=set_score,
            reserves_adequacy_score=res_score,
            liquidity_score=liq_score,
            wcs_score=wcs,
            wcs_band=band,
        )

    def _assign_band(self, wcs_score: float) -> str:
        for lo, hi, label in WCS_BANDS:
            if lo <= wcs_score <= hi:
                return label
        return "Critical"

    def explain_components(self, scores: CSPComponentScores) -> list[str]:
        sentences: list[str] = []

        if scores.solvency_score >= 80:
            buffer = round(scores.solvency_ratio_pct - 150.0, 1)
            sentences.append(
                f"Solvency ratio of {scores.solvency_ratio_pct:.1f}% provides a "
                f"{buffer:.1f}% buffer above IPEC's mandatory minimum."
            )
        elif scores.solvency_score < 60 and scores.solvency_score >= 25:
            sentences.append(
                f"Solvency ratio of {scores.solvency_ratio_pct:.1f}% is close to "
                "IPEC's mandatory minimum of 150% — warrants monitoring."
            )
        elif scores.solvency_score < 25:
            sentences.append(
                f"Solvency ratio of {scores.solvency_ratio_pct:.1f}% is below "
                "IPEC's mandatory minimum of 150%."
            )

        if scores.settlement_capacity_score >= 80:
            sentences.append(
                f"Liquid assets cover approximately {scores.settlement_months:.1f} "
                "months of projected claims."
            )
        elif scores.settlement_capacity_score < 25:
            sentences.append(
                "Liquid assets cover less than one month of projected claims — "
                "settlement capacity is limited."
            )

        if scores.reserves_adequacy_score >= 80:
            sentences.append(
                f"Claims reserves are {scores.reserves_ratio:.2f}x annual paid claims — "
                "adequately provisioned."
            )
        elif scores.reserves_adequacy_score < 25:
            sentences.append(
                f"Claims reserves represent {scores.reserves_ratio:.2f}x annual paid claims — "
                "below industry benchmark of 1.0x."
            )

        if scores.liquidity_score >= 80:
            sentences.append(
                f"Current ratio of {scores.liquidity_ratio:.2f} indicates comfortable "
                "short-term financial flexibility."
            )
        elif scores.liquidity_score < 25:
            sentences.append(
                "Current liabilities exceed current assets — "
                "immediate liquidity pressure present."
            )

        return sentences
