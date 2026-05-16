"""
app/modules/ml/training_orchestrator.py
=========================================
One-shot ingestion + training orchestrator.
Call build_and_train() from the API or CLI to:
  1. Ingest PDFs from configured source paths
  2. Build JSON corpus
  3. Train the circular classifier
  4. (Re)train the settlement risk model on updated data

Moved from app/services/training_orchestrator.py.
"""
import logging
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_SOURCES = [
    {
        "path": r"C:\Users\lenovo\Downloads\downloads\insurance_circulars",
        "label": "circulars",
    },
    {
        "path": r"C:\Users\lenovo\Desktop\Scrapper\kb\raw",
        "label": "kb_documents",
    },
]

CORPUS_PATH = Path(settings.app_dataset_dir) / "circulars_corpus.json"


def build_and_train(
    sources: list[dict] | None = None,
    retrain_settlement: bool = True,
    progress_cb=None,
) -> dict[str, Any]:
    """
    Full pipeline:
      1. Ingest documents → corpus JSON
      2. Train circular classifier
      3. Optionally retrain settlement risk model
    """
    if sources is None:
        sources = DEFAULT_SOURCES

    results: dict[str, Any] = {
        "sources": [s["path"] for s in sources],
        "corpus_path": str(CORPUS_PATH),
    }

    logger.info("=== Step 1: Building document corpus ===")
    from app.modules.documents.ingestion.corpus_builder import build_corpus  # noqa: PLC0415
    try:
        corpus = build_corpus(
            source_paths=sources,
            output_path=CORPUS_PATH,
            progress_cb=progress_cb,
        )
        results["corpus_size"] = len(corpus)
        results["extractable_docs"] = sum(1 for r in corpus if r.get("extractable"))
        results["category_distribution"] = {}
        for r in corpus:
            cat = r.get("category", "general")
            results["category_distribution"][cat] = results["category_distribution"].get(cat, 0) + 1
        logger.info("Corpus: %d docs, %d extractable", len(corpus), results["extractable_docs"])
    except Exception as e:
        logger.error("Corpus build failed: %s", e)
        results["corpus_error"] = str(e)
        return results

    logger.info("=== Step 2: Training circular classifier ===")
    from app.modules.ml.circular_classifier import train_circular_classifier  # noqa: PLC0415
    try:
        clf_meta = train_circular_classifier()
        results["classifier"] = clf_meta
        logger.info("Classifier trained: accuracy=%.2f", clf_meta.get("accuracy", 0))
    except Exception as e:
        logger.error("Classifier training failed: %s", e)
        results["classifier_error"] = str(e)

    if retrain_settlement:
        logger.info("=== Step 3: Retraining settlement risk model ===")
        try:
            from app.modules.ml.training_service import train_demo_model  # noqa: PLC0415
            risk_meta = train_demo_model()
            results["settlement_model"] = risk_meta
            logger.info("Settlement model retrained")
        except Exception as e:
            logger.warning("Settlement model retrain skipped: %s", e)
            results["settlement_model_note"] = str(e)

    results["status"] = "complete"
    logger.info("=== Training pipeline complete ===")
    return results


def get_training_status() -> dict[str, Any]:
    """Return current state of models and corpus."""
    from app.modules.ml.circular_classifier import get_classifier_status  # noqa: PLC0415

    corpus_exists = CORPUS_PATH.exists()
    corpus_size = 0
    if corpus_exists:
        try:
            import json
            with open(CORPUS_PATH) as f:
                corpus_size = len(json.load(f))
        except Exception:
            pass

    return {
        "corpus_exists": corpus_exists,
        "corpus_path": str(CORPUS_PATH),
        "corpus_size": corpus_size,
        "classifier": get_classifier_status(),
        "sources": DEFAULT_SOURCES,
    }
