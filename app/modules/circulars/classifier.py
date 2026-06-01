"""
Deep Learning Circular Classifier
==================================
Multi-Layer Perceptron (neural network) that classifies regulatory circulars
into risk levels (low / moderate / high) based on TF-IDF text features.

Architecture:
  TF-IDF (max_features=5000)
    → Dense(512, relu)
    → Dense(256, relu)
    → Dense(128, relu)
    → Dense(3, softmax)

Implemented via sklearn.neural_network.MLPClassifier — a true multi-layer
perceptron (deep learning model). No GPU required.

Training workflow:
  1. At first use the model is untrained; it returns a default analysis.
  2. Call CircularClassifier.train(texts, labels) to train on labelled circulars.
  3. Once trained, CircularClassifier.predict(text) returns risk class + confidence.
  4. The trained model is persisted to storage/models/circular_classifier.joblib.
"""
from __future__ import annotations

import joblib
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline

from app.modules.circulars.nlp import CircularNLPAnalyser

# ---------------------------------------------------------------------------
# Storage path
# ---------------------------------------------------------------------------
_MODELS_DIR = Path("app/storage/models")
_MODEL_FILE  = _MODELS_DIR / "circular_classifier.joblib"

LABEL_MAP = {0: "low", 1: "moderate", 2: "high"}
LABEL_MAP_INV = {v: k for k, v in LABEL_MAP.items()}

# ---------------------------------------------------------------------------
# Synthetic training data generator (weak supervision / proxy labels)
# ---------------------------------------------------------------------------
# When no labelled circulars exist, we generate proxy training examples from
# our risk keyword vocabulary to initialise the deep learning model.

_HIGH_TEMPLATES = [
    "The company faces insolvency risk due to severe reserve deficiency and capital inadequacy. "
    "Immediate compliance required under Section 45. Penalty and licence revocation may apply. "
    "Solvency margin breach. Winding up proceedings initiated. Statutory fund shortfall. "
    "Undercapitalized insurer. Non-compliance deadline. Mandatory regulatory examination.",

    "IPEC/2024/01 – Solvency Directive. All insurers must comply immediately with minimum capital "
    "requirement or face suspension. Outstanding claims backlog is unsustainable. Liquidity crisis "
    "detected. Claims settlement failures. Regulatory sanction imminent. Reserve deficiency.",

    "Non-compliance with insurance act. Licence suspension. Penalty imposed for failure to meet "
    "statutory fund requirements. Insolvency proceedings. Claimant compensation overdue. "
    "Claims reserve inadequate. Receivership. Undercapitalized. Winding up. Mandatory compliance.",
]

_MODERATE_TEMPLATES = [
    "Insurers are reminded to maintain adequate claims reserves. The claims ratio has increased "
    "significantly. Quarterly financial returns are overdue. Reporting obligations must be met. "
    "Reinsurance cession requirements apply. IPEC circular guidance on compliance deadlines.",

    "Circular No. 5 of 2024. Compliance notice. Brokers and agents must comply with disclosure "
    "requirements. Policyholder consumer protection measures apply. Intermediary commissions. "
    "Deadline for submission of financial statements is 31 March 2024.",

    "Market conduct supervisory review. Mis-selling of insurance products noted. Consumer "
    "complaints received. Disclosure obligations mandatory. Transparency requirements. "
    "Annual actuarial return. Claims ratio trending upward. Broker registration required.",
]

_LOW_TEMPLATES = [
    "General notice to all insurance companies. Annual dinner and awards ceremony scheduled. "
    "Industry consultative meeting planned for April 2024. Stakeholder engagement session. "
    "Regulatory updates noted. Voluntary compliance encouraged. Industry growth statistics.",

    "IPEC quarterly newsletter. Market statistics for Q3 2024. Premium income summary. "
    "New product approvals. Microinsurance licensing update. Industry conference programme. "
    "Informational guidance note. No mandatory action required at this time.",

    "Informational circular regarding upcoming changes to reporting format. Guidance note only. "
    "No penalty applicable. Training workshop for actuaries. Voluntary industry participation. "
    "General regulatory awareness. No immediate compliance deadline.",
]


def _build_proxy_training_data() -> tuple[list[str], list[int]]:
    """Generate labelled proxy training data from keyword templates."""
    texts = _HIGH_TEMPLATES * 8 + _MODERATE_TEMPLATES * 8 + _LOW_TEMPLATES * 8
    labels = [2] * (len(_HIGH_TEMPLATES) * 8) + \
             [1] * (len(_MODERATE_TEMPLATES) * 8) + \
             [0] * (len(_LOW_TEMPLATES) * 8)
    return texts, labels


# ---------------------------------------------------------------------------
# Deep Learning pipeline
# ---------------------------------------------------------------------------

def _build_pipeline() -> Pipeline:
    """
    Build the MLP deep learning pipeline:
      TF-IDF → MLPClassifier (3 hidden layers = deep network)
    """
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
            stop_words="english",
        )),
        ("mlp", MLPClassifier(
            hidden_layer_sizes=(512, 256, 128),   # 3-layer deep network
            activation="relu",
            solver="adam",
            alpha=1e-4,           # L2 regularisation
            learning_rate="adaptive",
            max_iter=500,
            early_stopping=True,
            validation_fraction=0.15,
            random_state=42,
            verbose=False,
        )),
    ])


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

class CircularClassifier:
    """
    Deep Learning text classifier for insurance regulatory circulars.
    Classifies circular risk level: low / moderate / high.
    """

    def __init__(self) -> None:
        self._pipeline: Pipeline | None = None
        self._trained = False
        self._load_if_exists()

    # ------------------------------------------------------------------
    def _load_if_exists(self) -> None:
        if _MODEL_FILE.exists():
            try:
                bundle = joblib.load(_MODEL_FILE)
                self._pipeline = bundle["pipeline"]
                self._trained = True
            except Exception:
                self._trained = False

    # ------------------------------------------------------------------
    def is_trained(self) -> bool:
        return self._trained

    # ------------------------------------------------------------------
    def train(
        self,
        texts: list[str] | None = None,
        labels: list[int] | None = None,
        use_proxy: bool = True,
    ) -> dict:
        """
        Train the deep learning classifier.

        Args:
            texts:      List of circular text strings (optional if use_proxy=True).
            labels:     Corresponding integer risk labels 0/1/2.
            use_proxy:  If True, augment with proxy training data.

        Returns:
            dict with training summary.
        """
        _MODELS_DIR.mkdir(parents=True, exist_ok=True)

        all_texts: list[str] = list(texts or [])
        all_labels: list[int] = list(labels or [])

        if use_proxy or not all_texts:
            proxy_texts, proxy_labels = _build_proxy_training_data()
            all_texts = proxy_texts + all_texts
            all_labels = proxy_labels + all_labels

        if len(set(all_labels)) < 2:
            return {"error": "Need at least 2 distinct label classes to train."}

        pipeline = _build_pipeline()
        pipeline.fit(all_texts, all_labels)

        self._pipeline = pipeline
        self._trained = True

        joblib.dump({"pipeline": pipeline}, _MODEL_FILE)

        return {
            "status": "trained",
            "n_samples": len(all_texts),
            "classes": sorted(set(all_labels)),
            "architecture": "TF-IDF(5000, ngram=1-2) → MLP(512→256→128→3)",
            "model_file": str(_MODEL_FILE),
        }

    # ------------------------------------------------------------------
    def predict(self, text: str) -> dict:
        """
        Predict risk level for a circular text.
        If untrained, trains automatically on proxy data first.
        """
        if not self._trained or self._pipeline is None:
            self.train(use_proxy=True)

        probs = self._pipeline.predict_proba([text])[0].tolist()
        pred_class = int(np.argmax(probs))

        return {
            "risk_level": LABEL_MAP.get(pred_class, "low"),
            "risk_class": pred_class,
            "probabilities": {
                "low":      round(probs[0], 4),
                "moderate": round(probs[1], 4) if len(probs) > 1 else 0.0,
                "high":     round(probs[2], 4) if len(probs) > 2 else 0.0,
            },
            "model": "DeepLearning-MLP(TF-IDF 5000 → 512→256→128→3)",
        }

    # ------------------------------------------------------------------
    def predict_with_nlp(self, text: str, nlp_result=None) -> dict:
        """
        Enhanced prediction combining DL classifier + NLP risk signals.
        """
        dl_result = self.predict(text)

        if nlp_result is None:
            nlp_result = CircularNLPAnalyser().analyse(text)

        # Combine DL probability with rule-based NLP score
        dl_high_prob = dl_result["probabilities"]["high"]
        dl_mod_prob  = dl_result["probabilities"]["moderate"]
        nlp_score    = nlp_result.circular_risk_score  # 0-10

        # Fused score: 60% DL + 40% NLP (normalised)
        nlp_norm = min(nlp_score / 10.0, 1.0)
        fused_high = 0.6 * dl_high_prob + 0.4 * nlp_norm

        if fused_high >= 0.45:
            fused_label = "high"
        elif fused_high >= 0.2 or dl_mod_prob >= 0.35:
            fused_label = "moderate"
        else:
            fused_label = "low"

        return {
            **dl_result,
            "fused_risk_level":    fused_label,
            "fused_risk_score":    round(fused_high, 4),
            "nlp_risk_score":      round(nlp_score, 4),
            "predicted_category":  nlp_result.predicted_category,
            "category_confidence": nlp_result.category_confidence,
            "entities": {
                "dates":            nlp_result.dates[:5],
                "monetary_values":  nlp_result.monetary_values[:5],
                "regulatory_refs":  nlp_result.regulatory_refs[:5],
                "insurer_mentions": nlp_result.insurer_mentions[:3],
            },
            "risk_signals": {
                "compliance":       nlp_result.compliance_signal,
                "financial_stress": nlp_result.financial_stress_signal,
                "claims":           nlp_result.claims_signal,
                "regulatory":       nlp_result.regulatory_signal,
                "market_conduct":   nlp_result.market_conduct_signal,
                "total":            nlp_result.total_risk_signals,
            },
        }


# Module-level singleton (lazy initialise)
_classifier: CircularClassifier | None = None


def get_classifier() -> CircularClassifier:
    global _classifier
    if _classifier is None:
        _classifier = CircularClassifier()
    return _classifier
