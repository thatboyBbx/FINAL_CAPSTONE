"""
Insurance circular text classifier.
Pipeline: TF-IDF (unigrams + bigrams) → SGDClassifier (log loss, balanced classes).

Usage
-----
# train
from app.modules.ml.circular_classifier import train_circular_classifier
meta = train_circular_classifier()

# infer
from app.modules.ml.circular_classifier import predict_circular_category
result = predict_circular_category(text="...", filename="Circular 3 of 2024 - Settlement of Claims.pdf")
"""
import json
import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import classification_report
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split

from app.core.config import settings
from app.modules.documents.ingestion.feature_extractor import _infer_category

logger = logging.getLogger(__name__)

MODEL_DIR = Path(settings.app_model_dir)
MODEL_PATH = MODEL_DIR / "circular_classifier.joblib"
META_PATH = MODEL_DIR / "circular_classifier.json"
CORPUS_PATH = Path(settings.app_dataset_dir) / "circulars_corpus.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _doc_text(record: dict) -> str:
    """Build training text by weighting filename more than body."""
    fn = record.get("filename", "")
    body = record.get("text", "")[:4000]
    return f"{fn} {fn} {fn} {body}"


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_circular_classifier(
    corpus_path: Path = CORPUS_PATH,
    save_path: Path = MODEL_PATH,
) -> dict[str, Any]:
    """Train a TF-IDF + SGD classifier on the ingested corpus. Returns metrics dict."""
    if not corpus_path.exists():
        raise FileNotFoundError(
            f"Corpus not found at {corpus_path}. "
            "Run build_and_train() first to ingest documents."
        )

    with open(corpus_path, encoding="utf-8") as f:
        corpus = json.load(f)

    if len(corpus) < 5:
        raise ValueError(f"Corpus too small ({len(corpus)} docs). Need at least 5.")

    texts = [_doc_text(r) for r in corpus]
    labels = [r["category"] for r in corpus]
    unique_cats = sorted(set(labels))

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=20000,
            sublinear_tf=True,
            min_df=1,
            strip_accents="unicode",
            analyzer="word",
        )),
        ("clf", SGDClassifier(
            loss="modified_huber",
            alpha=5e-5,
            max_iter=200,
            tol=1e-4,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )),
    ])

    if len(texts) >= 20:
        X_tr, X_te, y_tr, y_te = train_test_split(
            texts, labels, test_size=0.2, random_state=42, stratify=None
        )
        pipeline.fit(X_tr, y_tr)
        y_pred = pipeline.predict(X_te)
        report = classification_report(y_te, y_pred, output_dict=True, zero_division=0)
        accuracy = float(report.get("accuracy", 0.0))
        f1 = float(report.get("macro avg", {}).get("f1-score", 0.0))
        eval_note = f"80/20 split — {len(X_te)} test docs"
    else:
        pipeline.fit(texts, labels)
        accuracy = f1 = 0.0
        eval_note = "Trained on all data (< 20 docs, no eval split)"

    save_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, save_path)

    meta = {
        "total_docs": len(texts),
        "categories": unique_cats,
        "category_counts": {c: labels.count(c) for c in unique_cats},
        "accuracy": round(accuracy, 4),
        "f1_macro": round(f1, 4),
        "eval_note": eval_note,
        "model_path": str(save_path),
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    logger.info(
        "Circular classifier trained: %d docs, %d categories, accuracy=%.2f, f1=%.2f",
        len(texts), len(unique_cats), accuracy, f1,
    )
    return meta


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

_pipeline_cache: Pipeline | None = None


def _load_pipeline() -> Pipeline | None:
    global _pipeline_cache
    if _pipeline_cache is not None:
        return _pipeline_cache
    if MODEL_PATH.exists():
        try:
            _pipeline_cache = joblib.load(MODEL_PATH)
            return _pipeline_cache
        except Exception as e:
            logger.warning("Could not load circular classifier: %s", e)
    return None


def predict_circular_category(
    text: str,
    filename: str = "",
) -> dict[str, Any]:
    """Predict the category of a single document using hybrid rule+ML strategy."""
    rule_category = _infer_category(filename, text)

    pipeline = _load_pipeline()
    if pipeline is not None:
        try:
            input_text = f"{filename} {filename} {filename} {text[:4000]}"
            ml_category = pipeline.predict([input_text])[0]
            try:
                proba = pipeline.predict_proba([input_text])[0]
                classes = list(pipeline.classes_)
                ml_conf = float(np.max(proba))
                top = sorted(zip(classes, proba.tolist()), key=lambda x: -x[1])[:3]
                top_categories = [{"category": c, "confidence": round(p, 3)} for c, p in top]
            except Exception:
                ml_conf = 1.0
                top_categories = [{"category": ml_category, "confidence": 1.0}]

            if ml_category == "general" and rule_category != "general":
                final_category = rule_category
                final_conf = 0.82
                method = "rule_hybrid"
            elif ml_category != "general" and ml_conf >= 0.55:
                final_category = ml_category
                final_conf = ml_conf
                method = "ml_model"
            else:
                final_category = rule_category
                final_conf = 0.75
                method = "rule_hybrid"

            return {
                "category": final_category,
                "confidence": round(final_conf, 3),
                "top_categories": top_categories,
                "method": method,
            }
        except Exception as e:
            logger.warning("ML prediction failed, falling back: %s", e)

    return {
        "category": rule_category,
        "confidence": 0.85,
        "top_categories": [{"category": rule_category, "confidence": 0.85}],
        "method": "rule_based",
    }


def get_classifier_status() -> dict[str, Any]:
    """Return current model status for dashboard display."""
    if not MODEL_PATH.exists():
        return {"trained": False, "model_path": str(MODEL_PATH)}
    try:
        with open(META_PATH) as f:
            meta = json.load(f)
        meta["trained"] = True
        return meta
    except Exception:
        return {"trained": True, "model_path": str(MODEL_PATH)}
