"""
Synthetic training data generator for CSP/WCS risk scoring and XGBoost anomaly detection.
Produces 1500 rows of realistic Zimbabwean insurer financial snapshots.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

SAVE_PATH = Path(__file__).parent / "insurance_synthetic.csv"

ZIMBABWEAN_INSURERS: list[str] = [
    "Zimnat General Insurance",
    "Zimnat Life Assurance",
    "Old Mutual Zimbabwe",
    "Old Mutual Life Assurance Zimbabwe",
    "First Mutual Life",
    "First Mutual Health",
    "Fidelity Life Assurance",
    "Fidelity Life Zimbabwe",
    "CABS Insurance",
    "Sanctuary Insurance",
    "Nicoz Diamond Insurance",
    "Cell Insurance",
    "RM Insurance",
    "RM Life Zimbabwe",
    "Moonlight Insurance",
    "Minerva Risk Advisors",
    "Tristar Insurance",
    "Heritage Insurance",
    "Heritage Life Assurance",
    "ZB Life Assurance",
    "ZB Bank Insurance",
    "FBC Insurance",
    "CBZ Life",
    "Alliance Insurance",
    "NicozDiamond Brokers",
]

INSURER_TYPES: list[str] = ["life", "general", "composite", "reinsurer"]

STRESS_SCENARIOS = [
    "high_claims_low_solvency",
    "declining_premium_low_reserves",
    "low_compliance_low_solvency",
    "regulatory_breach",
]

RNG = np.random.default_rng(42)
random.seed(42)

N_TOTAL = 1500
N_ANOMALY = 120
N_NORMAL = N_TOTAL - N_ANOMALY


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _derive_wcs_score(
    solvency_ratio: float,
    claims_ratio: float,
    reserve_adequacy: float,
    liquidity_ratio: float,
) -> float:
    return (
        0.35 * min(solvency_ratio / 1.5, 1.0)
        + 0.30 * max(1.0 - claims_ratio, 0.0)
        + 0.20 * min(reserve_adequacy / 1.0, 1.0)
        + 0.15 * min(liquidity_ratio / 1.5, 1.0)
    )


def _wcs_to_label(wcs: float) -> str:
    if wcs >= 0.75:
        return "strong"
    elif wcs >= 0.55:
        return "adequate"
    elif wcs >= 0.35:
        return "watch"
    else:
        return "distressed"


def _is_anomaly(
    claims_ratio: float,
    solvency_ratio: float,
    premium_growth: float,
    reserve_adequacy: float,
    compliance_score: float,
) -> bool:
    if claims_ratio > 0.95 and solvency_ratio < 0.90:
        return True
    if premium_growth < -0.25 and reserve_adequacy < 0.60:
        return True
    if compliance_score < 0.60 and solvency_ratio < 1.0:
        return True
    if solvency_ratio < 0.70:
        return True
    return False


def _generate_normal_rows(n: int) -> list[dict]:
    rows = []
    for _ in range(n):
        solvency_ratio = _clip(float(RNG.normal(1.45, 0.35)), 0.5, 3.0)
        # beta-distributed claims ratio, skewed right
        claims_ratio = _clip(float(RNG.beta(2.5, 1.8) * 1.1), 0.1, 1.2)
        premium_growth = _clip(float(RNG.normal(0.08, 0.18)), -0.40, 0.60)
        reserve_adequacy = _clip(float(RNG.normal(0.88, 0.15)), 0.3, 1.5)
        liquidity_ratio = _clip(float(RNG.normal(1.25, 0.30)), 0.4, 2.5)
        compliance_score = float(RNG.uniform(0.50, 1.00))
        policy_count = int(_clip(int(RNG.lognormal(mean=np.log(4500), sigma=0.8)), 200, 50000))
        year = random.randint(2018, 2024)
        quarter = random.randint(1, 4)

        # ensure not anomaly — regenerate if it would be
        if _is_anomaly(claims_ratio, solvency_ratio, premium_growth, reserve_adequacy, compliance_score):
            solvency_ratio = _clip(float(RNG.normal(1.60, 0.20)), 0.95, 3.0)
            claims_ratio = _clip(float(RNG.beta(2.0, 2.0) * 0.90), 0.10, 0.94)
            compliance_score = float(RNG.uniform(0.62, 1.00))

        wcs = _derive_wcs_score(solvency_ratio, claims_ratio, reserve_adequacy, liquidity_ratio)
        risk_label = _wcs_to_label(wcs)
        anomaly_flag = 0

        rows.append({
            "insurer_name": random.choice(ZIMBABWEAN_INSURERS),
            "insurer_type": random.choice(INSURER_TYPES),
            "solvency_ratio": round(solvency_ratio, 4),
            "claims_ratio": round(claims_ratio, 4),
            "premium_growth": round(premium_growth, 4),
            "reserve_adequacy": round(reserve_adequacy, 4),
            "liquidity_ratio": round(liquidity_ratio, 4),
            "compliance_score": round(compliance_score, 4),
            "policy_count": policy_count,
            "year": year,
            "quarter": quarter,
            "risk_label": risk_label,
            "anomaly_flag": anomaly_flag,
        })
    return rows


def _generate_anomaly_row(scenario: str) -> dict:
    year = random.randint(2018, 2024)
    quarter = random.randint(1, 4)
    policy_count = int(_clip(int(RNG.lognormal(mean=np.log(2000), sigma=0.6)), 200, 20000))
    compliance_score = float(RNG.uniform(0.50, 1.00))
    premium_growth = _clip(float(RNG.normal(0.08, 0.18)), -0.40, 0.60)
    reserve_adequacy = _clip(float(RNG.normal(0.88, 0.15)), 0.3, 1.5)
    liquidity_ratio = _clip(float(RNG.normal(1.25, 0.30)), 0.4, 2.5)
    solvency_ratio = _clip(float(RNG.normal(1.45, 0.35)), 0.5, 3.0)
    claims_ratio = _clip(float(RNG.beta(2.5, 1.8) * 1.1), 0.1, 1.2)

    if scenario == "high_claims_low_solvency":
        claims_ratio = _clip(float(RNG.uniform(0.96, 1.20)), 0.96, 1.20)
        solvency_ratio = _clip(float(RNG.uniform(0.50, 0.89)), 0.50, 0.89)
    elif scenario == "declining_premium_low_reserves":
        premium_growth = _clip(float(RNG.uniform(-0.40, -0.26)), -0.40, -0.26)
        reserve_adequacy = _clip(float(RNG.uniform(0.30, 0.59)), 0.30, 0.59)
    elif scenario == "low_compliance_low_solvency":
        compliance_score = _clip(float(RNG.uniform(0.50, 0.59)), 0.50, 0.59)
        solvency_ratio = _clip(float(RNG.uniform(0.70, 0.99)), 0.70, 0.99)
    elif scenario == "regulatory_breach":
        solvency_ratio = _clip(float(RNG.uniform(0.50, 0.69)), 0.50, 0.69)

    wcs = _derive_wcs_score(solvency_ratio, claims_ratio, reserve_adequacy, liquidity_ratio)
    risk_label = _wcs_to_label(wcs)

    return {
        "insurer_name": random.choice(ZIMBABWEAN_INSURERS),
        "insurer_type": random.choice(INSURER_TYPES),
        "solvency_ratio": round(solvency_ratio, 4),
        "claims_ratio": round(claims_ratio, 4),
        "premium_growth": round(premium_growth, 4),
        "reserve_adequacy": round(reserve_adequacy, 4),
        "liquidity_ratio": round(liquidity_ratio, 4),
        "compliance_score": round(compliance_score, 4),
        "policy_count": policy_count,
        "year": year,
        "quarter": quarter,
        "risk_label": risk_label,
        "anomaly_flag": 1,
    }


def generate() -> pd.DataFrame:
    normal_rows = _generate_normal_rows(N_NORMAL)
    anomaly_rows = [
        _generate_anomaly_row(random.choice(STRESS_SCENARIOS))
        for _ in range(N_ANOMALY)
    ]
    all_rows = normal_rows + anomaly_rows
    df = pd.DataFrame(all_rows)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    return df


if __name__ == "__main__":
    df = generate()

    SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SAVE_PATH, index=False)

    dist = df["risk_label"].value_counts()
    print(f"Generated: {len(df)} rows")
    print(f"Anomalies: {int(df['anomaly_flag'].sum())} flagged")
    print("Risk distribution:")
    for label in ["strong", "adequate", "watch", "distressed"]:
        count = int(dist.get(label, 0))
        print(f"  {label:<12}: {count} rows")
    print(f"Saved to: {SAVE_PATH}")
