"""
Train document classification model.

Uses TF-IDF + Logistic Regression — lightweight, fast, and interpretable.

Performance targets:
  Accuracy:      >85%
  Training time: <1 minute on CPU
  Inference:     <100ms per document

Usage:
  python scripts/generate_classification_training_data.py   # first
  python scripts/train_document_classifier.py               # then this
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import cross_val_score, train_test_split

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRAINING_DATA_DIR = Path("storage/training_data")
MODEL_DIR = Path("storage/models/app")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


class DocumentClassifierTrainer:
    """Trains, evaluates, and persists the document classification model."""

    def __init__(self) -> None:
        self.vectorizer: TfidfVectorizer | None = None
        self.classifier: LogisticRegression | None = None
        self.label_mapping: Dict[str, int] = {
            "policy_wording": 0,
            "reinsurance_treaty": 1,
            "claims_documentation": 2,
            "broker_agreement": 3,
        }
        self.reverse_mapping: Dict[int, str] = {v: k for k, v in self.label_mapping.items()}

    def load_training_data(self, data_path: str) -> Tuple[List[str], List[int]]:
        """
        Load training samples from a JSON file produced by generate_classification_training_data.py.

        Returns:
            (texts, integer_labels) tuple.

        Raises:
            FileNotFoundError: If data_path does not exist.
            ValueError: If a sample contains an unrecognised category label.
        """
        logger.info("Loading training data from: %s", data_path)
        with open(data_path, encoding="utf-8") as f:
            data = json.load(f)

        samples = data["data"]
        texts: List[str] = []
        labels: List[int] = []

        for item in samples:
            category = item["category"]
            if category not in self.label_mapping:
                raise ValueError(f"Unknown category in training data: {category!r}")
            texts.append(item["text"])
            labels.append(self.label_mapping[category])

        logger.info(
            "Loaded %d samples across %d categories", len(texts), len(set(labels))
        )
        return texts, labels

    def train(self, texts: List[str], labels: List[int]) -> Dict[str, Any]:
        """
        Fit TF-IDF vectorizer and Logistic Regression classifier.

        Returns:
            Dictionary of evaluation metrics including accuracy, cross-validation
            scores, and per-category classification report.
        """
        logger.info("Splitting data 80/20 (stratified)…")
        X_train, X_test, y_train, y_test = train_test_split(
            texts, labels, test_size=0.2, random_state=42, stratify=labels
        )
        logger.info(
            "Train: %d samples  |  Test: %d samples", len(X_train), len(X_test)
        )

        logger.info("Fitting TF-IDF vectorizer…")
        self.vectorizer = TfidfVectorizer(
            max_features=2000,
            ngram_range=(1, 3),
            min_df=2,
            max_df=0.95,
            strip_accents="unicode",
            lowercase=True,
            stop_words="english",
        )
        X_train_vec = self.vectorizer.fit_transform(X_train)
        X_test_vec = self.vectorizer.transform(X_test)
        logger.info("Feature matrix shape: %s", X_train_vec.shape)

        logger.info("Training Logistic Regression…")
        self.classifier = LogisticRegression(
            C=1.0,
            solver="lbfgs",
            max_iter=500,
            random_state=42,
            n_jobs=-1,
        )
        self.classifier.fit(X_train_vec, y_train)

        # Evaluation
        y_train_pred = self.classifier.predict(X_train_vec)
        y_test_pred = self.classifier.predict(X_test_vec)
        train_accuracy = float(np.mean(np.array(y_train_pred) == np.array(y_train)))
        test_accuracy = float(np.mean(np.array(y_test_pred) == np.array(y_test)))

        cv_scores = cross_val_score(
            self.classifier, X_train_vec, y_train, cv=5, scoring="accuracy"
        )

        report = classification_report(
            y_test,
            y_test_pred,
            target_names=list(self.label_mapping.keys()),
            output_dict=True,
        )
        cm = confusion_matrix(y_test, y_test_pred)

        metrics: Dict[str, Any] = {
            "train_accuracy": round(train_accuracy, 4),
            "test_accuracy": round(test_accuracy, 4),
            "cv_accuracy_mean": round(float(cv_scores.mean()), 4),
            "cv_accuracy_std": round(float(cv_scores.std()), 4),
            "classification_report": report,
            "confusion_matrix": cm.tolist(),
            "feature_count": X_train_vec.shape[1],
            "training_samples": len(X_train),
            "test_samples": len(X_test),
        }

        logger.info("Training complete!")
        logger.info("  Train Accuracy : %.2f%%", train_accuracy * 100)
        logger.info("  Test Accuracy  : %.2f%%", test_accuracy * 100)
        logger.info(
            "  CV Accuracy    : %.2f%% (±%.2f%%)",
            cv_scores.mean() * 100,
            cv_scores.std() * 100,
        )
        return metrics

    def save_model(self, metrics: Dict[str, Any]) -> None:
        """Persist vectorizer, classifier, and metadata JSON to MODEL_DIR."""
        vectorizer_path = MODEL_DIR / "document_classifier_vectorizer.joblib"
        classifier_path = MODEL_DIR / "document_classifier_model.joblib"
        metadata_path = MODEL_DIR / "document_classifier_metadata.json"

        joblib.dump(self.vectorizer, vectorizer_path)
        logger.info("Saved vectorizer → %s", vectorizer_path)

        joblib.dump(self.classifier, classifier_path)
        logger.info("Saved classifier → %s", classifier_path)

        metadata: Dict[str, Any] = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "model_type": "TF-IDF + Logistic Regression",
            "categories": list(self.label_mapping.keys()),
            "label_mapping": self.label_mapping,
            "metrics": metrics,
            "vectorizer_path": str(vectorizer_path),
            "classifier_path": str(classifier_path),
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        logger.info("Saved metadata → %s", metadata_path)


def main() -> int:
    """Entry point: find latest training data, train, evaluate, save."""
    print("\n" + "=" * 60)
    print("DOCUMENT CLASSIFIER TRAINING")
    print("=" * 60)

    training_files = sorted(
        TRAINING_DATA_DIR.glob("document_classification_training_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not training_files:
        print("\nNo training data found!")
        print("Run: python scripts/generate_classification_training_data.py")
        return 1

    latest_file = training_files[0]
    print(f"\nUsing: {latest_file.name}")

    trainer = DocumentClassifierTrainer()
    try:
        texts, labels = trainer.load_training_data(str(latest_file))
    except (FileNotFoundError, ValueError) as exc:
        print(f"\nFailed to load training data: {exc}")
        return 1

    metrics = trainer.train(texts, labels)
    trainer.save_model(metrics)

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"Train Accuracy : {metrics['train_accuracy'] * 100:.2f}%")
    print(f"Test Accuracy  : {metrics['test_accuracy'] * 100:.2f}%")
    print(
        f"CV Accuracy    : {metrics['cv_accuracy_mean'] * 100:.2f}%"
        f" (±{metrics['cv_accuracy_std'] * 100:.2f}%)"
    )
    print("\nPer-Category Performance:")
    report = metrics["classification_report"]
    for category in trainer.label_mapping:
        if category in report:
            r = report[category]
            print(
                f"  {category:25s}  P={r['precision']:.3f}  R={r['recall']:.3f}  F1={r['f1-score']:.3f}"
            )

    if metrics["test_accuracy"] < 0.85:
        print(
            f"\nWARNING: Test accuracy {metrics['test_accuracy'] * 100:.1f}% is below the 85% target."
        )
        print("Consider adding more training data or tuning hyperparameters.")

    print("\nModel saved to: storage/models/app/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
