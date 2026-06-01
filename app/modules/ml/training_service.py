"""
app/modules/ml/training_service.py
====================================
Demo settlement risk model — training and loading.
Moved from app/services/model_training_service.py.
"""
import json
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

from app.infrastructure.storage.dataset_registry import DatasetRegistry


registry = DatasetRegistry()

MODEL_FILENAME = "demo_settlement_model.joblib"
VECTORIZER_FILENAME = "demo_settlement_vectorizer.joblib"
METADATA_FILENAME = "demo_settlement_model_metadata.json"


def _get_model_dir() -> Path:
    model_dir = registry.get_model_dir("demo")
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


def _get_model_path() -> Path:
    return _get_model_dir() / MODEL_FILENAME


def _get_vectorizer_path() -> Path:
    return _get_model_dir() / VECTORIZER_FILENAME


def _get_metadata_path() -> Path:
    return _get_model_dir() / METADATA_FILENAME


def _build_training_data() -> tuple[list[dict], list[int]]:
    rows: list[dict] = []

    feature_rows: list[dict] = []
    target_rows: list[int] = []

    for row in rows:
        feature_rows.append(
            {
                "insurer": row["insurer"],
                "policy_type": row["policy_type"],
                "claim_amount": float(row["claim_amount"]),
                "premium": float(row["premium"]),
                "risk_score": float(row["risk_score"]),
                "vehicle_value": int(row["vehicle_value"]),
            }
        )
        delayed = 1 if int(row["settlement_days"]) >= 25 else 0
        target_rows.append(delayed)

    return feature_rows, target_rows


def train_demo_model() -> dict:
    feature_rows, target_rows = _build_training_data()

    if len(feature_rows) < 20:
        raise ValueError("Not enough demo rows to train the model.")

    vectorizer = DictVectorizer(sparse=False)
    X = vectorizer.fit_transform(feature_rows)
    y = target_rows

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=250,
        max_depth=10,
        min_samples_split=4,
        min_samples_leaf=2,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy":  round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "recall":    round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "f1_score":  round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        "roc_auc":   round(float(roc_auc_score(y_test, y_prob)), 4),
    }

    joblib.dump(model, _get_model_path())
    joblib.dump(vectorizer, _get_vectorizer_path())

    metadata = {
        "model_name": "demo_settlement_delay_random_forest",
        "mode": "demo",
        "target": "delayed_settlement_risk",
        "threshold_rule": "settlement_days >= 25",
        "feature_count": int(X.shape[1]),
        "training_rows": len(X_train),
        "test_rows": len(X_test),
        "metrics": metrics,
        "model_path": str(_get_model_path()).replace("\\", "/"),
        "vectorizer_path": str(_get_vectorizer_path()).replace("\\", "/"),
    }

    with _get_metadata_path().open("w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2)

    return {"status": "ok", "message": "Demo model trained successfully.", "metadata": metadata}


def load_demo_model_bundle() -> dict:
    model_path = _get_model_path()
    vectorizer_path = _get_vectorizer_path()
    metadata_path = _get_metadata_path()

    if not model_path.exists():
        raise FileNotFoundError("Demo model file not found.")
    if not vectorizer_path.exists():
        raise FileNotFoundError("Demo vectorizer file not found.")
    if not metadata_path.exists():
        raise FileNotFoundError("Demo metadata file not found.")

    model = joblib.load(model_path)
    vectorizer = joblib.load(vectorizer_path)

    with metadata_path.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    return {"model": model, "vectorizer": vectorizer, "metadata": metadata}
