"""
CSP XGBoost Anomaly Classifier.

Predicts whether an insurer is "at risk of claims settlement failure" based on
four core financial indicators plus year-on-year change rates.

Why XGBoost:
  - Handles class imbalance via iterative reweighting (scale_pos_weight)
  - Native SHAP integration for per-prediction explainability
  - Reproducible: fixed random_state=42
  - Generalises through ensembling while remaining tractable on a small dataset

Model is persisted to app/ml/models/csp_xgboost.joblib.
If the file is absent at startup, WCS-only fallback is used automatically.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib

logger = logging.getLogger(__name__)

MODEL_PATH = Path("app/ml/models/csp_xgboost.joblib")
MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

# Features used for training and inference
FEATURES: list[str] = [
    "solvency_ratio_pct",
    "settlement_capacity_months",
    "reserves_to_paid_ratio",
    "liquidity_ratio",
    "claims_ratio_pct",
    "solvency_ratio_yoy_change",
    "claims_reserves_yoy_change",
    "premiums_yoy_change",
]


class CSPXGBoostModel:
    """
    Thin wrapper around XGBClassifier for CSP anomaly detection.

    Call ``train`` to fit and persist a model.
    Call ``load`` on startup to load the persisted model.
    Use ``predict_risk`` and ``get_shap_explanation`` for inference.
    """

    def __init__(self) -> None:
        self.model: Any | None = None
        self._shap_explainer: Any | None = None

    # ── Training ──────────────────────────────────────────────────────────────

    def train(self, X: Any, y: Any) -> None:
        """
        Fit XGBClassifier on the provided feature matrix and binary labels.

        Args:
            X: pd.DataFrame with columns matching FEATURES.
            y: pd.Series of binary labels (1 = at risk, 0 = healthy).

        Saves the trained model to MODEL_PATH via joblib.
        """
        try:
            import xgboost as xgb

            n_negative = int((y == 0).sum())
            n_positive = int((y == 1).sum())
            scale_pos_weight = (n_negative / n_positive) if n_positive > 0 else 1.0

            self.model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                scale_pos_weight=scale_pos_weight,
                use_label_encoder=False,
                eval_metric="logloss",
                random_state=42,
                n_jobs=-1,
            )
            self.model.fit(X[FEATURES], y)
            joblib.dump(self.model, MODEL_PATH)
            logger.info("CSP XGBoost model trained and saved to %s", MODEL_PATH)

        except ImportError:
            logger.error("xgboost package not installed. Run: pip install xgboost>=2.0.0")
            raise
        except Exception as exc:
            logger.error("XGBoost training failed: %s", exc, exc_info=True)
            raise

    # ── Loading ───────────────────────────────────────────────────────────────

    def load(self) -> None:
        """
        Load the persisted XGBoost model from disk.

        If the model file is not found, logs a warning and sets self.model = None
        (WCS-only fallback will be used by CSPService).
        """
        if not MODEL_PATH.exists():
            logger.warning(
                "CSP XGBoost model not found at %s. "
                "WCS-only scoring will be used. "
                "Run the CSP training pipeline to enable anomaly detection.",
                MODEL_PATH,
            )
            return
        try:
            self.model = joblib.load(MODEL_PATH)
            logger.info("CSP XGBoost model loaded from %s", MODEL_PATH)
        except Exception as exc:
            logger.error("Failed to load CSP XGBoost model: %s", exc, exc_info=True)
            self.model = None

    # ── Inference ─────────────────────────────────────────────────────────────

    def predict_risk(self, features: dict[str, float]) -> tuple[float, bool]:
        """
        Predict at-risk probability and flag for a single insurer snapshot.

        Args:
            features: Dict mapping FEATURES names to float values.

        Returns:
            (probability, flag) where flag is True if probability > 0.5.
            Returns (0.0, False) if model is not loaded.
        """
        if self.model is None:
            return 0.0, False
        try:
            import pandas as pd

            df = pd.DataFrame([features])[FEATURES]
            prob = float(self.model.predict_proba(df)[0][1])
            return round(prob, 4), prob > 0.5
        except Exception as exc:
            logger.error("XGBoost prediction failed: %s", exc, exc_info=True)
            return 0.0, False

    def get_shap_explanation(self, features: dict[str, float]) -> dict[str, float]:
        """
        Compute SHAP feature contributions for a single prediction.

        Args:
            features: Dict mapping FEATURES names to float values.

        Returns:
            Dict of feature_name → SHAP contribution value.
            Returns empty dict if model or shap package is unavailable.
        """
        if self.model is None:
            return {}
        try:
            import pandas as pd
            import shap

            if self._shap_explainer is None:
                self._shap_explainer = shap.TreeExplainer(self.model)

            df = pd.DataFrame([features])[FEATURES]
            shap_values = self._shap_explainer.shap_values(df)

            # For binary classification, shap_values is shape (1, n_features)
            if hasattr(shap_values, "__len__") and len(shap_values) == 2:
                vals = shap_values[1][0]
            else:
                vals = shap_values[0]

            return {feat: round(float(vals[i]), 4) for i, feat in enumerate(FEATURES)}

        except ImportError:
            logger.warning("shap package not installed — SHAP explanations unavailable")
            return {}
        except Exception as exc:
            logger.error("SHAP computation failed: %s", exc, exc_info=True)
            return {}

    def shap_to_sentence(self, shap_dict: dict[str, float]) -> str:
        """
        Convert a SHAP contribution dict to a plain English sentence.

        Identifies the feature with the highest absolute SHAP value and
        generates a descriptive sentence.  Falls back to a diffuse-risk notice
        if no dominant signal (all |SHAP| < 0.1).

        Args:
            shap_dict: Feature → SHAP contribution mapping from get_shap_explanation.

        Returns:
            A single plain English sentence.
        """
        if not shap_dict:
            return ""

        dominant_feat = max(shap_dict, key=lambda k: abs(shap_dict[k]))
        dominant_val = shap_dict[dominant_feat]

        if abs(dominant_val) < 0.1:
            return (
                "No single dominant risk signal identified — "
                "risk is diffuse across multiple indicators."
            )

        sentences: dict[str, str] = {
            "solvency_ratio_yoy_change": (
                "Primary signal: solvency ratio has declined "
                f"{abs(dominant_val) * 100:.0f}% over the past year."
                if dominant_val < 0
                else "Primary signal: solvency ratio has improved materially year-on-year."
            ),
            "settlement_capacity_months": (
                "Primary signal: liquid asset coverage of claims has deteriorated."
                if dominant_val < 0
                else "Primary signal: liquid asset coverage of claims has strengthened."
            ),
            "reserves_to_paid_ratio": (
                "Primary signal: claims reserve adequacy has declined — "
                "IBNR provisions warrant closer review."
                if dominant_val < 0
                else "Primary signal: claims reserves have strengthened relative to paid claims."
            ),
            "liquidity_ratio": (
                "Primary signal: current ratio has deteriorated — "
                "short-term liquidity pressure is elevated."
                if dominant_val < 0
                else "Primary signal: current ratio improvement signals strengthened liquidity."
            ),
            "claims_ratio_pct": (
                "Primary signal: claims ratio has increased materially, "
                "compressing underwriting margins."
                if dominant_val < 0
                else "Primary signal: improving claims ratio indicates better underwriting performance."
            ),
            "claims_reserves_yoy_change": (
                "Primary signal: claims reserves have declined year-on-year — "
                "IBNR provisioning trend warrants monitoring."
                if dominant_val < 0
                else "Primary signal: claims reserves have grown year-on-year, "
                "improving provisioning adequacy."
            ),
            "premiums_yoy_change": (
                "Primary signal: gross written premiums have declined — "
                "market share or pricing pressure may be a factor."
                if dominant_val < 0
                else "Primary signal: premium growth is strong, expanding the capital base."
            ),
        }

        return sentences.get(
            dominant_feat,
            f"Primary signal: {dominant_feat.replace('_', ' ')} "
            f"({'negative' if dominant_val < 0 else 'positive'} contribution).",
        )
