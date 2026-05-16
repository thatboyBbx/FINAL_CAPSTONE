"""
TF-IDF + Logistic Regression risk classifier for intel news articles.
Labels: Regulatory Risk | Market Risk | Claims Alert | Neutral
Model persisted to storage/models/intel_classifier.pkl
"""
from __future__ import annotations

import io
import logging
import os
import pickle
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

LABELS = ["Regulatory Risk", "Market Risk", "Claims Alert", "Neutral"]

_MODEL_PATH = Path("storage/models/intel_classifier.pkl")
_META_PATH  = Path("storage/models/intel_classifier_meta.pkl")

_LABEL_KEYWORDS: Dict[str, List[str]] = {
    "Regulatory Risk": [
        "ipec", "praz", "regulation", "compliance", "licence", "statutory",
        "fine", "sanction", "regulator", "enforcement", "directive",
    ],
    "Market Risk": [
        "stock exchange", "zse", "shares", "listed", "dividend", "earnings",
        "financial results", "profit", "loss", "market cap", "trading",
        "premium income", "underwriting loss",
    ],
    "Claims Alert": [
        "claim", "claims", "payout", "dispute", "complaint", "fraud",
        "settlement refused", "court", "lawsuit", "non-payment",
    ],
}


def _auto_label(text: str) -> str:
    t = text.lower()
    for label, kws in _LABEL_KEYWORDS.items():
        if any(k in t for k in kws):
            return label
    return "Neutral"


def _ensure_model_dir() -> None:
    _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_pipeline() -> object | None:
    try:
        if _MODEL_PATH.exists():
            with open(_MODEL_PATH, "rb") as f:
                return pickle.load(f)
    except Exception as e:
        logger.warning("intel classifier load error: %s", e)
    return None


def is_trained() -> bool:
    return _MODEL_PATH.exists()


def get_model_meta() -> dict | None:
    try:
        if _META_PATH.exists():
            with open(_META_PATH, "rb") as f:
                return pickle.load(f)
    except Exception as e:
        logger.warning("intel classifier meta load error: %s", e)
    return None


def train(articles: list[dict]) -> dict:
    """
    Train on intel articles. Articles should be dicts with 'title' and 'snippet'.
    Returns summary dict.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.model_selection import cross_val_score
        import numpy as np
    except ImportError:
        return {"error": "scikit-learn not installed"}

    if len(articles) < 10:
        return {"error": f"Too few articles ({len(articles)}). Ingest more news first."}

    texts  = [f"{a.get('title', '')} {a.get('snippet', '')}" for a in articles]
    labels = [_auto_label(t) for t in texts]

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=8000,
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=2,
        )),
        ("clf", LogisticRegression(
            max_iter=500, C=1.0, solver="lbfgs", multi_class="auto",
        )),
    ])

    pipeline.fit(texts, labels)

    n_folds = min(3, min(labels.count(l) for l in set(labels)) or 1)
    if n_folds >= 2:
        scores   = cross_val_score(pipeline, texts, labels, cv=n_folds)
        accuracy = float(np.mean(scores))
    else:
        accuracy = 1.0

    trained_at = datetime.now(timezone.utc).isoformat()
    classes    = sorted(set(labels))

    _ensure_model_dir()
    try:
        with open(_MODEL_PATH, "wb") as f:
            pickle.dump(pipeline, f)
        meta = {
            "trained_at":  trained_at,
            "accuracy":    round(accuracy, 4),
            "num_samples": len(texts),
            "classes":     classes,
            "label_dist":  {l: labels.count(l) for l in LABELS},
        }
        with open(_META_PATH, "wb") as f:
            pickle.dump(meta, f)
    except Exception as e:
        logger.warning("intel classifier save error: %s", e)
        return {"error": f"Failed to save model: {e}"}

    return meta


def predict(text: str) -> Dict:
    """Predict risk label for a single text. Falls back to keyword heuristic."""
    pipeline = _load_pipeline()
    if pipeline is None:
        label = _auto_label(text)
        return {"label": label, "confidence": 0.0, "source": "heuristic"}
    try:
        proba = pipeline.predict_proba([text])[0]
        label = pipeline.classes_[proba.argmax()]
        conf  = float(proba.max())
        return {"label": label, "confidence": round(conf, 4), "source": "model"}
    except Exception as e:
        logger.warning("intel predict error: %s", e)
        return {"label": "Neutral", "confidence": 0.0, "source": "error"}


def apply_labels_to_all(db) -> int:
    """Re-run predictions on all intel articles. Returns count updated."""
    from app.modules.intel.repo import update_risk_label, get_all_articles

    pipeline = _load_pipeline()
    articles = get_all_articles(db)

    updated = 0
    for article in articles:
        text = f"{article.title or ''} {article.snippet or ''}"
        if pipeline:
            try:
                proba = pipeline.predict_proba([text])[0]
                label = pipeline.classes_[proba.argmax()]
                conf  = float(proba.max())
            except Exception:
                label = _auto_label(text)
                conf  = 0.0
        else:
            label = _auto_label(text)
            conf  = 0.0
        update_risk_label(db, article.id, label, round(conf, 4))
        updated += 1

    return updated
