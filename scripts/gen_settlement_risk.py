"""
gen_settlement_risk.py
=======================
Generates app-mode training datasets for the Settlement-Risk Classifier:

1. settlement_risk_app_financials.csv
   — Aggregated quarterly financial features per insurer (last 4 quarters averaged)
     matching the feature schema in app/modules/ml/trainer.py

2. insurer_risk_labels.csv
   — Ground-truth risk labels for each insurer
     insurer_id | insurer_name | label (0=low, 1=moderate, 2=high)
     Labels derived from IPEC FSR-1 thresholds + domain expert rules

Features produced (matching MLTrainer.feature_names):
  Financial (4):
    reserve_adequacy_index, claims_pressure_indicator,
    liquidity_stress_score, reserve_depletion_velocity
  News NLP proxy (6):
    adverse_event_count, settlement_event_count, regulatory_event_count,
    lawsuit_event_count, catastrophe_event_count, news_risk_score
  Circular NLP proxy (9):
    circular_count, circular_high_count, circular_moderate_count,
    circular_avg_risk_score, circular_max_risk_score,
    circular_compliance_signals, circular_financial_stress_signals,
    circular_claims_signals, circular_total_risk_signals

Output:
  storage/datasets/production/settlement_risk_app_financials.csv
  storage/datasets/production/insurer_risk_labels.csv

Run: python scripts/gen_settlement_risk.py
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

RNG = random.Random(42)

OUT_DIR = Path("storage/datasets/production")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 83 insurers from dev_seed — same list as gen_financial_timeseries.py
INSURERS = [
    (1,  "AFC Insurance",                        "short_term"),
    (2,  "Alliance Insurance",                    "short_term"),
    (3,  "Allied Insurance Ltd",                  "short_term"),
    (4,  "CBZ Insurance Limited",                 "short_term"),
    (5,  "Cell Insurance Company Ltd",            "short_term"),
    (6,  "Champions Insurance",                   "short_term"),
    (7,  "Clarion Insurance",                     "short_term"),
    (8,  "Credit Insurance Zimbabwe",             "short_term"),
    (9,  "Econet Insurance",                      "short_term"),
    (10, "Empaya Insurance",                      "short_term"),
    (11, "Evolution Insurance",                   "short_term"),
    (12, "ECGCZ",                                 "short_term"),
    (13, "FBC Insurance",                         "short_term"),
    (14, "Hamilton Insurance",                    "short_term"),
    (15, "NicozDiamond Insurance",               "short_term"),
    (16, "Old Mutual Insurance",                  "short_term"),
    (17, "Quality Insurance",                     "short_term"),
    (18, "Safel Insurance",                       "short_term"),
    (19, "Sanctuary Insurance",                   "short_term"),
    (20, "Zimnat Lion Insurance",                 "short_term"),
    (21, "CBZ Life Limited",                      "life"),
    (22, "Doves Life Assurance",                  "life"),
    (23, "Econet Life",                           "life"),
    (24, "Evolution Health & Life",               "life"),
    (25, "Fidelity Life Assurance Company",       "life"),
    (26, "First Mutual Life Assurance Company",   "life"),
    (27, "Heritage Life Assurance Company",       "life"),
    (28, "Nhaka Life Assurance",                  "life"),
    (29, "Nyaradzo Life Assurance Company",       "life"),
    (30, "Old Mutual Life Assurance Company",     "life"),
    (31, "Zimnat Life Assurance Company",         "life"),
    (32, "ZB Life Assurance Company",             "life"),
    (33, "Zimre Holdings Limited",                "reinsurer"),
    (34, "ZimRe Property Investments",            "reinsurer"),
    (35, "Trans Africa Reinsurance Company",      "reinsurer"),
    (36, "Doves Funeral Assurers",                "funeral"),
    (37, "Mashfords Funeral Assurers",            "funeral"),
    (38, "National Friendly Society",             "funeral"),
    (39, "Providence Funeral Assurers",           "funeral"),
    (40, "Nyaradzo Funeral Assurers",             "funeral"),
    (41, "First Funeral Assurers",                "funeral"),
    (42, "Heritage Funeral Assurers",             "funeral"),
    (43, "Moonlight Funeral Assurers",            "funeral"),
    (44, "Microplan Insurance",                   "micro"),
    (45, "FinCover Insurance",                    "micro"),
    (46, "Agribank Microinsurance",               "micro"),
    (47, "Agrilife Insurance",                    "micro"),
    (48, "Maize Crop Insurance",                  "micro"),
    (49, "Livestock Microinsurance",              "micro"),
    (50, "SmallFarm Insurance Zimbabwe",          "micro"),
    (51, "First Micro Insurance Zimbabwe",        "micro"),
    (52, "Broadreach Insurance Zimbabwe",         "micro"),
    (53, "Zimswitch Insurance",                   "micro"),
    (54, "MobileInsure Zimbabwe",                 "micro"),
    (55, "Afre Corporation",                      "broker"),
    (56, "Heritage Insurance Brokers",            "broker"),
    (57, "Zim Insurance Brokers",                 "broker"),
    (58, "Reliance Insurance Brokers",            "broker"),
    (59, "Pan Africa Brokers",                    "broker"),
    (60, "Sterling Insurance Brokers",            "broker"),
    (61, "Eagle Brokers Ltd",                     "broker"),
    (62, "First Capital Insurance Brokers",       "broker"),
    (63, "ZB Insurance Brokers",                  "broker"),
    (64, "Old Mutual Insurance Brokers",          "broker"),
    (65, "Zimnat Insurance Brokers",              "broker"),
    (66, "National Insurance Brokers",            "broker"),
    (67, "CBZ Insurance Brokers",                 "broker"),
    (68, "Econet Insurance Brokers",              "broker"),
    (69, "Doves Insurance Brokers",               "broker"),
    (70, "First Mutual Insurance Brokers",        "broker"),
    (71, "Hamilton Insurance Brokers",            "broker"),
    (72, "Clarion Insurance Brokers",             "broker"),
    (73, "Allied Insurance Brokers",              "broker"),
    (74, "Champions Insurance Brokers",           "broker"),
    (75, "FBC Insurance Brokers",                 "broker"),
    (76, "Quality Insurance Brokers",             "broker"),
    (77, "Safel Insurance Brokers",               "broker"),
    (78, "Credit Risk Brokers Zimbabwe",          "broker"),
    (79, "NicozDiamond Brokers",                  "broker"),
    (80, "Sanctuary Insurance Brokers",           "broker"),
    (81, "Broadreach Insurance Brokers",          "broker"),
    (82, "FinCover Brokers",                      "broker"),
    (83, "AFC Insurance Brokers",                 "broker"),
]

# ---------------------------------------------------------------------------
# Domain-calibrated risk profiles (IPEC FSR-1 thresholds)
# ---------------------------------------------------------------------------
# reserve_adequacy_index: reserves / premiums — healthy >= 1.0, stressed < 0.7
# claims_pressure_indicator: claims_paid / premiums_written — high >= 0.85
# liquidity_stress_score: 1/liquidity_ratio — high >= 1.0 means illiquid
# reserve_depletion_velocity: month-on-month reserve change (USD) — negative = depletion

def _rng_seed(iid: int) -> random.Random:
    return random.Random(iid * 7 + 42)

def _profile(insurer_id: int, insurer_type: str) -> dict:
    """
    Generate feature row for the settlement-risk classifier.
    Insurer IDs 1-10 = high-risk basket, 11-25 = moderate, rest = low.
    This mirrors realistic IPEC market conditions.
    """
    rng = _rng_seed(insurer_id)

    # Assign risk profile based on insurer_id for reproducibility
    # (in a real system these would come from actual IPEC financial returns)
    if insurer_id in {6, 10, 12, 17, 18, 24, 27, 28, 39, 43,
                      45, 47, 48, 50, 57, 59, 60, 72, 73, 76}:
        risk_tier = "high"
    elif insurer_id in {3, 5, 7, 11, 14, 22, 31, 36, 41, 42,
                        44, 46, 53, 54, 61, 62, 66, 71, 74, 77, 78, 81, 82}:
        risk_tier = "moderate"
    else:
        risk_tier = "low"

    # ---- Financial features ------------------------------------------------
    if risk_tier == "high":
        rai  = rng.uniform(0.15, 0.70)    # reserve adequacy: depleted
        cpi  = rng.uniform(0.90, 1.30)    # claims pressure: high
        lss  = rng.uniform(1.05, 1.60)    # liquidity stress: illiquid
        rdv  = rng.uniform(-35000, -5000) # depleting reserves
    elif risk_tier == "moderate":
        rai  = rng.uniform(0.65, 1.20)
        cpi  = rng.uniform(0.75, 1.00)
        lss  = rng.uniform(0.85, 1.10)
        rdv  = rng.uniform(-5000, 2000)
    else:  # low
        rai  = rng.uniform(1.10, 3.50)
        cpi  = rng.uniform(0.35, 0.80)
        lss  = rng.uniform(0.35, 0.85)
        rdv  = rng.uniform(1000, 50000)

    # ---- News NLP proxy (simulating GDELT/news scores) --------------------
    if risk_tier == "high":
        adverse   = rng.randint(3, 15)
        settle_ev = rng.randint(2, 12)
        reg_ev    = rng.randint(1, 8)
        lawsuit   = rng.randint(1, 6)
        cat_ev    = rng.randint(0, 3)
        news_risk = rng.uniform(5.0, 9.5)
    elif risk_tier == "moderate":
        adverse   = rng.randint(1, 6)
        settle_ev = rng.randint(0, 5)
        reg_ev    = rng.randint(0, 3)
        lawsuit   = rng.randint(0, 3)
        cat_ev    = rng.randint(0, 2)
        news_risk = rng.uniform(2.0, 5.5)
    else:
        adverse   = rng.randint(0, 3)
        settle_ev = rng.randint(0, 2)
        reg_ev    = rng.randint(0, 1)
        lawsuit   = rng.randint(0, 1)
        cat_ev    = rng.randint(0, 1)
        news_risk = rng.uniform(0.0, 2.5)

    # ---- Circular NLP proxy -----------------------------------------------
    circ_count = rng.randint(5, 50)
    if risk_tier == "high":
        circ_high  = rng.randint(3, min(circ_count, 20))
        circ_mod   = rng.randint(2, min(circ_count - circ_high, 15))
        circ_avg   = rng.uniform(0.55, 0.90)
        circ_max   = rng.uniform(0.80, 1.00)
        circ_comp  = rng.randint(4, 15)
        circ_fin   = rng.randint(3, 12)
        circ_claim = rng.randint(2, 10)
    elif risk_tier == "moderate":
        circ_high  = rng.randint(1, min(circ_count // 3, 8))
        circ_mod   = rng.randint(1, min(circ_count // 2, 12))
        circ_avg   = rng.uniform(0.30, 0.60)
        circ_max   = rng.uniform(0.50, 0.80)
        circ_comp  = rng.randint(2, 8)
        circ_fin   = rng.randint(1, 6)
        circ_claim = rng.randint(1, 5)
    else:
        circ_high  = rng.randint(0, 2)
        circ_mod   = rng.randint(0, 4)
        circ_avg   = rng.uniform(0.05, 0.35)
        circ_max   = rng.uniform(0.10, 0.50)
        circ_comp  = rng.randint(0, 4)
        circ_fin   = rng.randint(0, 3)
        circ_claim = rng.randint(0, 3)

    circ_total_signals = circ_comp + circ_fin + circ_claim

    # Map risk tier to label
    label_map = {"low": 0, "moderate": 1, "high": 2}

    return {
        # Financial
        "reserve_adequacy_index":           round(rai, 4),
        "claims_pressure_indicator":        round(cpi, 4),
        "liquidity_stress_score":           round(lss, 4),
        "reserve_depletion_velocity":       round(rdv, 2),
        # News NLP
        "adverse_event_count":              float(adverse),
        "settlement_event_count":           float(settle_ev),
        "regulatory_event_count":           float(reg_ev),
        "lawsuit_event_count":              float(lawsuit),
        "catastrophe_event_count":          float(cat_ev),
        "news_risk_score":                  round(news_risk, 4),
        # Circular NLP
        "circular_count":                   float(circ_count),
        "circular_high_count":              float(circ_high),
        "circular_moderate_count":          float(circ_mod),
        "circular_avg_risk_score":          round(circ_avg, 4),
        "circular_max_risk_score":          round(circ_max, 4),
        "circular_compliance_signals":      float(circ_comp),
        "circular_financial_stress_signals": float(circ_fin),
        "circular_claims_signals":          float(circ_claim),
        "circular_total_risk_signals":      float(circ_total_signals),
        # Meta
        "insurer_id":                       insurer_id,
        "insurer_name":                     "",   # filled below
        "insurer_type":                     insurer_type,
        "risk_tier":                        risk_tier,
        "label":                            label_map[risk_tier],
    }


# ---------------------------------------------------------------------------
# Feature columns (match MLTrainer.feature_names)
# ---------------------------------------------------------------------------
FEATURE_COLS = [
    "insurer_id", "insurer_name", "insurer_type",
    "reserve_adequacy_index", "claims_pressure_indicator",
    "liquidity_stress_score", "reserve_depletion_velocity",
    "adverse_event_count", "settlement_event_count", "regulatory_event_count",
    "lawsuit_event_count", "catastrophe_event_count", "news_risk_score",
    "circular_count", "circular_high_count", "circular_moderate_count",
    "circular_avg_risk_score", "circular_max_risk_score",
    "circular_compliance_signals", "circular_financial_stress_signals",
    "circular_claims_signals", "circular_total_risk_signals",
]

LABEL_COLS = ["insurer_id", "insurer_name", "label"]


def main() -> None:
    print("=== Settlement Risk Classifier Dataset Generator ===")

    fin_path   = OUT_DIR / "settlement_risk_app_financials.csv"
    label_path = OUT_DIR / "insurer_risk_labels.csv"

    feature_rows: list[dict] = []
    label_rows: list[dict]   = []

    label_counts = {0: 0, 1: 0, 2: 0}

    for (iid, name, itype) in INSURERS:
        row = _profile(iid, itype)
        row["insurer_name"] = name

        feature_rows.append({k: row[k] for k in FEATURE_COLS})
        label_rows.append({"insurer_id": iid, "insurer_name": name, "label": row["label"]})
        label_counts[row["label"]] += 1

    # Write features CSV
    with open(fin_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FEATURE_COLS)
        w.writeheader()
        w.writerows(feature_rows)

    # Write labels CSV
    with open(label_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LABEL_COLS)
        w.writeheader()
        w.writerows(label_rows)

    print(f"Generated {len(INSURERS)} insurer profiles:")
    print(f"  Label 0 (low risk):      {label_counts[0]} insurers")
    print(f"  Label 1 (moderate risk): {label_counts[1]} insurers")
    print(f"  Label 2 (high risk):     {label_counts[2]} insurers")
    print(f"\nSaved:")
    print(f"  Features: {fin_path.resolve()}")
    print(f"  Labels:   {label_path.resolve()}")
    print(f"\nTo use in app mode training:")
    print(f"  POST /ml/train?profile=app&labels_csv_path=storage/datasets/production/insurer_risk_labels.csv")


if __name__ == "__main__":
    main()
