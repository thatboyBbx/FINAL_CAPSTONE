"""
Insurance-specific Named Entity Recognition (NER) service.

Extracts 8 entity types from insurance documents:
  COVERAGE_AMOUNT  — monetary coverage limits (e.g. "$1,000,000 per occurrence")
  PREMIUM          — premium amounts and payment schedules
  DEDUCTIBLE       — deductible / excess amounts
  POLICY_PERIOD    — policy start / end dates and terms
  POLICY_NUMBER    — policy identification numbers
  INSURER          — insurance company names
  INSURED          — policyholder names / organisations
  EXCLUSION        — exclusionary clauses

Extraction strategy (in order):
  1. Fine-tuned spaCy model at storage/models/app/ner_model  (if available)
  2. Fallback: en_core_web_sm base model
  3. Blank spaCy model  (last resort — regex only)
  4. Regex patterns    — supplement spaCy for insurance-specific tokens
  5. Deduplication     — remove overlapping / duplicate spans
  6. Persistence       — save to extracted_entities table
"""

import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

# Path where scripts/train_ner_model.py saves the custom model
_CUSTOM_MODEL_PATH = Path("storage/models/app/ner_model")

# Maximum characters fed to spaCy in one call (performance guard for huge PDFs)
_MAX_TEXT_CHARS = 100_000

# Mapping from spaCy standard label → insurance entity type.
# Only labels listed here are retained; all others are discarded.
_SPACY_LABEL_MAP: dict[str, str] = {
    "MONEY":  "COVERAGE_AMOUNT",   # monetary values → coverage amounts
    "DATE":   "POLICY_PERIOD",     # dates / date ranges → policy period
    "ORG":    "INSURER",           # organisations → insurer names
    "PERSON": "INSURED",           # person names → insured / policyholder
}

# Insurance domain keywords used to boost confidence when found in context
_CONTEXT_KEYWORDS: frozenset[str] = frozenset({
    "policy", "coverage", "premium", "deductible", "insured", "insurer",
    "limit", "reinsurance", "treaty", "clause", "schedule", "endorsement",
    "exclusion", "peril", "loss", "claim", "benefit", "indemnity",
    "aggregate", "occurrence", "retention", "excess", "renewal",
})


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------

class EntityExtractionService:
    """
    Extracts insurance-specific named entities from document text.

    Typical usage::

        service = EntityExtractionService()
        result  = service.extract_entities(document_id=42, text="...", db=db)

    The returned dict has the shape::

        {
            "entities_found":     42,
            "entities_by_type":   {"COVERAGE_AMOUNT": 5, "PREMIUM": 2, ...},
            "entities":           [...],
            "processing_time_ms": 1234.56,
        }
    """

    def __init__(self) -> None:
        # Load NER model at startup so the first extraction call is not slow.
        self._nlp = self._load_nlp_model()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_nlp_model(self):
        """
        Load the best available spaCy NER model.

        Priority:
          1. Custom fine-tuned insurance model (storage/models/app/ner_model)
          2. Generic en_core_web_sm
          3. Blank en model (regex-only fallback)

        Returns a loaded spaCy Language object.
        """
        import spacy  # noqa: PLC0415 — deferred so server starts even if spacy missing

        # ── 1. Custom fine-tuned model ──────────────────────────────────────
        if _CUSTOM_MODEL_PATH.exists():
            try:
                nlp = spacy.load(str(_CUSTOM_MODEL_PATH))
                logger.info(
                    "EntityExtractionService: loaded custom NER model from %s",
                    _CUSTOM_MODEL_PATH,
                )
                return nlp
            except Exception as exc:
                logger.warning(
                    "EntityExtractionService: custom model load failed (%s) "
                    "— falling back to en_core_web_sm",
                    exc,
                )

        # ── 2. Generic en_core_web_sm ───────────────────────────────────────
        try:
            nlp = spacy.load("en_core_web_sm")
            logger.info(
                "EntityExtractionService: loaded base model en_core_web_sm"
            )
            return nlp
        except OSError:
            logger.error(
                "EntityExtractionService: en_core_web_sm not installed. "
                "Run:  python -m spacy download en_core_web_sm"
            )

        # ── 3. Blank model — regex extraction still works ───────────────────
        nlp = spacy.blank("en")
        logger.warning(
            "EntityExtractionService: using blank spaCy model — "
            "only regex extraction is active"
        )
        return nlp

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_entities(
        self,
        document_id: int,
        text: str,
        db: Session,
    ) -> dict[str, Any]:
        """
        Extract all insurance entities from *text* and persist them to the
        ``extracted_entities`` database table.

        Parameters
        ----------
        document_id:
            Primary key of the Document record.
        text:
            Full plain-text content of the document.
        db:
            Active SQLAlchemy session — used to write entities and commit.

        Returns
        -------
        dict with keys: entities_found, entities_by_type, entities,
        processing_time_ms.
        """
        start = time.perf_counter()

        # Guard: truncate extremely long texts to keep spaCy fast
        if len(text) > _MAX_TEXT_CHARS:
            logger.warning(
                "Document %d: text truncated from %d to %d chars for NER",
                document_id, len(text), _MAX_TEXT_CHARS,
            )
            text = text[:_MAX_TEXT_CHARS]

        raw_entities: list[dict[str, Any]] = []

        # ── Pass 1: spaCy NER ───────────────────────────────────────────────
        try:
            doc = self._nlp(text)
            for span in doc.ents:
                entity_type = self._map_entity_type(span.label_)
                if entity_type is None:
                    continue  # label not relevant to insurance domain
                confidence = self._calculate_confidence(span)
                raw_entities.append({
                    "entity_type":      entity_type,
                    "entity_value":     span.text.strip(),
                    "start_char":       span.start_char,
                    "end_char":         span.end_char,
                    "confidence_score": confidence,
                    "source":           "spacy",
                })
        except Exception as exc:
            logger.error(
                "Document %d: spaCy NER pass failed — %s", document_id, exc
            )

        # ── Pass 2: Regex supplement ────────────────────────────────────────
        try:
            regex_entities = self._extract_patterns(text)
            raw_entities.extend(regex_entities)
        except Exception as exc:
            logger.error(
                "Document %d: regex extraction failed — %s", document_id, exc
            )

        # ── Deduplicate overlapping / duplicate spans ───────────────────────
        deduped = self._deduplicate(raw_entities)

        # ── Persist to database ─────────────────────────────────────────────
        saved: list[dict[str, Any]] = []
        try:
            saved = self._save_entities(document_id, deduped, db)
        except Exception as exc:
            logger.error(
                "Document %d: failed to persist entities — %s",
                document_id, exc,
            )

        # ── Build summary ───────────────────────────────────────────────────
        by_type: dict[str, int] = {}
        for ent in saved:
            by_type[ent["entity_type"]] = by_type.get(ent["entity_type"], 0) + 1

        elapsed_ms = (time.perf_counter() - start) * 1_000
        logger.info(
            "Document %d: extracted %d entities in %.1f ms",
            document_id, len(saved), elapsed_ms,
        )

        return {
            "entities_found":     len(saved),
            "entities_by_type":   by_type,
            "entities":           saved,
            "processing_time_ms": round(elapsed_ms, 2),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _map_entity_type(self, spacy_label: str) -> str | None:
        """
        Translate a spaCy standard label to an insurance entity type.
        Returns ``None`` for labels that have no insurance-domain relevance
        (e.g. GPE, NORP, CARDINAL) so they are silently ignored.
        """
        return _SPACY_LABEL_MAP.get(spacy_label)

    def _extract_patterns(self, text: str) -> list[dict[str, Any]]:
        """
        Apply insurance-specific regex patterns to supplement spaCy.

        Each pattern is a (entity_type, regex_string) tuple. The first
        capturing group is used as the entity value; when no group exists
        the full match is used.

        Patterns cover:
          - Coverage amounts / policy limits
          - Premium payments (annual, monthly, quarterly)
          - Deductibles and self-insured retentions
          - Policy numbers / certificate numbers
          - Policy periods (date ranges)
          - Exclusion clauses
        """
        entities: list[dict[str, Any]] = []

        # Each tuple: (entity_type, pattern_string)
        patterns: list[tuple[str, str]] = [

            # ── Coverage amounts ──────────────────────────────────────────
            (
                "COVERAGE_AMOUNT",
                r"(\$[\d,]+(?:\.\d{2})?\s*(?:million|M|billion|B)?)"
                r"(?:\s+(?:per\s+(?:occurrence|event|claim|annum|year)|coverage"
                r"|limit|sum\s+insured|aggregate|maximum|indemnity))",
            ),
            (
                "COVERAGE_AMOUNT",
                r"(?:limit(?:s)?\s+of\s+(?:liability|indemnity)|sum\s+insured"
                r"|(?:total\s+)?coverage\s+limit)"
                r"\s*(?:of|:)?\s*(\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|M))?)",
            ),

            # ── Premiums ──────────────────────────────────────────────────
            (
                "PREMIUM",
                r"(?:annual\s+)?premium\s*(?:of|:)?\s*(\$[\d,]+(?:\.\d{2})?)"
                r"(?:\s+(?:annually|per\s+annum|monthly|quarterly|per\s+year))?",
            ),
            (
                "PREMIUM",
                r"(?:total\s+)?(?:reinsurance\s+)?premium\s*:\s*"
                r"(\$[\d,]+(?:\.\d{2})?)",
            ),

            # ── Deductibles ───────────────────────────────────────────────
            (
                "DEDUCTIBLE",
                r"(\$[\d,]+(?:\.\d{2})?)\s+"
                r"(?:deductible|excess|self[- ]insured\s+retention)",
            ),
            (
                "DEDUCTIBLE",
                r"(?:deductible|excess|retention)\s*(?:of|:)?\s*"
                r"(\$[\d,]+(?:\.\d{2})?)",
            ),

            # ── Policy numbers ────────────────────────────────────────────
            (
                "POLICY_NUMBER",
                r"[Pp]olicy\s+(?:[Nn][Oo]\.?|[Nn]umber|#)\s*:?\s*"
                r"([A-Z0-9][A-Z0-9\-/]{5,24})",
            ),
            (
                "POLICY_NUMBER",
                r"(?:Certificate|Contract)\s+(?:[Nn]o\.?|[Nn]umber)\s*:?\s*"
                r"([A-Z0-9\-]{6,20})",
            ),

            # ── Policy periods ────────────────────────────────────────────
            (
                "POLICY_PERIOD",
                r"(?:policy\s+period|period\s+of\s+(?:cover(?:age)?|insurance)"
                r"|effective\s+(?:date|period))\s*:?\s*"
                r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}"
                r"\s+(?:to|through|–|—|-)\s*"
                r"\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
            ),
            (
                "POLICY_PERIOD",
                r"(?:from|commencing)\s+"
                r"(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})"
                r"\s+(?:to|until|through)\s+"
                r"(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})",
            ),

            # ── Exclusions ────────────────────────────────────────────────
            (
                "EXCLUSION",
                r"(?:this\s+policy\s+does\s+not\s+cover"
                r"|excluded?\s+from\s+coverage"
                r"|exclusion(?:s)?\s*(?:include|apply|:|—)\s*)"
                r"(.{10,120}?)(?:\.|;|\n)",
            ),
            (
                "EXCLUSION",
                r"(?:shall\s+not\s+be\s+liable|no\s+coverage\s+for"
                r"|not\s+covered\s+(?:under|by)\s+this\s+policy)\s*"
                r"(.{10,100}?)(?:\.|;|\n|$)",
            ),
        ]

        for entity_type, pattern_str in patterns:
            try:
                compiled = re.compile(pattern_str, re.IGNORECASE | re.DOTALL)
                for match in compiled.finditer(text):
                    # Use the first non-None capturing group, else full match
                    groups = [g for g in match.groups() if g is not None]
                    value = groups[0].strip() if groups else match.group(0).strip()
                    if not value or len(value) < 2:
                        continue
                    entities.append({
                        "entity_type":      entity_type,
                        "entity_value":     value,
                        "start_char":       match.start(),
                        "end_char":         match.end(),
                        "confidence_score": 0.78,   # regex baseline confidence
                        "source":           "regex",
                    })
            except re.error as exc:
                logger.warning(
                    "Regex compile error for %s: %s", entity_type, exc
                )

        return entities

    def _calculate_confidence(self, span) -> float:
        """
        Heuristic confidence score for a spaCy entity span.

        Base score: 0.75
        +0.05  entity has ≥ 3 tokens  (longer spans are more specific)
        +0.05  entity has ≥ 6 tokens  (very specific mention)
        +0.05  sentence contains ≥ 1 insurance keyword
        +0.05  sentence contains ≥ 3 insurance keywords  (strong context)

        Capped at 1.0.
        """
        score = 0.75

        # Length bonus — longer entities are typically more precise
        if len(span) >= 3:
            score += 0.05
        if len(span) >= 6:
            score += 0.05

        # Context bonus — presence of insurance keywords in the same sentence
        try:
            sent_lower = span.sent.text.lower()
            hits = sum(1 for kw in _CONTEXT_KEYWORDS if kw in sent_lower)
            if hits >= 1:
                score += 0.05
            if hits >= 3:
                score += 0.05
        except Exception:
            # span.sent raises on blank model — safe to ignore
            pass

        return min(round(score, 4), 1.0)

    def _deduplicate(
        self, entities: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Remove overlapping spans and exact-duplicate (type, value) pairs.

        Strategy:
          1. Sort by start_char ASC, confidence DESC.
          2. Walk the list: skip any span whose start falls inside the
             previous kept span (overlap elimination).
          3. Secondary pass: drop same (entity_type, normalised_value) pairs.
        """
        # Sort: earlier start first; for ties keep highest confidence
        sorted_ents = sorted(
            entities,
            key=lambda e: (e["start_char"], -e["confidence_score"]),
        )

        # Pass 1 — remove overlapping spans
        kept: list[dict[str, Any]] = []
        last_end = -1
        for ent in sorted_ents:
            if ent["start_char"] < last_end:
                continue   # overlaps with the previously kept entity
            kept.append(ent)
            last_end = ent["end_char"]

        # Pass 2 — remove same (type, value) duplicates
        seen: set[tuple[str, str]] = set()
        final: list[dict[str, Any]] = []
        for ent in kept:
            key = (ent["entity_type"], ent["entity_value"].lower().strip())
            if key in seen:
                continue
            seen.add(key)
            final.append(ent)

        return final

    def _save_entities(
        self,
        document_id: int,
        entities: list[dict[str, Any]],
        db: Session,
    ) -> list[dict[str, Any]]:
        """
        Persist the extracted entities to the ``extracted_entities`` table.

        Any pre-existing entities for this document are deleted first so
        re-extraction always produces a clean result.

        Returns a list of dicts representing the saved records (including
        auto-assigned ``id`` values).
        """
        # Lazy import prevents circular import at module load time
        from app.modules.documents.model import ExtractedEntity  # noqa: PLC0415

        # Remove stale entities from a previous extraction run
        db.query(ExtractedEntity).filter(
            ExtractedEntity.document_id == document_id
        ).delete(synchronize_session=False)

        now = datetime.now(timezone.utc)
        saved: list[dict[str, Any]] = []

        for ent in entities:
            record = ExtractedEntity(
                document_id=document_id,
                entity_type=ent["entity_type"],
                entity_value=ent["entity_value"],
                start_char=ent["start_char"],
                end_char=ent["end_char"],
                confidence_score=ent["confidence_score"],
                extracted_at=now,
            )
            db.add(record)
            db.flush()   # ensure record.id is populated before we read it

            saved.append({
                "id":            record.id,
                "entity_type":   record.entity_type,
                "entity_value":  record.entity_value,
                "start_char":    record.start_char,
                "end_char":      record.end_char,
                "confidence":    record.confidence_score,
                "is_correct":    record.is_correct,
                "extracted_at":  record.extracted_at.isoformat(),
            })

        db.commit()
        return saved
