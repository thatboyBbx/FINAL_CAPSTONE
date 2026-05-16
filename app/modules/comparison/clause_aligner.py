"""
ClauseAligner — aligns clauses from two documents using sentence embeddings
and the Hungarian algorithm (optimal one-to-one matching).

Requires: sentence-transformers, scipy
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class ClauseAligner:
    """
    Aligns clause lists from two documents.
    Reuses the module-level SentenceTransformer singleton from the RAG module
    to avoid loading the model twice.
    """

    def align(
        self,
        clauses_a: List[Dict[str, Any]],
        clauses_b: List[Dict[str, Any]],
        similarity_threshold: float = 0.75,
    ) -> List[Dict[str, Any]]:
        """
        Compute optimal one-to-one alignment between clauses_a and clauses_b.

        Each clause dict has at minimum: clause_id, clause_type, text, char_start, char_end.

        Returns a list of alignment dicts with status:
          'identical'  — same wording (similarity == 1.0)
          'modified'   — matched but wording changed (similarity >= threshold)
          'removed'    — in A but no acceptable match in B
          'added'      — in B but no acceptable match in A
        """
        if not clauses_a and not clauses_b:
            return []

        # Handle degenerate cases
        if not clauses_a:
            return [_alignment("added", None, cb) for cb in clauses_b]
        if not clauses_b:
            return [_alignment("removed", ca, None) for ca in clauses_a]

        # Embed all clause texts
        from app.ai.rag.vector_store import _get_st_model
        model = _get_st_model()

        texts_a = [c.get("text", "") for c in clauses_a]
        texts_b = [c.get("text", "") for c in clauses_b]

        try:
            emb_a = model.encode(texts_a, show_progress_bar=False)  # (n_a, dim)
            emb_b = model.encode(texts_b, show_progress_bar=False)  # (n_b, dim)
        except Exception as exc:
            logger.error("Embedding failed in ClauseAligner: %s", exc)
            return []

        # Compute cosine similarity matrix
        sim_matrix = _cosine_similarity_matrix(emb_a, emb_b)  # (n_a, n_b)

        # Hungarian algorithm on the cost matrix (1 - similarity)
        try:
            from scipy.optimize import linear_sum_assignment
            row_idx, col_idx = linear_sum_assignment(1.0 - sim_matrix)
        except ImportError:
            logger.error("scipy is required for ClauseAligner. pip install scipy")
            return []

        matched_a: set[int] = set()
        matched_b: set[int] = set()
        alignments: List[Dict[str, Any]] = []

        for r, c in zip(row_idx, col_idx):
            sim = float(sim_matrix[r, c])
            if sim >= similarity_threshold:
                # Determine status based on similarity
                if abs(sim - 1.0) < 1e-6:
                    status = "identical"
                else:
                    status = "modified"
                alignments.append(
                    _alignment(status, clauses_a[r], clauses_b[c], sim)
                )
                matched_a.add(r)
                matched_b.add(c)
            # Below threshold — both clauses treated as unmatched

        # Unmatched clauses from A → removed
        for i, ca in enumerate(clauses_a):
            if i not in matched_a:
                alignments.append(_alignment("removed", ca, None))

        # Unmatched clauses from B → added
        for j, cb in enumerate(clauses_b):
            if j not in matched_b:
                alignments.append(_alignment("added", None, cb))

        return alignments


def _cosine_similarity_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute pairwise cosine similarity between two embedding matrices."""
    # Normalize rows to unit vectors
    norm_a = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-10)
    norm_b = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return norm_a @ norm_b.T  # (n_a, n_b)


def _alignment(
    status: str,
    clause_a: dict[str, Any] | None,
    clause_b: dict[str, Any] | None,
    similarity: float = 0.0,
) -> dict[str, Any]:
    """Build a standardised alignment result dict."""
    clause_type = (
        (clause_a or clause_b or {}).get("clause_type", "unknown")
    )
    return {
        "status": status,
        "similarity_score": round(similarity, 4),
        "clause_a": clause_a,
        "clause_b": clause_b,
        "clause_type": clause_type,
        "change_summary": _describe_change(status, clause_a, clause_b, similarity),
    }


def _describe_change(
    status: str,
    clause_a: dict | None,
    clause_b: dict | None,
    similarity: float,
) -> str:
    """Generate a short human-readable description of the change."""
    if status == "identical":
        return "Clause is identical in both documents."
    if status == "added":
        ctype = (clause_b or {}).get("clause_type", "clause")
        return f"New {ctype} clause added in document B."
    if status == "removed":
        ctype = (clause_a or {}).get("clause_type", "clause")
        return f"{ctype.capitalize()} clause removed in document B."
    # modified
    pct = round((1.0 - similarity) * 100, 1)
    ctype = (clause_a or {}).get("clause_type", "clause")
    return (
        f"{ctype.capitalize()} clause modified "
        f"({pct}% deviation from document A wording)."
    )
