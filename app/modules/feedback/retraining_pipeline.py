"""
RetrainingPipeline — uses accumulated feedback to retrain the NER and risk models.

NER base dataset:
  HuggingFace: "autonlp-project/insurance-ner"
  Download: from datasets import load_dataset; ds = load_dataset("autonlp-project/insurance-ner")
  Fallback: "Jean-Baptiste/roberta-large-ner-english" base model fine-tuned once
  50+ corrections are accumulated.

Risk model:
  Base: XGBoost regressor saved at storage/models/app/settlement_model.joblib (or similar).
  Retraining relabels risk scores based on is_false_positive and correct_severity feedback.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.modules.feedback.feedback_store import FeedbackStore

logger = logging.getLogger(__name__)

_TRAINING_DATA_DIR = Path("storage/training_data")
_MODEL_DIR = Path("storage/models/app")
_NER_MODEL_DIR = _MODEL_DIR / "ner_model"
_NER_METRICS_FILE = _NER_MODEL_DIR / "metrics.json"


class RetrainingPipeline:
    """Orchestrates NER and risk model retraining with human feedback."""

    def __init__(self) -> None:
        self._store = FeedbackStore()

    # ------------------------------------------------------------------
    # NER retraining
    # ------------------------------------------------------------------

    def prepare_ner_training_data(self, db: Session) -> str:
        """
        Build spaCy-format training data from entity_feedback records
        combined with the HuggingFace base dataset.
        Returns the path to the saved training data JSON file.
        """
        from app.modules.feedback.model import EntityFeedback
        from app.modules.circulars.model import CircularAnalysis

        feedback_rows = (
            db.query(EntityFeedback)
            .filter(EntityFeedback.used_in_training == False)  # noqa: E712
            .all()
        )

        training_data: List[Dict[str, Any]] = []

        for fb in feedback_rows:
            # Retrieve the source text from the circular analysis
            text = ""
            if fb.circular_analysis_id:
                analysis = (
                    db.query(CircularAnalysis)
                    .filter(CircularAnalysis.id == fb.circular_analysis_id)
                    .first()
                )
                if analysis and analysis.extracted_text:
                    text = analysis.extracted_text[:2000]

            if not text:
                continue

            # Find the corrected value in the text to get char positions
            start = text.find(fb.corrected_value)
            if start == -1:
                continue
            end = start + len(fb.corrected_value)

            # spaCy training format
            training_data.append({
                "text": text,
                "entities": [[start, end, fb.corrected_type.upper()]],
            })

        # Attempt to load HuggingFace base dataset and add it
        try:
            from datasets import load_dataset
            ds = load_dataset("autonlp-project/insurance-ner", trust_remote_code=True)
            for item in (ds.get("train") or []):
                tokens = item.get("tokens", [])
                ner_tags = item.get("ner_tags", [])
                if tokens:
                    text = " ".join(tokens)
                    training_data.append({
                        "text": text,
                        "entities": [],  # simplified — token-level labels not converted here
                    })
        except Exception as exc:
            logger.info("HuggingFace base NER dataset unavailable: %s", exc)

        # Save training data
        _TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = _TRAINING_DATA_DIR / f"ner_training_{ts}.json"
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(training_data, f, ensure_ascii=False, indent=2)
            logger.info("NER training data saved: %s (%d examples)", out_path, len(training_data))
        except Exception as exc:
            logger.error("Failed to save training data: %s", exc)
            raise

        return str(out_path)

    def retrain_ner_model(self, training_data_path: str) -> str:
        """
        Resume training of the existing spaCy NER model with new data.
        Only saves if new F1 > previous F1.
        Returns the path to the updated model.
        """
        try:
            import spacy
            from spacy.training import Example
        except ImportError:
            logger.error("spacy not installed — NER retraining skipped.")
            return ""

        # Load existing model or create a blank one
        if _NER_MODEL_DIR.exists():
            try:
                nlp = spacy.load(str(_NER_MODEL_DIR))
            except Exception:
                nlp = spacy.blank("en")
        else:
            nlp = spacy.blank("en")

        # Ensure NER pipe exists
        if "ner" not in nlp.pipe_names:
            nlp.add_pipe("ner", last=True)

        ner = nlp.get_pipe("ner")

        # Load training data
        with open(training_data_path, encoding="utf-8") as f:
            raw_data = json.load(f)

        # Add labels from training data
        for item in raw_data:
            for _, _, label in item.get("entities", []):
                ner.add_label(label)

        # Build spaCy Example objects
        examples = []
        for item in raw_data:
            text = item.get("text", "")
            entities = item.get("entities", [])
            if not text or not entities:
                continue
            try:
                doc = nlp.make_doc(text)
                example = Example.from_dict(doc, {"entities": entities})
                examples.append(example)
            except Exception:
                continue

        if not examples:
            logger.warning("No valid training examples found — NER retrain skipped.")
            return ""

        # Split 80/20 for evaluation
        split = int(len(examples) * 0.8)
        train_examples = examples[:split]
        eval_examples  = examples[split:]

        # Train for 30 iterations
        optimizer = nlp.resume_training()
        for _ in range(30):
            import random
            random.shuffle(train_examples)
            for batch in spacy.util.minibatch(train_examples, size=8):
                nlp.update(batch, sgd=optimizer, drop=0.35)

        # Evaluate
        scores = nlp.evaluate(eval_examples) if eval_examples else {}
        new_f1 = scores.get("ents_f", 0.0)
        logger.info("NER retrain complete — F1: %.4f", new_f1)

        # Load previous F1 and only save if improved
        prev_f1 = 0.0
        if _NER_METRICS_FILE.exists():
            try:
                with open(_NER_METRICS_FILE) as f:
                    prev_f1 = json.load(f).get("f1", 0.0)
            except Exception:
                pass

        if new_f1 <= prev_f1 and prev_f1 > 0:
            logger.info("New F1 (%.4f) <= previous (%.4f) — not saving.", new_f1, prev_f1)
            return str(_NER_MODEL_DIR)

        # Atomic save: write to _new first, then rename
        new_model_dir = _MODEL_DIR / "ner_model_new"
        try:
            nlp.to_disk(str(new_model_dir))
            if _NER_MODEL_DIR.exists():
                import shutil
                shutil.rmtree(str(_NER_MODEL_DIR))
            new_model_dir.rename(_NER_MODEL_DIR)
            # Save metrics
            _NER_METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(_NER_METRICS_FILE, "w") as f:
                json.dump({"f1": new_f1, "updated_at": datetime.now(timezone.utc).isoformat()}, f)
            logger.info("NER model saved to %s (F1=%.4f).", _NER_MODEL_DIR, new_f1)
        except Exception as exc:
            logger.error("Failed to save NER model: %s", exc)

        return str(_NER_MODEL_DIR)

    # ------------------------------------------------------------------
    # Risk model retraining
    # ------------------------------------------------------------------

    def retrain_risk_model(self, db: Session) -> str:
        """
        Retrain the XGBoost risk model using risk_flag_feedback corrections.
        Returns path to the updated model.
        """
        from app.modules.feedback.model import RiskFlagFeedback
        from app.modules.circulars.model import CircularAnalysis

        rows = (
            db.query(RiskFlagFeedback)
            .filter(RiskFlagFeedback.used_in_training == False)  # noqa: E712
            .all()
        )

        if not rows:
            logger.info("No risk flag feedback to train on.")
            return ""

        # Build feature/label arrays from CircularAnalysis rows
        try:
            import numpy as np
            import joblib
            from xgboost import XGBRegressor
        except ImportError as exc:
            logger.error("Required ML packages missing: %s", exc)
            return ""

        feature_rows = []
        labels = []

        severity_map = {"low": 0.2, "moderate": 0.5, "high": 0.8, "critical": 1.0}

        for fb in rows:
            analysis = (
                db.query(CircularAnalysis)
                .filter(CircularAnalysis.id == fb.circular_analysis_id)
                .first()
            )
            if not analysis:
                continue

            # Feature vector: risk signal counts from analysis
            feats = [
                analysis.compliance_signal or 0,
                analysis.financial_stress_signal or 0,
                analysis.claims_signal or 0,
                analysis.regulatory_signal or 0,
                analysis.market_conduct_signal or 0,
                analysis.total_risk_signals or 0,
                analysis.nlp_risk_score or 0.0,
            ]
            feature_rows.append(feats)

            # Label: corrected severity (adjusted down if false positive)
            correct_score = severity_map.get(fb.correct_severity.lower(), 0.5)
            if fb.is_false_positive:
                correct_score *= 0.3  # dramatically reduce score for false positives
            labels.append(correct_score)

        if not feature_rows:
            logger.warning("No feature rows built for risk model retraining.")
            return ""

        X = np.array(feature_rows, dtype=np.float32)
        y = np.array(labels, dtype=np.float32)

        # Load existing model or create a new one
        model_path = _MODEL_DIR / "risk_model.joblib"
        try:
            if model_path.exists():
                model = joblib.load(str(model_path))
            else:
                model = XGBRegressor(
                    n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42
                )
        except Exception:
            model = XGBRegressor(n_estimators=100, max_depth=3, random_state=42)

        try:
            model.fit(X, y)
        except Exception as exc:
            logger.error("Risk model fit failed: %s", exc)
            return ""

        # Atomic save
        new_path = _MODEL_DIR / "risk_model_new.joblib"
        try:
            _MODEL_DIR.mkdir(parents=True, exist_ok=True)
            joblib.dump(model, str(new_path))
            if model_path.exists():
                model_path.unlink()
            new_path.rename(model_path)
            logger.info("Risk model updated at %s.", model_path)
        except Exception as exc:
            logger.error("Failed to save risk model: %s", exc)
            return ""

        return str(model_path)

    # ------------------------------------------------------------------
    # Full retraining orchestration
    # ------------------------------------------------------------------

    def run_full_retraining(self, db: Session) -> Dict[str, Any]:
        """
        Orchestrate NER and risk model retraining.
        Marks all used feedback as consumed.
        Called monthly by APScheduler.
        """
        pending = self._store.get_pending_feedback(db)
        total = pending["total_count"]

        ner_retrained = False
        risk_retrained = False
        new_f1 = 0.0
        ner_entity_ids: List[int] = []

        # Retrain NER if entity corrections are available
        entity_corrections = pending.get("entity_corrections", [])
        if entity_corrections:
            try:
                training_path = self.prepare_ner_training_data(db)
                result_path = self.retrain_ner_model(training_path)
                if result_path:
                    ner_retrained = True
                    ner_entity_ids = [c["id"] for c in entity_corrections]
                    # Read new F1 from metrics file
                    if _NER_METRICS_FILE.exists():
                        with open(_NER_METRICS_FILE) as f:
                            new_f1 = json.load(f).get("f1", 0.0)
            except Exception as exc:
                logger.error("NER retraining failed: %s", exc)

        # Retrain risk model if risk corrections are available
        risk_corrections = pending.get("risk_corrections", [])
        risk_ids: List[int] = []
        if risk_corrections:
            try:
                result_path = self.retrain_risk_model(db)
                if result_path:
                    risk_retrained = True
                    risk_ids = [c["id"] for c in risk_corrections]
            except Exception as exc:
                logger.error("Risk model retraining failed: %s", exc)

        # Mark all used feedback as consumed
        self._store.mark_feedback_used(db, ner_entity_ids, risk_ids)

        return {
            "ner_retrained": ner_retrained,
            "risk_retrained": risk_retrained,
            "ner_f1_new": new_f1,
            "feedback_used": len(ner_entity_ids) + len(risk_ids),
        }
