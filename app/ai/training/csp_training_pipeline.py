"""
CSP XGBoost Training Pipeline.

Generates synthetic training data modelled on IPEC FSR-1 financial ratios,
trains the CSPXGBoostModel, and saves the artifact to disk.

Usage:
    python -m app.ai.training.csp_training_pipeline
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.ai.inference.csp_xgboost_model import CSPXGBoostModel, FEATURES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

RNG = np.random.default_rng(42)

N_HEALTHY = 160
N_AT_RISK = 40
N_TOTAL = N_HEALTHY + N_AT_RISK


def _generate_healthy() -> dict[str, np.ndarray]:
    n = N_HEALTHY
    return {
        "solvency_ratio_pct": RNG.normal(220, 30, n).clip(155, 400),
        "settlement_capacity_months": RNG.normal(4.5, 1.0, n).clip(2.5, 12),
        "reserves_to_paid_ratio": RNG.normal(1.5, 0.25, n).clip(1.05, 3.0),
        "liquidity_ratio": RNG.normal(1.8, 0.3, n).clip(1.1, 4.0),
        "claims_ratio_pct": RNG.normal(62, 6, n).clip(40, 74),
        "solvency_ratio_yoy_change": RNG.normal(5, 8, n).clip(-10, 30),
        "claims_reserves_yoy_change": RNG.normal(8, 10, n).clip(-15, 40),
        "premiums_yoy_change": RNG.normal(12, 8, n).clip(-5, 40),
        "_label": np.zeros(n, dtype=int),
    }


def _generate_at_risk() -> dict[str, np.ndarray]:
    n = N_AT_RISK
    return {
        "solvency_ratio_pct": RNG.normal(140, 20, n).clip(80, 155),
        "settlement_capacity_months": RNG.normal(1.2, 0.5, n).clip(0.1, 2.5),
        "reserves_to_paid_ratio": RNG.normal(0.6, 0.2, n).clip(0.1, 1.05),
        "liquidity_ratio": RNG.normal(0.85, 0.2, n).clip(0.3, 1.1),
        "claims_ratio_pct": RNG.normal(85, 10, n).clip(74, 120),
        "solvency_ratio_yoy_change": RNG.normal(-12, 8, n).clip(-35, 5),
        "claims_reserves_yoy_change": RNG.normal(-15, 10, n).clip(-40, 5),
        "premiums_yoy_change": RNG.normal(-8, 10, n).clip(-30, 10),
        "_label": np.ones(n, dtype=int),
    }


def build_training_dataframe() -> tuple[pd.DataFrame, pd.Series]:
    healthy = _generate_healthy()
    at_risk = _generate_at_risk()

    rows: dict[str, list] = {k: [] for k in [*FEATURES, "_label"]}
    for source in (healthy, at_risk):
        for key in rows:
            rows[key].extend(source[key].tolist())

    df = pd.DataFrame(rows)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    X = df[FEATURES].copy()
    y = df["_label"].copy()

    logger.info(
        "Training dataset: %d samples  |  %d healthy  |  %d at-risk",
        len(df),
        int((y == 0).sum()),
        int((y == 1).sum()),
    )
    return X, y


def run() -> int:
    print("\n" + "=" * 60)
    print("CSP XGBOOST FINANCIAL MODEL TRAINING")
    print("=" * 60)

    logger.info("Generating synthetic IPEC FSR-1 training data…")
    try:
        X, y = build_training_dataframe()
    except Exception as exc:
        logger.error("Failed to generate training data: %s", exc, exc_info=True)
        return 1

    model = CSPXGBoostModel()
    logger.info("Training XGBoost classifier…")
    try:
        model.train(X, y)
    except Exception as exc:
        logger.error("Training failed: %s", exc, exc_info=True)
        return 1

    model2 = CSPXGBoostModel()
    model2.load()
    if model2.model is None:
        logger.error("Model reload failed — file not written correctly.")
        return 1

    preds = model2.model.predict(X[FEATURES])
    accuracy = float((preds == y.values).mean())
    logger.info("Training accuracy: %.1f%%", accuracy * 100)

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"Samples      : {len(X)}  ({int((y==0).sum())} healthy / {int((y==1).sum())} at-risk)")
    print(f"Train accuracy: {accuracy * 100:.1f}%")
    print(f"Artifact path : app/ai/models/csp_xgboost.joblib")

    return 0


if __name__ == "__main__":
    sys.exit(run())
