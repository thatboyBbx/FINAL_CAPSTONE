from datetime import date
from statistics import mean

from app.modules.financials.model import FinancialSnapshot


class FinancialFeatureEngineer:
    """
    Computes engineered financial stress indicators
    over a rolling time window.
    """

    def __init__(self, snapshots: list[FinancialSnapshot]):
        if not snapshots:
            raise ValueError("No financial snapshots provided.")

        # Sort by date (oldest → newest)
        self.snapshots = sorted(snapshots, key=lambda s: s.reporting_date)

    def reserve_adequacy_index(self) -> float:
        reserves = [s.claims_reserves for s in self.snapshots]
        claims = [s.claims_paid for s in self.snapshots if s.claims_paid > 0]

        if not claims:
            return 0.0

        return mean(reserves) / mean(claims)

    def claims_pressure_indicator(self) -> float:
        total_claims = sum(s.claims_paid for s in self.snapshots)
        total_premiums = sum(s.premiums_written for s in self.snapshots)

        if total_premiums <= 0:
            return 0.0

        return total_claims / total_premiums

    def liquidity_stress_score(self) -> float:
        liquidity = [s.liquidity_ratio for s in self.snapshots if s.liquidity_ratio > 0]

        if not liquidity:
            return 0.0

        return 1.0 / mean(liquidity)

    def reserve_depletion_velocity(self) -> float:
        first = self.snapshots[0]
        last = self.snapshots[-1]

        days = (last.reporting_date - first.reporting_date).days
        if days <= 0:
            return 0.0

        return (last.claims_reserves - first.claims_reserves) / days

    def compute_feature_vector(self) -> dict:
        return {
            "reserve_adequacy_index": round(self.reserve_adequacy_index(), 4),
            "claims_pressure_indicator": round(self.claims_pressure_indicator(), 4),
            "liquidity_stress_score": round(self.liquidity_stress_score(), 4),
            "reserve_depletion_velocity": round(self.reserve_depletion_velocity(), 4),
        }
