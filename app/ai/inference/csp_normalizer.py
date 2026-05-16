"""
CSP Normalizer — maps raw financial figures to 0–100 scores.

Each indicator uses piecewise linear scaling anchored to IPEC regulatory
benchmarks and actuarial practice standards.  The general-purpose
``interpolate`` function is used for all four indicators.

Methodology Note (Chapter 3 — Model Design):
    Normalization anchors are grounded in regulatory thresholds where available
    (IPEC minimum solvency 150%) and actuarial practice standards where
    regulatory benchmarks are absent (e.g. 2-month liquid asset coverage
    adapted from Lloyd's minimum liquidity requirements for the Zimbabwean context).
"""
from __future__ import annotations


def interpolate(value: float, anchors: list[tuple[float, float]]) -> float:
    """
    Piecewise linear interpolation between anchor points.

    Args:
        value:   The raw financial metric value.
        anchors: Sorted list of (input_value, output_score) tuples.
                 Must have at least two entries.  Values outside the anchor
                 range are clamped to the minimum or maximum output score.

    Returns:
        A score between the minimum and maximum output scores defined by anchors.

    Example:
        >>> interpolate(175.0, [(100, 0), (150, 50), (200, 75), (250, 100)])
        62.5
    """
    if not anchors or len(anchors) < 2:
        raise ValueError("anchors must contain at least two (input, score) pairs")

    # Clamp below minimum anchor
    if value <= anchors[0][0]:
        return float(anchors[0][1])

    # Clamp above maximum anchor
    if value >= anchors[-1][0]:
        return float(anchors[-1][1])

    # Find the segment containing value
    for i in range(len(anchors) - 1):
        x0, y0 = anchors[i]
        x1, y1 = anchors[i + 1]
        if x0 <= value <= x1:
            # Linear interpolation within segment
            ratio = (value - x0) / (x1 - x0)
            return float(y0 + ratio * (y1 - y0))

    # Should be unreachable
    return float(anchors[-1][1])


# ─────────────────────────── Anchor tables ───────────────────────────────────
# Each list of tuples is (raw_value, normalised_score_0_to_100).

_SOLVENCY_ANCHORS: list[tuple[float, float]] = [
    (100.0, 0.0),    # below IPEC minimum → score = 0
    (150.0, 50.0),   # IPEC mandatory minimum
    (200.0, 75.0),
    (250.0, 100.0),
]

_SETTLEMENT_ANCHORS: list[tuple[float, float]] = [
    (1.0, 0.0),   # less than 1 month coverage → score = 0
    (2.0, 50.0),
    (4.0, 75.0),
    (6.0, 100.0),
]

_RESERVES_ANCHORS: list[tuple[float, float]] = [
    (0.5, 0.0),   # reserves < 50% of paid claims → score = 0
    (1.0, 50.0),
    (1.5, 75.0),
    (2.0, 100.0),
]

_LIQUIDITY_ANCHORS: list[tuple[float, float]] = [
    (1.0, 0.0),   # current ratio below 1.0 → score = 0
    (1.2, 50.0),
    (1.5, 75.0),
    (2.0, 100.0),
]


# ─────────────────────────── Public API ──────────────────────────────────────

def score_solvency(solvency_ratio_pct: float) -> float:
    """
    Convert solvency ratio (%) to a 0–100 score.

    Args:
        solvency_ratio_pct: e.g. 187.5 means 187.5%.

    Returns:
        Score 0–100.
    """
    return round(interpolate(solvency_ratio_pct, _SOLVENCY_ANCHORS), 2)


def score_settlement_capacity(
    liquid_assets_usd: float,
    gross_claims_paid_usd: float,
) -> float:
    """
    Convert liquid-asset coverage months to a 0–100 score.

    Derived metric: liquid_assets / (gross_claims_paid / 12) = months_coverage.

    Args:
        liquid_assets_usd:       Cash and short-term instruments only.
        gross_claims_paid_usd:   Annual gross claims paid.

    Returns:
        Score 0–100.  Returns 0.0 if gross_claims_paid_usd is zero.
    """
    if gross_claims_paid_usd <= 0:
        return 0.0
    months_coverage = liquid_assets_usd / (gross_claims_paid_usd / 12.0)
    return round(interpolate(months_coverage, _SETTLEMENT_ANCHORS), 2)


def score_reserves_adequacy(
    total_claims_reserves_usd: float,
    gross_claims_paid_usd: float,
) -> float:
    """
    Convert reserves-to-paid-claims ratio to a 0–100 score.

    Derived metric: total_claims_reserves / gross_claims_paid = reserves_ratio.

    Args:
        total_claims_reserves_usd: Outstanding + IBNR reserves.
        gross_claims_paid_usd:     Annual gross claims paid.

    Returns:
        Score 0–100.  Returns 0.0 if gross_claims_paid_usd is zero.
    """
    if gross_claims_paid_usd <= 0:
        return 0.0
    reserves_ratio = total_claims_reserves_usd / gross_claims_paid_usd
    return round(interpolate(reserves_ratio, _RESERVES_ANCHORS), 2)


def score_liquidity(
    current_assets_usd: float,
    current_liabilities_usd: float,
) -> float:
    """
    Convert current ratio to a 0–100 score.

    Args:
        current_assets_usd:      Total current assets.
        current_liabilities_usd: Total current liabilities.

    Returns:
        Score 0–100.  Returns 0.0 if current_liabilities_usd is zero.
    """
    if current_liabilities_usd <= 0:
        return 0.0
    liquidity_ratio = current_assets_usd / current_liabilities_usd
    return round(interpolate(liquidity_ratio, _LIQUIDITY_ANCHORS), 2)
