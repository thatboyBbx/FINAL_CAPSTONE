from datetime import timedelta
import joblib
from sqlalchemy.orm import Session

from app.modules.ml.registry import load_meta
from app.modules.financials.repo import FinancialRepo
from app.modules.financials.features import FinancialFeatureEngineer
from app.modules.news.repo import NewsRepo
from app.modules.news.features import NewsFeatureEngineer
from app.modules.ml.text_classifier import get_circular_features


class MLPredictor:
    def __init__(self) -> None:
        self.fin_repo  = FinancialRepo()
        self.news_repo = NewsRepo()

    def _vector(self, db: Session, insurer_id: int, days: int, feature_names: list[str]) -> list[float]:
        fin_snaps = self.fin_repo.list_last_days(db, insurer_id, days=days)
        if not fin_snaps:
            raise ValueError("No financial snapshots found for insurer in window.")

        fin_features = FinancialFeatureEngineer(fin_snaps).compute_feature_vector()

        latest_fin = self.fin_repo.latest(db, insurer_id)
        if not latest_fin:
            raise ValueError("No financial data found to anchor news window.")

        end      = latest_fin.reporting_date
        start    = end - timedelta(days=days)
        articles = self.news_repo.list_by_range(db, insurer_id, start=start, end=end)
        news_features = NewsFeatureEngineer(articles).compute()

        # Circular NLP features (system-wide regulatory environment)
        circular_features = get_circular_features(db)

        row = {**fin_features, **news_features, **circular_features}
        return [float(row.get(f, 0.0)) for f in feature_names]

    def predict(self, db: Session, insurer_id: int, profile: str = "demo", days: int = 90) -> dict:
        meta = load_meta(profile)
        if not meta:
            raise ValueError(f"No trained model found for profile '{profile}'. Train it first.")

        bundle       = joblib.load(meta["model_path"])
        model        = bundle["model"]
        feature_names = bundle["feature_names"]

        model_label   = bundle.get("model_label",   "UNLABELED MODEL")
        profile_label = bundle.get("profile_label", meta.get("model_label", "UNLABELED PROFILE"))

        x = self._vector(db, insurer_id, days=days, feature_names=feature_names)

        pred  = int(model.predict([x])[0])
        probs = model.predict_proba([x])[0].tolist() if hasattr(model, "predict_proba") else []

        label_map = {0: "low", 1: "moderate", 2: "high"}

        return {
            "profile":          profile,
            "profile_label":    profile_label,
            "model_label":      model_label,
            "insurer_id":       insurer_id,
            "window_days":      days,
            "prediction_class": label_map.get(pred, str(pred)),
            "probabilities":    {
                "low":      probs[0] if len(probs) > 0 else None,
                "moderate": probs[1] if len(probs) > 1 else None,
                "high":     probs[2] if len(probs) > 2 else None,
            },
            "model_meta": meta,
        }
