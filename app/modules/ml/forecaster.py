"""
Financial Time-Series Forecaster
==================================
Deep Learning (MLP / neural network) forecaster for insurance financial metrics.

Predicts the next-period values of key financial indicators:
  - claims_reserves
  - claims_paid
  - premiums_written
  - liquidity_ratio

Architecture:
  Input: lagged sequence of normalised financial snapshots (window=4 periods)
  → Dense(128, relu)
  → Dense(64, relu)
  → Dense(32, relu)
  → Dense(4, linear)   ← 4 output metrics

Implemented via sklearn.neural_network.MLPRegressor.
The model learns temporal patterns from the insurer's financial history.
"""
from __future__ import annotations

import joblib
from pathlib import Path
from datetime import timedelta

import numpy as np
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from sqlalchemy.orm import Session
from app.modules.financials.repo import FinancialRepo

_MODELS_DIR  = Path("app/storage/models")
_MODEL_FILE  = _MODELS_DIR / "financial_forecaster.joblib"

FORECAST_FEATURES = [
    "claims_reserves",
    "claims_paid",
    "premiums_written",
    "liquidity_ratio",
]

WINDOW = 4   # number of past periods to use as input


def _build_forecaster_pipeline() -> Pipeline:
    """3-layer MLP regressor for financial time-series prediction."""
    return Pipeline([
        ("scaler", StandardScaler()),
        ("mlp", MLPRegressor(
            hidden_layer_sizes=(128, 64, 32),
            activation="relu",
            solver="adam",
            alpha=1e-4,
            learning_rate="adaptive",
            max_iter=1000,
            early_stopping=True,
            validation_fraction=0.15,
            random_state=42,
            verbose=False,
        )),
    ])


class FinancialForecaster:
    """
    Neural network forecaster for insurer financial metrics.
    Uses a sliding-window approach: feeds the last WINDOW periods as input
    and predicts the next period's values.
    """

    def __init__(self) -> None:
        self._pipeline: Pipeline | None = None
        self._trained  = False
        self._load_if_exists()

    def _load_if_exists(self) -> None:
        if _MODEL_FILE.exists():
            try:
                bundle = joblib.load(_MODEL_FILE)
                self._pipeline = bundle["pipeline"]
                self._trained  = True
            except Exception:
                self._trained = False

    def is_trained(self) -> bool:
        return self._trained

    # ------------------------------------------------------------------
    def _snapshots_to_matrix(self, snapshots: list) -> np.ndarray:
        """Convert a list of FinancialSnapshot objects into a numeric matrix."""
        rows = []
        for s in snapshots:
            rows.append([
                float(s.claims_reserves),
                float(s.claims_paid),
                float(s.premiums_written),
                float(s.liquidity_ratio),
            ])
        return np.array(rows, dtype=np.float64)

    def _make_windows(self, matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Build (X, y) pairs from a time-ordered matrix using sliding windows.
        X = flattened window of WINDOW rows  →  y = next row
        """
        X, y = [], []
        for i in range(len(matrix) - WINDOW):
            X.append(matrix[i : i + WINDOW].flatten())
            y.append(matrix[i + WINDOW])
        return np.array(X), np.array(y)

    # ------------------------------------------------------------------
    def train(self, db: Session) -> dict:
        """
        Train the forecaster on ALL insurer financial snapshots in the DB.
        Requires at least WINDOW+1 snapshots across all insurers.
        """
        _MODELS_DIR.mkdir(parents=True, exist_ok=True)
        fin_repo = FinancialRepo()

        from app.modules.insurers.repo import InsurerRepo
        insurers = InsurerRepo().list(db, skip=0, limit=500)

        all_X, all_y = [], []

        for insurer in insurers:
            snaps = fin_repo.list_last_days(db, insurer.id, days=730)
            if len(snaps) < WINDOW + 1:
                continue
            snaps_sorted = sorted(snaps, key=lambda s: s.reporting_date)
            matrix = self._snapshots_to_matrix(snaps_sorted)
            X, y = self._make_windows(matrix)
            if len(X):
                all_X.append(X)
                all_y.append(y)

        if not all_X:
            return {
                "status": "error",
                "detail": f"Need at least {WINDOW+1} financial snapshots per insurer. Add more data.",
            }

        X_full = np.vstack(all_X)
        y_full = np.vstack(all_y)

        pipeline = _build_forecaster_pipeline()
        pipeline.fit(X_full, y_full)

        self._pipeline = pipeline
        self._trained  = True

        joblib.dump({"pipeline": pipeline}, _MODEL_FILE)

        return {
            "status": "trained",
            "n_windows": len(X_full),
            "n_insurers": len(all_X),
            "input_features": WINDOW * len(FORECAST_FEATURES),
            "output_features": len(FORECAST_FEATURES),
            "architecture": f"MLP({WINDOW*4}→128→64→32→{len(FORECAST_FEATURES)})",
            "model_file": str(_MODEL_FILE),
        }

    # ------------------------------------------------------------------
    def predict(self, db: Session, insurer_id: int) -> dict:
        """
        Predict next-period financial metrics for a given insurer.
        """
        if not self._trained or self._pipeline is None:
            return {
                "status": "untrained",
                "detail": "Train the forecaster first via POST /ml/train-forecaster.",
            }

        fin_repo = FinancialRepo()
        snaps = fin_repo.list_last_days(db, insurer_id, days=365)

        if len(snaps) < WINDOW:
            return {
                "status": "insufficient_data",
                "detail": f"Need at least {WINDOW} financial snapshots. Found {len(snaps)}.",
            }

        snaps_sorted = sorted(snaps, key=lambda s: s.reporting_date)[-WINDOW:]
        matrix = self._snapshots_to_matrix(snaps_sorted)
        x = matrix.flatten().reshape(1, -1)

        y_pred = self._pipeline.predict(x)[0]

        latest_date = snaps_sorted[-1].reporting_date
        predicted_date = latest_date + timedelta(days=91)   # ~next quarter

        predictions = {feat: round(float(y_pred[i]), 2) for i, feat in enumerate(FORECAST_FEATURES)}

        # Derive risk trajectory from predicted vs latest actual
        latest = snaps_sorted[-1]
        reserve_change = predictions["claims_reserves"] - float(latest.claims_reserves)
        loss_ratio_pred = (predictions["claims_paid"] / max(predictions["premiums_written"], 1))

        if loss_ratio_pred >= 1.0 or reserve_change < -10000:
            trajectory = "deteriorating"
        elif loss_ratio_pred >= 0.85 or reserve_change < 0:
            trajectory = "stable_risk"
        else:
            trajectory = "improving"

        return {
            "status": "ok",
            "insurer_id": insurer_id,
            "predicted_period": str(predicted_date),
            "predictions": predictions,
            "risk_trajectory": trajectory,
            "predicted_loss_ratio": round(loss_ratio_pred, 4),
            "reserve_change": round(reserve_change, 2),
            "model": f"DeepLearning-MLP({WINDOW*4}→128→64→32→4)",
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_forecaster: FinancialForecaster | None = None


def get_forecaster() -> FinancialForecaster:
    global _forecaster
    if _forecaster is None:
        _forecaster = FinancialForecaster()
    return _forecaster
