"""
app/ai/rag/governance.py
==========================
RAGGovernanceEngine — deterministic retrieval with full audit trail.

Orchestration pipeline per query:
  1. Vector-store semantic retrieval (ChromaDB)
  2. Multi-signal confidence scoring  (retrieval_scorer)
  3. Confidence-threshold filtering   (hallucination gate)
  4. Hallucination risk detection     (retrieval_scorer)
  5. Citation record construction     (citation_tracker)
  6. Answer assembly from top chunks  (grounded, no inference)
  7. Audit log persistence            (RetrievalAuditLog)
  8. Return GovernanceQueryResult

If ChromaDB is unavailable or the document has not been indexed, the engine
falls back to keyword-based retrieval via QAEngine so the caller always
receives a structured response.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.ai.rag.citation_tracker import CitationRecord, build_citations, inline_citation_footer
from app.ai.rag.retrieval_scorer import (
    detect_hallucination_risks,
    score_and_filter,
)

logger = logging.getLogger(__name__)

_DEFAULT_MIN_CONFIDENCE: float = 0.30
_DEFAULT_TOP_K: int = 5
_SUPPRESSED_ANSWER = (
    "No sufficiently reliable passages were retrieved for this query. "
    "Confidence scores were below the minimum threshold ({threshold:.0%}). "
    "Try rephrasing your question or ensure the document has been re-indexed with the "
    "current embedding model."
)


@dataclass
class GovernanceQueryResult:
    answer: str
    citations: list[CitationRecord]
    confidence: float
    hallucination_flags: list[str]
    retrieval_stats: dict[str, Any]
    embedding_model: str
    embedding_version: str
    audit_log_id: int | None
    answer_returned: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "citations": [c.as_dict() for c in self.citations],
            "confidence": self.confidence,
            "hallucination_flags": self.hallucination_flags,
            "retrieval_stats": self.retrieval_stats,
            "embedding_model": self.embedding_model,
            "embedding_version": self.embedding_version,
            "audit_log_id": self.audit_log_id,
            "answer_returned": self.answer_returned,
        }


class RAGGovernanceEngine:
    """
    Governed RAG engine.  One shared instance is created at app startup.

    Parameters
    ----------
    vector_store : VectorStore | None
        ChromaDB-backed store.  If None, falls back to keyword search.
    min_confidence : float
        Default minimum composite confidence score (0–1) below which the
        answer is suppressed and a low_confidence flag is raised.
    top_k : int
        Maximum number of chunks to retrieve from ChromaDB before filtering.
    """

    def __init__(
        self,
        vector_store: Any = None,
        min_confidence: float = _DEFAULT_MIN_CONFIDENCE,
        top_k: int = _DEFAULT_TOP_K,
    ) -> None:
        self._vs = vector_store
        self.min_confidence = min_confidence
        self.top_k = top_k

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def governed_query(
        self,
        document_id: int,
        question: str,
        db: Session,
        user_id: int | None = None,
        min_confidence: float | None = None,
        top_k: int | None = None,
        require_embedding_version: str | None = None,
        document_text: str = "",
    ) -> GovernanceQueryResult:
        """
        Execute a governed RAG query.

        Parameters
        ----------
        document_id            : target document
        question               : user question
        db                     : SQLAlchemy session (for audit log + stale check)
        user_id                : optional — stored in audit log
        min_confidence         : override engine default
        top_k                  : override engine default
        require_embedding_version : only accept chunks with this embedding_version
        document_text          : fallback raw text if ChromaDB unavailable
        """
        from app.core.config import settings

        effective_min_conf = min_confidence if min_confidence is not None else self.min_confidence
        effective_top_k = top_k if top_k is not None else self.top_k
        effective_version = require_embedding_version or settings.embedding_version

        filters_applied = {
            "min_confidence": effective_min_conf,
            "top_k": effective_top_k,
            "require_embedding_version": require_embedding_version,
        }

        # --- semantic retrieval -----------------------------------------
        raw_chunks: list[dict[str, Any]] = []
        retrieval_method = "semantic"
        if self._vs is not None:
            try:
                raw_chunks = self._vs.query(
                    document_id=str(document_id),
                    question=question,
                    top_k=effective_top_k,
                    embedding_version_filter=require_embedding_version,
                )
            except Exception as exc:
                logger.warning(
                    "GovernanceEngine: VectorStore query failed for doc %d: %s — "
                    "falling back to keyword search.",
                    document_id,
                    exc,
                )

        # --- keyword fallback -------------------------------------------
        if not raw_chunks and document_text:
            retrieval_method = "keyword"
            raw_chunks = self._keyword_chunks(document_text, question)

        # --- score + filter ---------------------------------------------
        scored_chunks = score_and_filter(raw_chunks, question, min_confidence=effective_min_conf)

        # --- hallucination risk detection --------------------------------
        flags = detect_hallucination_risks(
            scored_chunks,
            question,
            min_confidence=effective_min_conf,
            current_embedding_version=effective_version,
        )

        # --- build citations --------------------------------------------
        citations = build_citations(scored_chunks, document_id)

        # --- assemble answer --------------------------------------------
        answer_returned = bool(scored_chunks) and "low_confidence" not in flags
        if answer_returned:
            answer = self._assemble_answer(scored_chunks, citations)
            answer_confidence = scored_chunks[0]["confidence_score"]
        else:
            answer = _SUPPRESSED_ANSWER.format(threshold=effective_min_conf)
            answer_confidence = (
                scored_chunks[0]["confidence_score"] if scored_chunks else 0.0
            )

        # --- retrieval stats --------------------------------------------
        all_confs = [c["confidence_score"] for c in scored_chunks]
        retrieval_stats = {
            "chunks_retrieved_raw": len(raw_chunks),
            "chunks_above_threshold": len(scored_chunks),
            "top_confidence": round(all_confs[0], 4) if all_confs else 0.0,
            "mean_confidence": round(sum(all_confs) / len(all_confs), 4) if all_confs else 0.0,
            "retrieval_method": retrieval_method,
        }

        # --- determine provenance model/version -------------------------
        emb_model = settings.embedding_model_name
        emb_version = settings.embedding_version
        if scored_chunks:
            emb_model = scored_chunks[0].get("embedding_model", emb_model)
            emb_version = scored_chunks[0].get("embedding_version", emb_version)

        # --- audit log --------------------------------------------------
        audit_log_id = self._write_audit_log(
            db=db,
            document_id=document_id,
            user_id=user_id,
            query_text=question,
            retrieval_method=retrieval_method,
            scored_chunks=scored_chunks,
            raw_chunk_count=len(raw_chunks),
            flags=flags,
            answer_confidence=answer_confidence,
            filters=filters_applied,
            answer_returned=answer_returned,
            embedding_model=emb_model,
            embedding_version=emb_version,
        )

        return GovernanceQueryResult(
            answer=answer,
            citations=citations,
            confidence=answer_confidence,
            hallucination_flags=flags,
            retrieval_stats=retrieval_stats,
            embedding_model=emb_model,
            embedding_version=emb_version,
            audit_log_id=audit_log_id,
            answer_returned=answer_returned,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _assemble_answer(
        self,
        chunks: list[dict[str, Any]],
        citations: list[CitationRecord],
    ) -> str:
        passage = " ".join(c["text"] for c in chunks[:3])
        footer = inline_citation_footer(citations[:3])
        return f"{passage}\n\n**Sources:**\n{footer}"

    def _keyword_chunks(
        self,
        document_text: str,
        question: str,
    ) -> list[dict[str, Any]]:
        from app.ai.nlp.text_utils import score_sentences, extract_keywords

        keywords = extract_keywords(question)
        if not keywords:
            return []
        scored = score_sentences(document_text, keywords)
        chunks = []
        for score, sentence, idx in scored[:self.top_k]:
            if not sentence.strip():
                continue
            char_start = document_text.find(sentence)
            char_start = max(0, char_start)
            chunks.append({
                "chunk_id": f"kw_chunk_{idx}",
                "text": sentence,
                "chunk_index": idx,
                "char_start": char_start,
                "char_end": char_start + len(sentence),
                "distance": max(0.0, 1.0 - score / max(len(keywords), 1)),
                "embedding_model": "keyword",
                "embedding_version": "keyword",
                "page_estimate": 1,
                "section_label": "",
                "word_count": len(sentence.split()),
            })
        return chunks

    def _write_audit_log(
        self,
        db: Session,
        document_id: int,
        user_id: int | None,
        query_text: str,
        retrieval_method: str,
        scored_chunks: list[dict[str, Any]],
        raw_chunk_count: int,
        flags: list[str],
        answer_confidence: float,
        filters: dict[str, Any],
        answer_returned: bool,
        embedding_model: str,
        embedding_version: str,
    ) -> int | None:
        try:
            from app.modules.rag_governance.model import RetrievalAuditLog

            all_confs = [c["confidence_score"] for c in scored_chunks]
            log = RetrievalAuditLog(
                queried_at=datetime.now(timezone.utc),
                document_id=document_id,
                user_id=user_id,
                query_text=query_text[:2000],
                retrieval_method=retrieval_method,
                chunks_retrieved=raw_chunk_count,
                chunks_above_threshold=len(scored_chunks),
                top_confidence=round(all_confs[0], 4) if all_confs else None,
                mean_confidence=round(sum(all_confs) / len(all_confs), 4) if all_confs else None,
                answer_confidence=round(answer_confidence, 4),
                embedding_model=embedding_model,
                embedding_version=embedding_version,
                chunk_ids_json=json.dumps([c.get("chunk_id") for c in scored_chunks]),
                hallucination_flags_json=json.dumps(flags),
                filters_applied_json=json.dumps(filters, default=str),
                answer_returned=answer_returned,
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            return log.id
        except Exception as exc:
            logger.warning("Could not write RetrievalAuditLog: %s", exc)
            db.rollback()
            return None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_governance_engine_instance: RAGGovernanceEngine | None = None


def get_governance_engine() -> RAGGovernanceEngine:
    """Return the shared RAGGovernanceEngine singleton."""
    global _governance_engine_instance
    if _governance_engine_instance is None:
        from app.ai.rag.vector_store import get_vector_store
        from app.core.config import settings
        try:
            vs = get_vector_store()
        except Exception as exc:
            logger.warning("GovernanceEngine: VectorStore unavailable (%s) — keyword-only mode.", exc)
            vs = None
        _governance_engine_instance = RAGGovernanceEngine(
            vector_store=vs,
            min_confidence=float(settings.rag_min_confidence),
            top_k=int(settings.rag_top_k),
        )
    return _governance_engine_instance
