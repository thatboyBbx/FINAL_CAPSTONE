"""
Train the CSP XGBoost financial distress classifier.

Delegates to app.ml.csp_training_pipeline which generates synthetic IPEC FSR-1
training data and trains an XGBClassifier with SHAP support.

Usage:
    python scripts/train_xgboost_financial_model.py

Prerequisites:
    pip install xgboost>=2.0.0 shap pandas numpy joblib

Output:
    app/ml/models/csp_xgboost.joblib
"""
import sys
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.csp_training_pipeline import run

if __name__ == "__main__":
    sys.exit(run())
