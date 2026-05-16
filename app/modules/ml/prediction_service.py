"""
app/modules/ml/prediction_service.py
======================================
Demo settlement risk prediction. Moved from app/services/prediction_service.py.
"""
from app.modules.ml.training_service import load_demo_model_bundle


def predict_demo_settlement_risk(
    insurer: str,
    policy_type: str,
    claim_amount: float,
    premium: float,
    risk_score: float,
    vehicle_value: int,
) -> dict:
    bundle = load_demo_model_bundle()
    model = bundle["model"]
    vectorizer = bundle["vectorizer"]
    metadata = bundle["metadata"]

    payload = [
        {
            "insurer": insurer,
            "policy_type": policy_type,
            "claim_amount": float(claim_amount),
            "premium": float(premium),
            "risk_score": float(risk_score),
            "vehicle_value": int(vehicle_value),
        }
    ]

    X = vectorizer.transform(payload)
    prediction = int(model.predict(X)[0])
    probability = float(model.predict_proba(X)[0][1])

    risk_label = "HIGH" if prediction == 1 else "LOW"

    if probability >= 0.75:
        expected_window = "30–45 days"
    elif probability >= 0.50:
        expected_window = "20–35 days"
    else:
        expected_window = "7–20 days"

    return {
        "status": "ok",
        "prediction": prediction,
        "risk_label": risk_label,
        "delay_probability": round(probability, 4),
        "expected_settlement_window": expected_window,
        "model_name": metadata["model_name"],
        "metrics": metadata["metrics"],
    }
