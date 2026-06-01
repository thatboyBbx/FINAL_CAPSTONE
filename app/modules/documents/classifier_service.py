"""
Document Classification Service.

Automatically classifies insurance documents into categories:
1. Policy Wording
2. Reinsurance Treaty
3. Claims Documentation
4. Broker Agreement

Uses pre-trained TF-IDF + Logistic Regression model with keyword-based fallback.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Literal

import joblib

logger = logging.getLogger(__name__)

# Model paths
MODEL_DIR = Path("storage/models/app")
VECTORIZER_PATH = MODEL_DIR / "document_classifier_vectorizer.joblib"
CLASSIFIER_PATH = MODEL_DIR / "document_classifier_model.joblib"
METADATA_PATH = MODEL_DIR / "document_classifier_metadata.json"

# Type hint for document categories
# Sandbox types appended (SANDBOX_EXP_v1) — additive only, existing types unchanged
DocumentCategory = Literal[
    "policy_wording",
    "reinsurance_treaty",
    "claims_documentation",
    "broker_agreement",
    "sandbox_application",
    "sandbox_quarterly_report",
    "sandbox_exit_report",
    "unknown",
]


class DocumentClassifierService:
    """
    Service for classifying insurance documents.

    Features:
    - Fast classification (<100ms per document)
    - Confidence scoring with per-category probability breakdown
    - Graceful keyword-based fallback if ML model is unavailable
    """

    def __init__(self) -> None:
        """Load pre-trained model or set to None if unavailable."""
        self.vectorizer = None
        self.classifier = None
        self.label_mapping: dict[str, int] | None = None
        self.reverse_mapping: dict[int, str] | None = None
        self._load_model()

    def _load_model(self) -> None:
        """Load vectorizer, classifier, and label metadata from disk."""
        try:
            if not VECTORIZER_PATH.exists() or not CLASSIFIER_PATH.exists():
                logger.warning(
                    "Document classifier model not found at %s. "
                    "Run: python scripts/train_document_classifier.py",
                    MODEL_DIR,
                )
                return

            self.vectorizer = joblib.load(VECTORIZER_PATH)
            self.classifier = joblib.load(CLASSIFIER_PATH)

            if METADATA_PATH.exists():
                with open(METADATA_PATH, encoding="utf-8") as f:
                    metadata = json.load(f)
                self.label_mapping = metadata.get("label_mapping", {})
                self.reverse_mapping = {int(v): k for k, v in self.label_mapping.items()}

            logger.info("Document classifier loaded successfully from %s", MODEL_DIR)

        except Exception as exc:
            logger.error("Failed to load document classifier: %s", exc, exc_info=True)
            self.vectorizer = None
            self.classifier = None

    def classify(self, document_text: str) -> Dict[str, Any]:
        """
        Classify an insurance document into one of four categories.

        Args:
            document_text: Full plain-text content of the document.

        Returns:
            {
                "category": "policy_wording" | "reinsurance_treaty" |
                            "claims_documentation" | "broker_agreement" | "unknown",
                "confidence": float,          # 0.0 – 1.0
                "probabilities": {            # per-category probability
                    "policy_wording": float,
                    "reinsurance_treaty": float,
                    "claims_documentation": float,
                    "broker_agreement": float,
                },
                "method": "ml_model" | "fallback",
            }
        """
        if not document_text or not document_text.strip():
            return {
                "category": "unknown",
                "confidence": 0.0,
                "probabilities": {k: round(1 / 7, 4) for k in (
                    "policy_wording", "reinsurance_treaty",
                    "claims_documentation", "broker_agreement",
                    "sandbox_application", "sandbox_quarterly_report",
                    "sandbox_exit_report",
                )},
                "method": "fallback",
            }

        if self.vectorizer is None or self.classifier is None:
            logger.warning("ML classifier unavailable — using keyword fallback")
            return self._fallback_classification(document_text)

        try:
            X = self.vectorizer.transform([document_text])
            prediction = self.classifier.predict(X)[0]
            probabilities = self.classifier.predict_proba(X)[0]

            category = self.reverse_mapping.get(int(prediction), "unknown")
            confidence = float(probabilities[int(prediction)])

            prob_dict: dict[str, float] = {}
            if self.label_mapping:
                for label_name, label_id in self.label_mapping.items():
                    prob_dict[label_name] = round(float(probabilities[int(label_id)]), 4)

            return {
                "category": category,
                "confidence": round(confidence, 4),
                "probabilities": prob_dict,
                "method": "ml_model",
            }

        except Exception as exc:
            logger.error("ML classification failed: %s — falling back to keywords", exc)
            return self._fallback_classification(document_text)

    def _fallback_classification(self, document_text: str) -> Dict[str, Any]:
        """
        Keyword-frequency fallback classifier for when the ML model is unavailable.

        Counts domain-specific keywords in each category and normalises the counts
        into a pseudo-probability distribution.
        """
        text_lower = document_text.lower()

        policy_keywords = [
            "policy", "coverage", "sum insured", "premium", "exclusions",
            "deductible", "excess", "insured", "insurer", "conditions",
            "section a", "section b", "policy period", "underwriting",
        ]
        treaty_keywords = [
            "reinsurance", "treaty", "reinsured", "reinsurer", "cession",
            "retention", "quota share", "excess of loss", "article",
            "layer", "reinstatement", "arbitration", "proportionate share",
        ]
        claims_keywords = [
            "claim", "claimant", "loss", "incident", "damage",
            "assessment", "adjustor", "settlement", "police report",
            "repair", "declaration", "claim number", "assessed loss",
        ]
        broker_keywords = [
            "broker", "brokerage", "commission", "appointment",
            "binding authority", "remit", "solicit", "procure",
            "premium remittance", "broker responsibilities", "binding",
        ]

        # Sandbox keywords — drawn from IPEC Regulatory Sandbox Guidelines (2025)
        sandbox_application_keywords = [
            "regulatory sandbox", "sandbox application", "testing period",
            "boundary condition", "regulatory waiver", "exemption sought",
            "consent to participate", "graduation phase", "exit plan",
        ]
        sandbox_quarterly_keywords = [
            "quarterly progress report", "kpi performance", "risk register",
            "operational challenges", "audit details", "customer complaints",
            "sandbox quarterly", "reporting period",
        ]
        sandbox_exit_keywords = [
            "exit report", "orderly exit", "post-exit", "graduation phase",
            "test was successful", "test outcome", "transition deployment",
            "commission will communicate",
        ]

        scores: dict[str, float] = {
            "policy_wording": sum(1.0 for kw in policy_keywords if kw in text_lower),
            "reinsurance_treaty": sum(1.0 for kw in treaty_keywords if kw in text_lower),
            "claims_documentation": sum(1.0 for kw in claims_keywords if kw in text_lower),
            "broker_agreement": sum(1.0 for kw in broker_keywords if kw in text_lower),
            # Sandbox document types (SANDBOX_EXP_v1)
            "sandbox_application": sum(
                1.0 for kw in sandbox_application_keywords if kw in text_lower
            ),
            "sandbox_quarterly_report": sum(
                1.0 for kw in sandbox_quarterly_keywords if kw in text_lower
            ),
            "sandbox_exit_report": sum(
                1.0 for kw in sandbox_exit_keywords if kw in text_lower
            ),
        }

        total = sum(scores.values())
        if total == 0.0:
            return {
                "category": "unknown",
                "confidence": 0.0,
                "probabilities": {k: 0.25 for k in scores},
                "method": "fallback",
            }

        probabilities = {k: round(v / total, 4) for k, v in scores.items()}
        category = max(probabilities, key=lambda k: probabilities[k])
        confidence = probabilities[category]

        return {
            "category": category,
            "confidence": confidence,
            "probabilities": probabilities,
            "method": "fallback",
        }
