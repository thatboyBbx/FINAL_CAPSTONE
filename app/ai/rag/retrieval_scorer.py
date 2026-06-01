"""
app/ai/rag/retrieval_scorer.py
================================
Multi-signal confidence scoring and hallucination reduction for deterministic RAG.

Confidence pipeline:
  semantic_score   = 1.0 − cosine_distance          (ChromaDB cosine, range [0,1])
  keyword_score    = |query_kw ∩ chunk_kw| / |query_kw|
  composite_score  = 0.75 × semantic + 0.25 × keyword

Hallucination flags (non-blocking — callers decide whether to suppress the answer):
  low_confidence        top chunk composite score below min_confidence threshold
  insufficient_chunks   fewer than 2 chunks available
  no_keyword_overlap    zero query keywords found across all retrieved text
  version_mismatch      at least one chunk embedded with a stale model/version
"""
from __future__ import annotations

from typing import Any

from app.ai.nlp.text_utils import extract_keywords

_W_SEMANTIC: float = 0.75
_W_KEYWORD: float = 0.25


def distance_to_semantic_confidence(distance: float) -> float:
    """ChromaDB cosine distance [0, 1] → semantic confidence [0, 1]."""
    return max(0.0, min(1.0, 1.0 - float(distance)))


def keyword_overlap_score(query: str, chunk_text: str) -> float:
    """Fraction of query keywords present in chunk_text (0.0–1.0)."""
    query_kws = set(extract_keywords(query))
    if not query_kws:
        return 0.0
    chunk_lower = chunk_text.lower()
    matched = sum(1 for kw in query_kws if kw in chunk_lower)
    return matched / len(query_kws)


def composite_confidence(query: str, chunk_text: str, distance: float) -> float:
    """Weighted semantic + keyword confidence, rounded to 4 decimal places."""
    semantic = distance_to_semantic_confidence(distance)
    keyword = keyword_overlap_score(query, chunk_text)
    return round(_W_SEMANTIC * semantic + _W_KEYWORD * keyword, 4)


def score_and_filter(
    chunks: list[dict[str, Any]],
    query: str,
    min_confidence: float = 0.0,
) -> list[dict[str, Any]]:
    """
    Attach confidence_score to each chunk, drop those below min_confidence,
    and return sorted descending by confidence_score.
    """
    scored: list[dict[str, Any]] = []
    for chunk in chunks:
        score = composite_confidence(
            query,
            chunk.get("text", ""),
            chunk.get("distance", 1.0),
        )
        enriched = {**chunk, "confidence_score": score}
        if score >= min_confidence:
            scored.append(enriched)
    scored.sort(key=lambda x: x["confidence_score"], reverse=True)
    return scored


def detect_hallucination_risks(
    chunks: list[dict[str, Any]],
    query: str,
    min_confidence: float = 0.3,
    current_embedding_version: str = "v1",
) -> list[str]:
    """
    Inspect scored chunks for signals that the answer may be unreliable.
    Returns a list of flag strings — empty list means no risks detected.
    """
    if not chunks:
        return ["low_confidence", "insufficient_chunks", "no_keyword_overlap"]

    flags: list[str] = []

    if chunks[0].get("confidence_score", 0.0) < min_confidence:
        flags.append("low_confidence")

    if len(chunks) < 2:
        flags.append("insufficient_chunks")

    query_kws = set(extract_keywords(query))
    if query_kws:
        combined = " ".join(c.get("text", "") for c in chunks).lower()
        if not any(kw in combined for kw in query_kws):
            flags.append("no_keyword_overlap")

    for chunk in chunks:
        chunk_version = chunk.get("embedding_version", "")
        if chunk_version and chunk_version != current_embedding_version:
            flags.append("version_mismatch")
            break

    return flags
