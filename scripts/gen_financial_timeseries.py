"""
gen_financial_timeseries.py
============================
Generates a production-quality multi-year quarterly financial time series for
all IPEC-licensed Zimbabwean insurers.

Covers 83 entities × 20 quarters (Q1 2020 – Q4 2024) = 1,660 rows minimum.
Models realistic Zimbabwe insurance market dynamics:
  - COVID-19 impact (Q1–Q3 2020): premium compression, claims spike
  - ZWL currency devaluation (2021–2022): FX volatility reflected in USD-equivalent reporting
  - Post-dollarisation stabilisation (2023–2024): steady premium growth, improving solvency
  - Class-specific dynamics (short-term vs life vs reinsurance vs funeral vs micro)

Output columns:
  insurer_name, insurer_type, reporting_date, quarter,
  claims_reserves, claims_paid, premiums_written, liquidity_ratio,
  solvency_ratio, combined_ratio, loss_ratio, expense_ratio,
  policy_count, investment_income

Output: storage/datasets/production/financial_forecaster_timeseries.csv

Run:    python scripts/gen_financial_timeseries.py
"""
from __future__ import annotations

import csv
import math
import random
from datetime import date
from pathlib import Path

RNG = random.Random(42)

OUT_DIR = Path("storage/datasets/production")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Full insurer roster (83 entities matching dev_seed.py)
# ---------------------------------------------------------------------------
INSURERS: list[dict] = [
    # Short-term (20)
    {"name": "AFC Insurance",                              "type": "short_term",  "size": "small"},
    {"name": "Alliance Insurance",                         "type": "short_term",  "size": "small"},
    {"name": "Allied Insurance Ltd",                       "type": "short_term",  "size": "small"},
    {"name": "CBZ Insurance Limited",                      "type": "short_term",  "size": "large"},
    {"name": "Cell Insurance Company Ltd",                 "type": "short_term",  "size": "small"},
    {"name": "Champions Insurance",                        "type": "short_term",  "size": "small"},
    {"name": "Clarion Insurance",                          "type": "short_term",  "size": "small"},
    {"name": "Credit Insurance Zimbabwe",                  "type": "short_term",  "size": "small"},
    {"name": "Econet Insurance",                           "type": "short_term",  "size": "medium"},
    {"name": "Empaya Insurance",                           "type": "short_term",  "size": "small"},
    {"name": "Evolution Insurance",                        "type": "short_term",  "size": "small"},
    {"name": "ECGCZ",                                      "type": "short_term",  "size": "small"},
    {"name": "FBC Insurance",                              "type": "short_term",  "size": "large"},
    {"name": "Hamilton Insurance",                         "type": "short_term",  "size": "small"},
    {"name": "NicozDiamond Insurance",                     "type": "short_term",  "size": "large"},
    {"name": "Old Mutual Insurance",                       "type": "short_term",  "size": "large"},
    {"name": "Quality Insurance",                          "type": "short_term",  "size": "small"},
    {"name": "Safel Insurance",                            "type": "short_term",  "size": "small"},
    {"name": "Sanctuary Insurance",                        "type": "short_term",  "size": "small"},
    {"name": "Zimnat Lion Insurance",                      "type": "short_term",  "size": "medium"},
    # Life assurers (12)
    {"name": "CBZ Life Limited",                           "type": "life",        "size": "large"},
    {"name": "Doves Life Assurance",                       "type": "life",        "size": "medium"},
    {"name": "Econet Life",                                "type": "life",        "size": "medium"},
    {"name": "Evolution Health & Life",                    "type": "life",        "size": "small"},
    {"name": "Fidelity Life Assurance Company",            "type": "life",        "size": "large"},
    {"name": "First Mutual Life Assurance Company",        "type": "life",        "size": "large"},
    {"name": "Heritage Life Assurance Company",            "type": "life",        "size": "small"},
    {"name": "Nhaka Life Assurance",                       "type": "life",        "size": "small"},
    {"name": "Nyaradzo Life Assurance Company",            "type": "life",        "size": "large"},
    {"name": "Old Mutual Life Assurance Company",          "type": "life",        "size": "large"},
    {"name": "Zimnat Life Assurance Company",              "type": "life",        "size": "medium"},
    {"name": "ZB Life Assurance Company",                  "type": "life",        "size": "medium"},
    # Reinsurers (3)
    {"name": "Zimre Holdings Limited",                     "type": "reinsurer",   "size": "large"},
    {"name": "ZimRe Property Investments",                 "type": "reinsurer",   "size": "medium"},
    {"name": "Trans Africa Reinsurance Company",           "type": "reinsurer",   "size": "medium"},
    # Funeral assurers (8)
    {"name": "Doves Funeral Assurers",                     "type": "funeral",     "size": "large"},
    {"name": "Mashfords Funeral Assurers",                 "type": "funeral",     "size": "medium"},
    {"name": "National Friendly Society",                  "type": "funeral",     "size": "medium"},
    {"name": "Providence Funeral Assurers",                "type": "funeral",     "size": "small"},
    {"name": "Nyaradzo Funeral Assurers",                  "type": "funeral",     "size": "large"},
    {"name": "First Funeral Assurers",                     "type": "funeral",     "size": "small"},
    {"name": "Heritage Funeral Assurers",                  "type": "funeral",     "size": "small"},
    {"name": "Moonlight Funeral Assurers",                 "type": "funeral",     "size": "small"},
    # Microinsurers (11)
    {"name": "Microplan Insurance",                        "type": "micro",       "size": "small"},
    {"name": "FinCover Insurance",                         "type": "micro",       "size": "small"},
    {"name": "Agribank Microinsurance",                    "type": "micro",       "size": "small"},
    {"name": "Agrilife Insurance",                         "type": "micro",       "size": "small"},
    {"name": "Maize Crop Insurance",                       "type": "micro",       "size": "small"},
    {"name": "Livestock Microinsurance",                   "type": "micro",       "size": "small"},
    {"name": "SmallFarm Insurance Zimbabwe",               "type": "micro",       "size": "small"},
    {"name": "First Micro Insurance Zimbabwe",             "type": "micro",       "size": "small"},
    {"name": "Broadreach Insurance Zimbabwe",              "type": "micro",       "size": "small"},
    {"name": "Zimswitch Insurance",                        "type": "micro",       "size": "small"},
    {"name": "MobileInsure Zimbabwe",                      "type": "micro",       "size": "small"},
    # Brokers with underwriting function (29 — represented as brokerage entities)
    {"name": "Afre Corporation",                           "type": "broker",      "size": "large"},
    {"name": "Heritage Insurance Brokers",                 "type": "broker",      "size": "medium"},
    {"name": "Zim Insurance Brokers",                      "type": "broker",      "size": "small"},
    {"name": "Reliance Insurance Brokers",                 "type": "broker",      "size": "medium"},
    {"name": "Pan Africa Brokers",                         "type": "broker",      "size": "small"},
    {"name": "Sterling Insurance Brokers",                 "type": "broker",      "size": "small"},
    {"name": "Eagle Brokers Ltd",                          "type": "broker",      "size": "small"},
    {"name": "First Capital Insurance Brokers",            "type": "broker",      "size": "medium"},
    {"name": "ZB Insurance Brokers",                       "type": "broker",      "size": "medium"},
    {"name": "Old Mutual Insurance Brokers",               "type": "broker",      "size": "large"},
    {"name": "Zimnat Insurance Brokers",                   "type": "broker",      "size": "medium"},
    {"name": "National Insurance Brokers",                 "type": "broker",      "size": "small"},
    {"name": "CBZ Insurance Brokers",                      "type": "broker",      "size": "large"},
    {"name": "Econet Insurance Brokers",                   "type": "broker",      "size": "medium"},
    {"name": "Doves Insurance Brokers",                    "type": "broker",      "size": "medium"},
    {"name": "First Mutual Insurance Brokers",             "type": "broker",      "size": "large"},
    {"name": "Hamilton Insurance Brokers",                 "type": "broker",      "size": "small"},
    {"name": "Clarion Insurance Brokers",                  "type": "broker",      "size": "small"},
    {"name": "Allied Insurance Brokers",                   "type": "broker",      "size": "small"},
    {"name": "Champions Insurance Brokers",                "type": "broker",      "size": "small"},
    {"name": "FBC Insurance Brokers",                      "type": "broker",      "size": "medium"},
    {"name": "Quality Insurance Brokers",                  "type": "broker",      "size": "small"},
    {"name": "Safel Insurance Brokers",                    "type": "broker",      "size": "small"},
    {"name": "Credit Risk Brokers Zimbabwe",               "type": "broker",      "size": "small"},
    {"name": "NicozDiamond Brokers",                       "type": "broker",      "size": "large"},
    {"name": "Sanctuary Insurance Brokers",                "type": "broker",      "size": "small"},
    {"name": "Broadreach Insurance Brokers",               "type": "broker",      "size": "small"},
    {"name": "FinCover Brokers",                           "type": "broker",      "size": "small"},
    {"name": "AFC Insurance Brokers",                      "type": "broker",      "size": "small"},
]

# ---------------------------------------------------------------------------
# Base premium ranges by type + size (annual USD)
# ---------------------------------------------------------------------------
BASE_PREMIUMS = {
    # (type, size): (min, max)
    ("short_term", "small"):   (400_000,   3_000_000),
    ("short_term", "medium"):  (3_000_000, 15_000_000),
    ("short_term", "large"):   (15_000_000, 80_000_000),
    ("life",       "small"):   (600_000,   4_000_000),
    ("life",       "medium"):  (4_000_000, 20_000_000),
    ("life",       "large"):   (20_000_000, 100_000_000),
    ("reinsurer",  "medium"):  (8_000_000, 40_000_000),
    ("reinsurer",  "large"):   (40_000_000, 200_000_000),
    ("funeral",    "small"):   (500_000,   2_500_000),
    ("funeral",    "medium"):  (2_500_000, 12_000_000),
    ("funeral",    "large"):   (12_000_000, 50_000_000),
    ("micro",      "small"):   (80_000,    500_000),
    ("broker",     "small"):   (50_000,    300_000),  # brokers: net commission income
    ("broker",     "medium"):  (300_000,   1_500_000),
    ("broker",     "large"):   (1_500_000, 8_000_000),
}

# ---------------------------------------------------------------------------
# Quarterly date sequence Q1-2020 to Q4-2024 (20 quarters)
# ---------------------------------------------------------------------------
QUARTERS: list[tuple[str, date]] = []
for yr in range(2020, 2025):
    for qn, mo in [(1, 3), (2, 6), (3, 9), (4, 12)]:
        QUARTERS.append((f"Q{qn} {yr}", date(yr, mo, 30 if mo in (6, 9) else 31 if mo == 3 else 31)))

# Macro market multipliers per quarter (captures COVID, currency, growth shocks)
# Values represent premium income relative to a stable baseline of 1.0
MACRO_FACTOR: dict[str, float] = {
    "Q1 2020": 0.92,  # COVID onset — new business slows
    "Q2 2020": 0.78,  # Lockdown — severe premium compression
    "Q3 2020": 0.83,  # Partial recovery
    "Q4 2020": 0.90,  # Year-end push
    "Q1 2021": 0.95,  # USD shortage, ZWL devaluation pressures
    "Q2 2021": 1.00,  # Base
    "Q3 2021": 1.05,
    "Q4 2021": 1.08,
    "Q1 2022": 1.10,  # Currency reform period — nominal growth
    "Q2 2022": 1.15,
    "Q3 2022": 1.12,
    "Q4 2022": 1.18,
    "Q1 2023": 1.22,  # ZiG introduction — stabilisation
    "Q2 2023": 1.28,
    "Q3 2023": 1.32,
    "Q4 2023": 1.38,
    "Q1 2024": 1.40,
    "Q2 2024": 1.45,
    "Q3 2024": 1.48,
    "Q4 2024": 1.52,
}

# COVID claims surge multiplier
CLAIMS_SURGE: dict[str, float] = {
    "Q2 2020": 1.35,  # COVID surge — large claims
    "Q3 2020": 1.20,
    "Q4 2020": 1.10,
}

# ---------------------------------------------------------------------------
# Per-insurer seed generator
# ---------------------------------------------------------------------------

def _insurer_seed(name: str) -> int:
    """Deterministic seed per insurer for reproducibility."""
    return sum(ord(c) for c in name) % 10000


def generate_insurer_series(ins: dict) -> list[dict]:
    """
    Generate 20 quarters of financial data for a single insurer.
    Each quarter's data realistically depends on the prior quarter.
    """
    rng = random.Random(_insurer_seed(ins["name"]) + 42)

    itype = ins["type"]
    size  = ins["size"]
    key   = (itype, size) if (itype, size) in BASE_PREMIUMS else ("short_term", "small")

    # Annual premium at baseline (2021 full year equivalent)
    annual_base_prem = rng.uniform(*BASE_PREMIUMS[key])
    quarterly_base_prem = annual_base_prem / 4.0

    # Per-insurer character (slight bias toward healthy or stressed)
    stress_level = rng.uniform(0, 1)        # 0 = very healthy, 1 = stressed
    is_stressed   = stress_level > 0.80     # ~20% of insurers are stressed
    is_moderate   = 0.60 < stress_level <= 0.80  # ~20% moderate

    # Claims ratio baseline by type
    claims_ratio_base = {
        "short_term": rng.uniform(0.52, 0.72),
        "life":        rng.uniform(0.35, 0.60),
        "reinsurer":   rng.uniform(0.50, 0.75),
        "funeral":     rng.uniform(0.42, 0.62),
        "micro":       rng.uniform(0.45, 0.68),
        "broker":      rng.uniform(0.20, 0.40),  # brokers: commission / GWP
    }.get(itype, 0.60)

    if is_stressed:
        claims_ratio_base = min(claims_ratio_base * 1.3, 0.98)
    elif is_moderate:
        claims_ratio_base = min(claims_ratio_base * 1.15, 0.88)

    # Reserve ratio (reserves / premiums_written): typically 1.0–3.0
    reserve_ratio_base = rng.uniform(0.8, 2.5)
    if is_stressed:
        reserve_ratio_base = rng.uniform(0.3, 0.9)

    # Solvency ratio baseline
    solvency_ratio_base = {
        True:  rng.uniform(0.90, 1.30),   # stressed
        False: rng.uniform(1.40, 3.20),   # healthy
    }[is_stressed]

    # Liquidity ratio
    liquidity_base = rng.uniform(0.85, 1.10) if is_stressed else rng.uniform(1.20, 2.80)

    # Policy count baseline
    policy_count_base = {
        ("short_term", "small"):  rng.randint(500, 3000),
        ("short_term", "medium"): rng.randint(3000, 15000),
        ("short_term", "large"):  rng.randint(15000, 80000),
        ("life",       "small"):  rng.randint(1000, 8000),
        ("life",       "medium"): rng.randint(8000, 40000),
        ("life",       "large"):  rng.randint(40000, 200000),
        ("reinsurer",  "medium"): rng.randint(50, 300),
        ("reinsurer",  "large"):  rng.randint(300, 1500),
        ("funeral",    "small"):  rng.randint(2000, 15000),
        ("funeral",    "medium"): rng.randint(15000, 70000),
        ("funeral",    "large"):  rng.randint(70000, 500000),
        ("micro",      "small"):  rng.randint(500, 8000),
        ("broker",     "small"):  rng.randint(100, 2000),
        ("broker",     "medium"): rng.randint(2000, 10000),
        ("broker",     "large"):  rng.randint(10000, 50000),
    }.get(key, rng.randint(500, 5000))

    rows: list[dict] = []

    # Rolling state variables for temporal coherence
    prev_reserves = quarterly_base_prem * reserve_ratio_base
    prev_liquidity = liquidity_base
    prev_solvency  = solvency_ratio_base

    for quarter_label, quarter_date in QUARTERS:
        macro = MACRO_FACTOR.get(quarter_label, 1.0)
        claims_surge = CLAIMS_SURGE.get(quarter_label, 1.0)

        # Add quarterly noise
        noise = rng.uniform(-0.06, 0.06)

        premiums_written = max(
            quarterly_base_prem * macro * (1 + noise),
            10_000.0,
        )

        # Claims paid — correlated with premiums, with surge
        eff_claims_ratio = claims_ratio_base * claims_surge * rng.uniform(0.88, 1.12)
        eff_claims_ratio = max(0.15, min(eff_claims_ratio, 1.20))
        claims_paid = premiums_written * eff_claims_ratio

        # Reserves — mean-reverting with drift
        target_reserves = premiums_written * reserve_ratio_base * rng.uniform(0.90, 1.10)
        # Stressed insurers see reserves deplete over time
        if is_stressed:
            target_reserves *= max(0.5, 1.0 - 0.015 * QUARTERS.index((quarter_label, quarter_date)))
        claims_reserves = 0.7 * prev_reserves + 0.3 * target_reserves
        claims_reserves = max(claims_reserves, 10_000.0)

        # Liquidity — slowly mean-reverting
        liquidity_shock = rng.uniform(-0.08, 0.08)
        if quarter_label in ("Q2 2020", "Q3 2020"):
            liquidity_shock -= 0.15   # COVID liquidity stress
        liquidity_ratio = max(0.50, prev_liquidity + liquidity_shock)
        liquidity_ratio = round(min(liquidity_ratio, 5.0), 3)

        # Solvency — slowly drifts based on profitability
        profit_factor = 1.0 if eff_claims_ratio < 0.80 else 0.98
        solvency_drift = rng.uniform(-0.05, 0.07) * profit_factor
        solvency_ratio = max(0.70, prev_solvency * (1 + solvency_drift))
        solvency_ratio = round(min(solvency_ratio, 5.0), 3)

        # Expense ratio (steady, slight improvement over time)
        expense_ratio = rng.uniform(0.22, 0.42) if itype != "broker" else rng.uniform(0.50, 0.80)
        combined_ratio = eff_claims_ratio + expense_ratio

        # Investment income (~3-7% of total assets proxy)
        investment_income = max(0, premiums_written * rng.uniform(0.03, 0.10))

        # Policy count — slowly growing
        qtr_idx = QUARTERS.index((quarter_label, quarter_date))
        growth_rate = 1.0 + 0.015 * qtr_idx * macro  # ~6% annual growth
        policy_count = int(policy_count_base * growth_rate * rng.uniform(0.95, 1.05))

        rows.append({
            "insurer_name":     ins["name"],
            "insurer_type":     itype,
            "quarter":          quarter_label,
            "reporting_date":   quarter_date.isoformat(),
            "premiums_written": round(premiums_written, 2),
            "claims_paid":      round(claims_paid, 2),
            "claims_reserves":  round(claims_reserves, 2),
            "liquidity_ratio":  liquidity_ratio,
            "solvency_ratio":   solvency_ratio,
            "loss_ratio":       round(eff_claims_ratio, 4),
            "expense_ratio":    round(expense_ratio, 4),
            "combined_ratio":   round(combined_ratio, 4),
            "investment_income": round(investment_income, 2),
            "policy_count":     policy_count,
        })

        # Update rolling state
        prev_reserves  = claims_reserves
        prev_liquidity = liquidity_ratio
        prev_solvency  = solvency_ratio

    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
FIELDNAMES = [
    "insurer_name", "insurer_type", "quarter", "reporting_date",
    "premiums_written", "claims_paid", "claims_reserves",
    "liquidity_ratio", "solvency_ratio", "loss_ratio",
    "expense_ratio", "combined_ratio", "investment_income", "policy_count",
]


def main() -> None:
    print("=== Financial Forecaster Time Series Generator ===")
    out_path = OUT_DIR / "financial_forecaster_timeseries.csv"

    all_rows: list[dict] = []
    for ins in INSURERS:
        series = generate_insurer_series(ins)
        all_rows.extend(series)
        print(f"  {ins['name']:<50} {len(series)} quarters")

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(all_rows)

    print(f"\nTotal rows: {len(all_rows)}")
    print(f"Insurers: {len(INSURERS)} | Quarters: {len(QUARTERS)}")
    print(f"Saved to: {out_path.resolve()}")

    # Quick validation
    prem_values = [r["premiums_written"] for r in all_rows]
    print(f"\nPremium range: USD {min(prem_values):,.0f} – {max(prem_values):,.0f} (quarterly)")
    solvency_vals = [r["solvency_ratio"] for r in all_rows]
    below_min = sum(1 for v in solvency_vals if v < 1.0)
    print(f"Rows with solvency < 100% (at-risk): {below_min} ({100*below_min/len(all_rows):.1f}%)")


if __name__ == "__main__":
    main()
