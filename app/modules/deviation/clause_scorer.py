"""
ClauseDeviationScorer — scores how far each clause in a document deviates
from the closest standard clause in the knowledge base.

Standard clause embeddings are cached as a numpy array at init to avoid
re-embedding on every request.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Deviation label thresholds
_DEVIATION_LABELS = [
    (0.10, "standard"),
    (0.30, "minor_deviation"),
    (0.55, "material_deviation"),
    (1.01, "significant_deviation"),
]


class ClauseDeviationScorer:
    """
    Loads standard clauses from DB, caches their embeddings, and scores
    submitted clause texts against the standard library.
    """

    def __init__(self, db) -> None:
        """
        Load all standard clauses from the DB and embed them.
        `db` is a SQLAlchemy Session.
        """
        self._standard_clauses: list[dict[str, Any]] = []
        self._embeddings: np.ndarray | None = None
        self._load_standards(db)

    def _load_standards(self, db) -> None:
        """Fetch standard clauses and embed them into a numpy cache."""
        from app.modules.deviation.model import StandardClause
        from app.ai.rag.vector_store import _get_st_model

        rows = db.query(StandardClause).all()
        if not rows:
            logger.warning(
                "No standard clauses in DB. Run KnowledgeBaseSeeder.seed_knowledge_base() first."
            )
            return

        self._standard_clauses = [
            {
                "id": r.id,
                "text": r.text,
                "clause_type": r.clause_type,
                "source": r.source,
                "jurisdiction": r.jurisdiction,
            }
            for r in rows
        ]

        try:
            model = _get_st_model()
            texts = [c["text"] for c in self._standard_clauses]
            embs  = model.encode(texts, show_progress_bar=False)
            self._embeddings = embs / (
                np.linalg.norm(embs, axis=1, keepdims=True) + 1e-10
            )  # unit-normalised
            logger.info(
                "ClauseDeviationScorer loaded %d standard clauses.", len(rows)
            )
        except Exception as exc:
            logger.error("Failed to embed standard clauses: %s", exc)
            self._embeddings = None

    # ------------------------------------------------------------------
    # Score a single clause
    # ------------------------------------------------------------------

    def score_clause(
        self, clause_text: str, clause_type: str
    ) -> Dict[str, Any]:
        """
        Score a single clause against the standard library.
        Returns deviation_score (0 = identical, 1 = completely different),
        deviation_label, closest standard clause info, and risk_implication.
        """
        if self._embeddings is None or not self._standard_clauses:
            return _empty_score(clause_text, clause_type)

        from app.ai.rag.vector_store import _get_st_model
        model = _get_st_model()

        try:
            emb = model.encode([clause_text], show_progress_bar=False)[0]
            emb = emb / (np.linalg.norm(emb) + 1e-10)
        except Exception as exc:
            logger.error("Clause embedding failed: %s", exc)
            return _empty_score(clause_text, clause_type)

        # Filter to clauses of matching type (or use all if none match)
        type_indices = [
            i for i, c in enumerate(self._standard_clauses)
            if c["clause_type"] == clause_type
        ]
        if not type_indices:
            type_indices = list(range(len(self._standard_clauses)))

        subset_emb    = self._embeddings[type_indices]  # (k, dim)
        subset_meta   = [self._standard_clauses[i] for i in type_indices]

        # Cosine similarity against filtered subset
        similarities = subset_emb @ emb  # (k,)
        best_idx     = int(np.argmax(similarities))
        best_sim     = float(similarities[best_idx])
        best_meta    = subset_meta[best_idx]

        deviation_score = round(1.0 - best_sim, 4)
        deviation_label = _label_from_score(deviation_score)
        risk_implication = _generate_risk_implication(
            clause_type, deviation_label, deviation_score
        )

        return {
            "deviation_score": deviation_score,
            "deviation_label": deviation_label,
            "closest_standard_clause_id": best_meta["id"],
            "closest_standard_clause_text": best_meta["text"],
            "closest_standard_source": best_meta["source"],
            "similarity_to_standard": round(best_sim, 4),
            "risk_implication": risk_implication,
        }

    # ------------------------------------------------------------------
    # Score all clauses in a document
    # ------------------------------------------------------------------

    def score_document(
        self, document_id: int, db
    ) -> Dict[str, Any]:
        """
        Score all clause-type entities extracted for a document.
        Saves results to clause_deviation_scores table.
        Returns aggregated scoring summary.
        """
        from app.modules.circulars.model import CircularAnalysis
        from app.modules.documents.model import Document
        from app.modules.deviation.model import ClauseDeviationScore
        from app.modules.comparison.service import _classify_clause_type

        # Get document text
        analysis = (
            db.query(CircularAnalysis)
            .filter(CircularAnalysis.document_id == document_id)
            .first()
        )

        text = ""
        if analysis and analysis.extracted_text:
            text = analysis.extracted_text

        if not text:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                from app.modules.circulars.extractor import extract_text, clean_text
                text = clean_text(extract_text(doc.file_path))

        if not text:
            return {
                "document_id": document_id,
                "total_clauses_scored": 0,
                "deviation_summary": {},
                "high_deviation_clauses": [],
                "avg_deviation_score": 0.0,
                "scores": [],
            }

        # Extract clause-like blocks (reuse comparison logic)
        from app.modules.comparison.service import ComparisonService
        svc = ComparisonService()
        clauses = svc._extract_clauses(document_id, db)

        scores_list = []
        label_counts: Dict[str, int] = {
            "standard": 0,
            "minor_deviation": 0,
            "material_deviation": 0,
            "significant_deviation": 0,
        }

        for clause in clauses:
            clause_type = clause.get("clause_type", "general")
            clause_text = clause.get("text", "")
            if not clause_text:
                continue

            result = self.score_clause(clause_text, clause_type)
            label = result.get("deviation_label", "standard")
            label_counts[label] = label_counts.get(label, 0) + 1

            # Persist the score
            try:
                score_row = ClauseDeviationScore(
                    document_id=document_id,
                    circular_analysis_id=analysis.id if analysis else None,
                    clause_text=clause_text[:2000],
                    clause_type=clause_type,
                    deviation_score=result["deviation_score"],
                    deviation_label=label,
                    closest_standard_clause_id=result.get("closest_standard_clause_id"),
                    similarity_to_standard=result.get("similarity_to_standard"),
                    risk_implication=result.get("risk_implication"),
                )
                db.add(score_row)
            except Exception as exc:
                logger.warning("Failed to save deviation score: %s", exc)

            scores_list.append({
                "clause_type": clause_type,
                "clause_text": clause_text[:300],
                **result,
            })

        try:
            db.commit()
        except Exception as exc:
            logger.error("Failed to commit deviation scores: %s", exc)
            db.rollback()

        avg_score = (
            sum(s["deviation_score"] for s in scores_list) / len(scores_list)
            if scores_list else 0.0
        )
        high_deviation = [
            s for s in scores_list if s.get("deviation_score", 0) > 0.55
        ]

        return {
            "document_id": document_id,
            "total_clauses_scored": len(scores_list),
            "deviation_summary": label_counts,
            "high_deviation_clauses": high_deviation,
            "avg_deviation_score": round(avg_score, 4),
            "scores": scores_list,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _label_from_score(score: float) -> str:
    for threshold, label in _DEVIATION_LABELS:
        if score <= threshold:
            return label
    return "significant_deviation"


def _generate_risk_implication(
    clause_type: str, deviation_label: str, deviation_score: float
) -> str:
    if clause_type == "exclusion" and deviation_label in (
        "material_deviation", "significant_deviation"
    ):
        return (
            "This exclusion clause deviates significantly from standard wording. "
            "Review carefully for broadened exclusion scope."
        )
    if clause_type == "coverage" and deviation_score > 0.30:
        return (
            "Coverage clause deviates from standard. "
            "Verify coverage limits and conditions are adequate."
        )
    if deviation_label == "standard":
        return "Clause conforms to standard market wording."
    return (
        f"Clause shows {deviation_label.replace('_', ' ')}. "
        "Review against standard wording."
    )


def _empty_score(clause_text: str, clause_type: str) -> Dict[str, Any]:
    return {
        "deviation_score": None,
        "deviation_label": "unknown",
        "closest_standard_clause_id": None,
        "closest_standard_clause_text": None,
        "closest_standard_source": None,
        "similarity_to_standard": None,
        "risk_implication": "Standard clause library is empty. Seed knowledge base first.",
    }


# ---------------------------------------------------------------------------
# Module-level singleton per DB session is not feasible (different sessions
# per request), so callers instantiate with: ClauseDeviationScorer(db).
# For efficiency, the standard clause embeddings are a class-level cache that
# persists after the first instantiation.
# ---------------------------------------------------------------------------
_cached_scorer: ClauseDeviationScorer | None = None


def get_clause_scorer(db) -> ClauseDeviationScorer:
    """Return a scorer, reloading standard clause embeddings if the DB changes."""
    global _cached_scorer
    if _cached_scorer is None:
        _cached_scorer = ClauseDeviationScorer(db)
    return _cached_scorer
