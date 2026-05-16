"""
Time-decay weighting for risk signals.

More recent data has higher influence on the final risk score.
Uses exponential decay: weight = exp(-lambda * age_days)

Half-life defaults:
  - Financial data: 90 days (quarterly)
  - News articles:  30 days (news is stale fast)
  - Circulars:     180 days (regulatory circulars stay relevant longer)
"""
from __future__ import annotations

import math
from datetime import date, timedelta


def exponential_weight(age_days: int, half_life_days: int) -> float:
    """
    Return e^(-lambda * age_days) where lambda = ln(2) / half_life_days.
    Result is in (0, 1]: weight=1 when age=0, weight=0.5 when age=half_life.
    """
    if age_days <= 0:
        return 1.0
    lam = math.log(2) / max(half_life_days, 1)
    return math.exp(-lam * age_days)


def decay_weight(reference_date: date, data_date: date, half_life_days: int) -> float:
    age = (reference_date - data_date).days
    return exponential_weight(age, half_life_days)


class TimeDecayConfig:
    financial_half_life: int = 90
    news_half_life: int      = 30
    circular_half_life: int  = 180


def apply_decay_to_scores(
    scores_with_dates: list[tuple[float, date]],
    reference_date: date,
    half_life_days: int,
) -> float:
    """
    Compute a time-decay weighted average of (score, date) pairs.

    Args:
        scores_with_dates: list of (score, date) tuples
        reference_date:   the 'now' reference (usually today or latest data date)
        half_life_days:   decay half-life in days

    Returns:
        Weighted average score (float), or 0.0 if no data.
    """
    if not scores_with_dates:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0

    for score, data_date in scores_with_dates:
        w = decay_weight(reference_date, data_date, half_life_days)
        weighted_sum += w * score
        total_weight += w

    if total_weight == 0:
        return 0.0

    return round(weighted_sum / total_weight, 4)
