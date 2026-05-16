from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import joblib
from sqlalchemy.orm import Session

from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier

from app.modules.insurers.repo import InsurerRepo
from app.modules.financials.repo import FinancialRepo
from app.modules.financials.features import FinancialFeatureEngineer
from app.modules.news.repo import NewsRepo
from app.modules.news.features import NewsFeatureEngineer
from app.modules.ml.text_classifier import get_circular_features, CIRCULAR_FEATURE_NAMES

from app.modules.ml.registry import model_path, save_meta
from app.modules.ml.labels import LabelConfig, make_label_provider


@dataclass
class TrainResult:
    meta: dict
    report: str


class MLTrainer:
    """
    PHASE 6 TRAINING (Two-mode) — Enhanced with Circular NLP Features

    (6A) DEMO MODE:
      - Profile: "demo"
      - Labels: Proxy labels (weak supervision)
      - Model Label: "DEMO: Settlement-Risk Classifier (Proxy-Labeled)"

    (6B) APP MODE:
      - Profile: "app"
      - Labels: Real labels from CSV
      - Model Label: "APP: Settlement-Risk Classifier (Real-Labeled)"

    Feature set (tabular + NLP):
      Financial features (4)  +  News features (6)  +  Circular NLP features (9)
      = 19 total features fed to GBDT / MLP ensemble
    """

    def __init__(self) -> None:
        self.insurer_repo = InsurerRepo()
        self.fin_repo     = FinancialRepo()
        self.news_repo    = NewsRepo()

        # Stable feature order across training & inference
        self.feature_names = [
            # Financial (4)
            "reserve_adequacy_index",
            "claims_pressure_indicator",
            "liquidity_stress_score",
            "reserve_depletion_velocity",
            # News NLP (6)
            "adverse_event_count",
            "settlement_event_count",
            "regulatory_event_count",
            "lawsuit_event_count",
            "catastrophe_event_count",
            "news_risk_score",
            # Circular DL NLP (9)
            *CIRCULAR_FEATURE_NAMES,
        ]

    def _build_feature_row(self, db: Session, insurer_id: int, days: int, circular_features: dict) -> dict | None:
        fin_snaps = self.fin_repo.list_last_days(db, insurer_id, days=days)
        if not fin_snaps:
            return None

        fin_features = FinancialFeatureEngineer(fin_snaps).compute_feature_vector()

        latest_fin = self.fin_repo.latest(db, insurer_id)
        if not latest_fin:
            return None

        end   = latest_fin.reporting_date
        start = end - timedelta(days=days)
        articles = self.news_repo.list_by_range(db, insurer_id, start=start, end=end)
        news_features = NewsFeatureEngineer(articles).compute()

        return {**fin_features, **news_features, **circular_features}

    def _choose_model(self, X, y) -> tuple[object, str]:
        """
        Model selection: GBDT primary (gradient boosted decision tree),
        Logistic Regression fallback for tiny datasets.
        Both are efficient tabular classifiers; the full pipeline also
        incorporates circular MLP deep learning features from the NLP stage.
        """
        n = len(X)
        if len(set(y)) < 2:
            raise ValueError("Training data has <2 classes. Add more insurers or adjust labels.")

        if n < 30:
            model = Pipeline(steps=[
                ("scaler", StandardScaler()),
                ("clf",    LogisticRegression(max_iter=4000, multi_class="auto")),
            ])
            return model, "Linear Model: Settlement-Risk Classifier (Logistic Regression)"

        model = HistGradientBoostingClassifier(
            max_depth=None,
            learning_rate=0.06,
            max_iter=400,
            random_state=42,
        )
        return model, "GBDT: Settlement-Risk Classifier (HistGradientBoosting + Circular-NLP)"

    def train(
        self,
        db: Session,
        profile: str,
        days: int = 90,
        test_size: float = 0.3,
        random_state: int = 42,
        labels_csv_path: str | None = None,
    ) -> TrainResult:
        label_provider, label_source = make_label_provider(
            LabelConfig(profile=profile, labels_csv_path=labels_csv_path)
        )

        model_label_profile = {
            "demo": "DEMO: Settlement-Risk Classifier (Proxy-Labeled)",
            "app":  "APP: Settlement-Risk Classifier (Real-Labeled)",
        }.get(profile, "UNKNOWN PROFILE")

        # Pre-compute system-wide circular features once (shared across insurers)
        circular_features = get_circular_features(db)

        insurers = self.insurer_repo.list(db, skip=0, limit=500)

        X, y = [], []

        for ins in insurers:
            row = self._build_feature_row(db, ins.id, days=days, circular_features=circular_features)
            if not row:
                continue

            try:
                lab = label_provider.label(ins.id, row)
            except Exception:
                if profile == "app":
                    continue
                raise

            X.append([float(row.get(f, 0.0)) for f in self.feature_names])
            y.append(int(lab))

        if len(X) < 5:
            raise ValueError(
                f"Not enough training rows ({len(X)}). Add more insurers/snapshots/news; "
                f"for app mode ensure labels exist for those insurers."
            )

        stratify = y if len(set(y)) > 1 else None

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=stratify
        )

        model, model_label = self._choose_model(X_train, y_train)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        acc    = accuracy_score(y_test, y_pred)
        report = classification_report(y_test, y_pred, digits=4)

        out = model_path(profile)
        joblib.dump(
            {
                "model":         model,
                "feature_names": self.feature_names,
                "model_label":   model_label,
                "profile_label": model_label_profile,
            },
            out,
        )

        metrics = {
            "accuracy":    float(acc),
            "rows":        len(X),
            "test_size":   float(test_size),
            "model_label": model_label,
        }
        meta = save_meta(profile, self.feature_names, metrics, label_source, model_label_profile)

        return TrainResult(meta=meta, report=report)
