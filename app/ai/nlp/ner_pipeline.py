"""
app/ai/nlp/ner_pipeline.py

Named Entity Recognition pipeline for insurance documents.
Uses spaCy as the base NLP engine with custom EntityRuler patterns
for insurance-specific entities that the base model does not recognise.

Entity types extracted:
    INSURER         — name of an insurance company
    POLICY_NUMBER   — alphanumeric policy reference
    COVERAGE_LIMIT  — monetary coverage amounts (e.g. "USD 500,000")
    PREMIUM         — premium amounts and payment terms
    DEDUCTIBLE      — deductible amounts and conditions
    POLICY_PERIOD   — policy start/end dates
    EXCLUSION       — flagged exclusionary phrases
    CLAUSE_REF      — clause numbers (e.g. "Clause 4.1", "Section 7")
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Insurance-specific EntityRuler patterns for spaCy
# Each pattern is a dict with "label" and "pattern" keys (token-level or string patterns)
_INSURANCE_PATTERNS: list[dict] = [
    # Policy numbers — e.g. "POL-2024-001234", "Policy No. 123456"
    {"label": "POLICY_NUMBER", "pattern": [{"TEXT": {"REGEX": r"POL[-/]?\d{4}[-/]?\d{4,8}"}}]},
    {"label": "POLICY_NUMBER", "pattern": [
        {"LOWER": {"IN": ["policy", "pol."]}},
        {"LOWER": {"IN": ["no.", "no", "number", "#"]}, "OP": "?"},
        {"TEXT": {"REGEX": r"\d{4,12}"}},
    ]},
    # Coverage limits — e.g. "USD 500,000", "$1,000,000 per occurrence"
    {"label": "COVERAGE_LIMIT", "pattern": [
        {"LOWER": {"IN": ["usd", "$", "us$", "zwl"]}},
        {"TEXT": {"REGEX": r"[\d,]+(?:\.\d{2})?"}}
    ]},
    {"label": "COVERAGE_LIMIT", "pattern": [
        {"TEXT": {"REGEX": r"[\d,]+(?:\.\d{2})?"}},
        {"LOWER": {"IN": ["per", "each"]}},
        {"LOWER": {"IN": ["occurrence", "accident", "event", "claim"]}}
    ]},
    # Premium — e.g. "annual premium of USD 12,000"
    {"label": "PREMIUM", "pattern": [
        {"LOWER": {"IN": ["premium", "premiums"]}},
        {"LOWER": {"IN": ["of", "is", "shall", "payable"]}, "OP": "?"},
        {"LOWER": {"IN": ["usd", "$"]}, "OP": "?"},
        {"TEXT": {"REGEX": r"[\d,]+(?:\.\d{2})?"}}
    ]},
    # Deductible / excess — e.g. "deductible of USD 5,000"
    {"label": "DEDUCTIBLE", "pattern": [
        {"LOWER": {"IN": ["deductible", "excess", "retention"]}},
        {"LOWER": {"IN": ["of", "is", "shall"]}, "OP": "?"},
        {"LOWER": {"IN": ["usd", "$"]}, "OP": "?"},
        {"TEXT": {"REGEX": r"[\d,]+(?:\.\d{2})?"}}
    ]},
    # Policy period — e.g. "from 1 January 2024 to 31 December 2024"
    {"label": "POLICY_PERIOD", "pattern": [
        {"LOWER": "from"},
        {"OP": "+"},
        {"LOWER": "to"},
        {"OP": "+"},
    ]},
    # Exclusion flags — opening words of common exclusionary phrases
    {"label": "EXCLUSION", "pattern": [{"LOWER": "excluding"}, {"OP": "+"}]},
    {"label": "EXCLUSION", "pattern": [{"LOWER": "this"}, {"LOWER": "policy"}, {"LOWER": "does"}, {"LOWER": "not"}, {"LOWER": "cover"}]},
    {"label": "EXCLUSION", "pattern": [{"LOWER": "not"}, {"LOWER": "covered"}, {"LOWER": "under"}, {"LOWER": "this"}, {"LOWER": "policy"}]},
    # Clause references — e.g. "Clause 4.1", "Section 7", "Article III"
    {"label": "CLAUSE_REF", "pattern": [
        {"LOWER": {"IN": ["clause", "section", "article", "paragraph"]}},
        {"TEXT": {"REGEX": r"\d+(?:\.\d+)*|[IVXLCDM]+"}}
    ]},
    # Insurer company names (common Zimbabwean insurers)
    {"label": "INSURER", "pattern": [{"LOWER": "nicoz"}, {"LOWER": {"IN": ["diamond", "insurance"]}, "OP": "?"}]},
    {"label": "INSURER", "pattern": [{"LOWER": "fml"}, {"LOWER": {"IN": ["risk", "insurance"]}, "OP": "?"}]},
    {"label": "INSURER", "pattern": [{"LOWER": "zimnat"}, {"LOWER": {"IN": ["lion", "insurance", "general"]}, "OP": "?"}]},
    {"label": "INSURER", "pattern": [{"LOWER": "sanctuary"}, {"LOWER": "insurance"}]},
    {"label": "INSURER", "pattern": [{"LOWER": "cell"}, {"LOWER": "insurance"}]},
    {"label": "INSURER", "pattern": [{"LOWER": "first"}, {"LOWER": "mutual"}, {"LOWER": {"IN": ["life", "insurance"]}, "OP": "?"}]},
    {"label": "INSURER", "pattern": [{"LOWER": "emerald"}, {"LOWER": "insurance"}]},
    {"label": "INSURER", "pattern": [{"LOWER": "old"}, {"LOWER": "mutual"}, {"LOWER": "insurance", "OP": "?"}]},
    {"label": "INSURER", "pattern": [{"LOWER": "life"}, {"LOWER": "guarantee"}, {"LOWER": "insurance"}]},
    {"label": "INSURER", "pattern": [{"LOWER": "altfin"}, {"LOWER": "insurance"}]},
]


@dataclass
class ExtractedEntity:
    """A single named entity extracted from document text."""
    text: str          # The raw text span that was matched
    label: str         # Entity type label (e.g. "PREMIUM", "POLICY_NUMBER")
    start: int         # Character offset start in the source text
    end: int           # Character offset end in the source text
    confidence: float  # Confidence score 0.0–1.0 (1.0 for ruler, 0.85 for model)


class InsuranceEntityRuler:
    """
    Wraps a spaCy pipeline with custom EntityRuler patterns for insurance documents.
    Lazy-loads the spaCy model to avoid startup cost when model is not installed.
    """

    _nlp: object = None  # Cached spaCy Language object

    @classmethod
    def _load_nlp(cls) -> object | None:
        """Load spaCy pipeline with insurance EntityRuler, caching the result."""
        if cls._nlp is not None:
            return cls._nlp

        try:
            import spacy

            # Try custom fine-tuned model first, then base model
            from pathlib import Path
            custom_model = Path("storage/models/app/ner_model")
            if custom_model.exists():
                nlp = spacy.load(str(custom_model))
                logger.info("Loaded custom NER model from %s", custom_model)
            else:
                nlp = spacy.load("en_core_web_sm")
                logger.info("Loaded spaCy en_core_web_sm base model")

            # Add insurance-specific EntityRuler before the NER component
            ruler = nlp.add_pipe("entity_ruler", before="ner" if "ner" in nlp.pipe_names else "last")
            ruler.add_patterns(_INSURANCE_PATTERNS)

            cls._nlp = nlp
            return nlp

        except OSError as exc:
            logger.warning(
                "spaCy model not installed: %s. "
                "Run: python -m spacy download en_core_web_sm",
                exc,
            )
            return None
        except Exception as exc:
            logger.error("Failed to load NER pipeline: %s", exc, exc_info=True)
            return None


def run_ner_pipeline(text: str) -> list[ExtractedEntity]:
    """
    Run the full NER extraction pipeline on insurance document text.
    Returns a list of ExtractedEntity objects.
    Returns an empty list (with a warning) if spaCy model is not installed — never raises.

    Args:
        text: Plain text extracted from an insurance document.

    Returns:
        List of ExtractedEntity, deduplicated and sorted by start offset.
    """
    if not text or not text.strip():
        return []

    nlp = InsuranceEntityRuler._load_nlp()
    if nlp is None:
        # Model not available — return empty rather than crash
        return []

    try:
        # Truncate to avoid memory issues on very large documents
        truncated = text[:100_000]
        doc = nlp(truncated)

        entities: list[ExtractedEntity] = []
        seen_spans: set[tuple[int, int]] = set()

        for ent in doc.ents:
            # Skip duplicates (same span can be matched by ruler + ner)
            span_key = (ent.start_char, ent.end_char)
            if span_key in seen_spans:
                continue
            seen_spans.add(span_key)

            # Map spaCy standard labels to insurance domain labels
            label = _map_spacy_label(ent.label_)
            if label is None:
                continue  # Discard irrelevant standard entity types

            confidence = 1.0 if ent.ent_id_ else 0.85  # ruler vs model
            entities.append(ExtractedEntity(
                text=ent.text,
                label=label,
                start=ent.start_char,
                end=ent.end_char,
                confidence=confidence,
            ))

        return sorted(entities, key=lambda e: e.start)

    except Exception as exc:
        logger.error("run_ner_pipeline failed: %s", exc, exc_info=True)
        return []


# Mapping from spaCy standard labels to insurance domain labels.
# Labels not listed here are filtered out.
_SPACY_LABEL_MAP: dict[str, str] = {
    "MONEY":          "COVERAGE_LIMIT",
    "DATE":           "POLICY_PERIOD",
    "ORG":            "INSURER",
    "PERSON":         "INSURED",
    "CARDINAL":       "COVERAGE_LIMIT",
    # Insurance-specific labels pass through unchanged
    "POLICY_NUMBER":  "POLICY_NUMBER",
    "COVERAGE_LIMIT": "COVERAGE_LIMIT",
    "PREMIUM":        "PREMIUM",
    "DEDUCTIBLE":     "DEDUCTIBLE",
    "POLICY_PERIOD":  "POLICY_PERIOD",
    "EXCLUSION":      "EXCLUSION",
    "CLAUSE_REF":     "CLAUSE_REF",
    "INSURER":        "INSURER",
}


def _map_spacy_label(spacy_label: str) -> str | None:
    """Map a spaCy entity label to an insurance domain label, or None to discard."""
    return _SPACY_LABEL_MAP.get(spacy_label)
