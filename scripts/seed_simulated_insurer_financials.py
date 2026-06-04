"""
Seed simulated insurer financials for UI and CSP dashboards.

This is deterministic and idempotent for the generated period labels. It updates
or inserts rows for every insurer, then refreshes CSP scores from the latest
simulated insurer_financials row.
"""
from __future__ import annotations

import random
from datetime import date
from decimal import Decimal

import app.main  # noqa: F401  Ensures all SQLAlchemy models are registered.
from app.core.db import SessionLocal
from app.modules.csp.model import CSPScore
from app.modules.csp.service import CSPService
from app.modules.financials.model import FinancialSnapshot, InsurerFinancials
from app.modules.insurers.model import Insurer

RNG = random.Random(20260602)
DATA_SOURCE = "Simulated insurer financials v1"

PERIODS = [
    (2024, 1, date(2024, 3, 31)),
    (2024, 2, date(2024, 6, 30)),
    (2024, 3, date(2024, 9, 30)),
    (2024, 4, date(2024, 12, 31)),
    (2025, 1, date(2025, 3, 31)),
    (2025, 2, date(2025, 6, 30)),
    (2025, 3, date(2025, 9, 30)),
    (2025, 4, date(2025, 12, 31)),
]

PROFILE_BY_CATEGORY = {
    "short_term": (7_500_000, 0.66, 1.65, 175.0),
    "life_assurance": (11_000_000, 0.52, 2.05, 220.0),
    "reinsurer": (16_000_000, 0.58, 2.35, 245.0),
    "funeral_assurer": (3_500_000, 0.48, 1.55, 165.0),
    "microinsurer": (950_000, 0.42, 1.35, 150.0),
    "broker": (1_750_000, 0.36, 1.25, 135.0),
    "multiple_agent": (1_250_000, 0.34, 1.18, 130.0),
    "underwriting_agent": (2_000_000, 0.44, 1.32, 145.0),
}

SIZE_MULTIPLIER_BY_NAME = {
    "old mutual": 3.4,
    "cbz": 2.8,
    "first mutual": 2.7,
    "fbc": 2.4,
    "zimnat": 2.2,
    "nyaradzo": 2.1,
    "fidelity": 1.9,
    "doves": 1.8,
    "econet": 1.7,
    "zb": 1.6,
}


def _money(value: float) -> Decimal:
    return Decimal(str(round(max(value, 0.0), 2)))


def _ratio(value: float, places: int = 4) -> Decimal:
    return Decimal(str(round(max(value, 0.0), places)))


def _size_multiplier(name: str) -> float:
    lower = name.lower()
    for needle, multiplier in SIZE_MULTIPLIER_BY_NAME.items():
        if needle in lower:
            return multiplier
    return RNG.uniform(0.75, 1.35)


def _period_label(year: int, quarter: int) -> str:
    return f"{year}Q{quarter}"


def _upsert_snapshot(db, insurer: Insurer, payload: dict) -> None:
    row = (
        db.query(FinancialSnapshot)
        .filter(
            FinancialSnapshot.insurer_id == insurer.id,
            FinancialSnapshot.period_label == payload["period_label"],
            FinancialSnapshot.period_type == "quarterly",
        )
        .first()
    )
    if row is None:
        row = FinancialSnapshot(insurer_id=insurer.id, period_type="quarterly")
        db.add(row)

    for key, value in payload.items():
        setattr(row, key, value)


def _upsert_insurer_financials(db, insurer: Insurer, payload: dict) -> str:
    row = (
        db.query(InsurerFinancials)
        .filter(
            InsurerFinancials.insurer_id == insurer.id,
            InsurerFinancials.period_type == "quarterly",
            InsurerFinancials.period_year == payload["period_year"],
            InsurerFinancials.period_quarter == payload["period_quarter"],
        )
        .first()
    )
    if row is None:
        row = InsurerFinancials(insurer_id=insurer.id, period_type="quarterly")
        db.add(row)

    for key, value in payload.items():
        setattr(row, key, value)

    db.flush()
    return row.id


def seed() -> dict:
    db = SessionLocal()
    try:
        insurers = db.query(Insurer).order_by(Insurer.id).all()
        financial_ids: list[str] = []

        for insurer in insurers:
            base_premium, claims_ratio, liquidity, solvency = PROFILE_BY_CATEGORY.get(
                insurer.category or "short_term",
                PROFILE_BY_CATEGORY["short_term"],
            )
            size = _size_multiplier(insurer.name)
            premium_base = base_premium * size * RNG.uniform(0.85, 1.2)
            reserve_base = premium_base * RNG.uniform(0.55, 1.35)

            for index, (year, quarter, reporting_date) in enumerate(PERIODS):
                growth = 1 + (index * RNG.uniform(0.015, 0.045))
                seasonal = [0.92, 1.0, 1.06, 1.14][quarter - 1]
                premium = premium_base * growth * seasonal * RNG.uniform(0.92, 1.08)
                paid_claims = premium * claims_ratio * RNG.uniform(0.85, 1.18)
                reserves = reserve_base * growth * RNG.uniform(0.9, 1.16)
                liquid_assets = paid_claims / 3 * liquidity * RNG.uniform(0.92, 1.14)
                current_liabilities = max(paid_claims / 2.5, 50_000)
                current_assets = current_liabilities * liquidity * RNG.uniform(0.92, 1.12)
                solvency_ratio = solvency + RNG.uniform(-22, 28) + index * RNG.uniform(-1.0, 2.8)
                total_assets = premium * RNG.uniform(1.8, 3.4)
                total_liabilities = total_assets * RNG.uniform(0.35, 0.78)
                capital = total_assets - total_liabilities
                min_capital = max(capital / max(solvency_ratio / 100, 0.1), 100_000)
                claims_ratio_pct = (paid_claims / premium) * 100 if premium else 0
                period_label = _period_label(year, quarter)

                _upsert_snapshot(
                    db,
                    insurer,
                    {
                        "reporting_date": reporting_date,
                        "period_label": period_label,
                        "currency": "USD",
                        "claims_reserves": float(reserves),
                        "claims_paid": float(paid_claims),
                        "premiums_written": float(premium),
                        "liquidity_ratio": float(liquidity),
                        "total_revenue_usd": _money(premium * RNG.uniform(0.92, 1.08)),
                        "insurance_revenue_usd": _money(premium),
                        "profit_after_tax_usd": _money(premium * RNG.uniform(0.04, 0.18)),
                        "investment_income_usd": _money(premium * RNG.uniform(0.02, 0.12)),
                        "total_assets_usd": _money(total_assets),
                        "total_liabilities_usd": _money(total_liabilities),
                        "capital_position_usd": _money(capital),
                        "minimum_capital_requirement_usd": _money(min_capital),
                        "capital_adequacy_ratio": _ratio(solvency_ratio / 100),
                        "market_share_pct": _ratio(RNG.uniform(0.001, 0.065)),
                        "prescribed_assets_pct": _ratio(RNG.uniform(0.08, 0.32)),
                        "reinsurance_assets_pct": _ratio(RNG.uniform(0.03, 0.28)),
                        "property_assets_pct": _ratio(RNG.uniform(0.02, 0.24)),
                        "cash_and_bank_pct": _ratio(RNG.uniform(0.08, 0.38)),
                        "data_source": DATA_SOURCE,
                    },
                )

                financial_ids.append(
                    _upsert_insurer_financials(
                        db,
                        insurer,
                        {
                            "period_year": year,
                            "period_quarter": quarter,
                            "total_assets_usd": _money(total_assets),
                            "total_liabilities_usd": _money(total_liabilities),
                            "solvency_margin_usd": _money(capital),
                            "solvency_ratio_pct": _ratio(solvency_ratio, 2),
                            "ipec_minimum_solvency_pct": _ratio(150.0, 2),
                            "gross_claims_paid_usd": _money(paid_claims),
                            "outstanding_claims_reserve": _money(reserves * 0.78),
                            "ibnr_reserve_usd": _money(reserves * 0.22),
                            "total_claims_reserves_usd": _money(reserves),
                            "claims_ratio_pct": _ratio(claims_ratio_pct, 2),
                            "current_assets_usd": _money(current_assets),
                            "current_liabilities_usd": _money(current_liabilities),
                            "liquidity_ratio": _ratio(current_assets / current_liabilities),
                            "liquid_assets_usd": _money(liquid_assets),
                            "gross_premiums_written_usd": _money(premium),
                            "net_premiums_earned_usd": _money(premium * RNG.uniform(0.72, 0.9)),
                            "data_source": DATA_SOURCE,
                            "source_url": None,
                            "extraction_confidence": 1.0,
                        },
                    )
                )

        if financial_ids:
            db.query(CSPScore).filter(CSPScore.financials_id.in_(financial_ids)).delete(
                synchronize_session=False
            )
        db.commit()

        refreshed = CSPService().refresh_all_scores(db)
        return {
            "status": "ok",
            "insurers": len(insurers),
            "periods": len(PERIODS),
            "financial_rows": len(financial_ids),
            "csp_scores_refreshed": refreshed,
            "data_source": DATA_SOURCE,
        }
    finally:
        db.close()


if __name__ == "__main__":
    print(seed())
