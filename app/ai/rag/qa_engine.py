"""
app/ai/rag/qa_engine.py
========================
 keyword-based document Q&A engine.

Replaces the Anthropic Claude API implementation with a zero-cost,
fully offline approach using keyword extraction and sentence scoring.

Academic justification:
  TF-IDF-style keyword matching (Jones, 1972) is an established NLP
  technique for information retrieval. For short domain-specific
  documents (individual insurance policies), keyword-based retrieval
  achieves high precision due to the controlled vocabulary of
  insurance language.

References:
  Jones, K.S. (1972). A statistical interpretation of term specificity
  and its application in retrieval. Journal of Documentation, 28(1).
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_STOP_WORDS: frozenset[str] = frozenset({
    "what", "is", "are", "the", "a", "an", "in", "of", "to", "for",
    "and", "or", "how", "does", "do", "this", "that", "it", "its",
    "with", "on", "at", "by", "from", "was", "be", "been", "has",
    "have", "had", "will", "would", "could", "should", "may", "might",
    "which", "who", "when", "where", "why", "about", "clause",
    "tell", "show", "find", "give", "please", "me",
})

_FALLBACK_EMPTY: dict[str, Any] = {
    "answer": "No relevant documents found in the knowledge base for this query.",
    "sources": [],
    "confidence": 0.0,
}


class QAEngine:
    """
    Offline document Q&A engine.

    Accepts vector_store and anthropic_api_key for API compatibility
    with any existing code that instantiates this class — both are
    ignored in offline mode.
    """

    def __init__(self, vector_store: Any = None, anthropic_api_key: str = "") -> None:
        self._vs = vector_store
        logger.info("QAEngine initialised in OFFLINE keyword-search mode.")

    def answer(
        self,
        document_id: str,
        question: str,
        document_title: str = "",
        document_text: str = "",
    ) -> dict[str, Any]:
        """
        Find relevant passages in document_text for the question.

        Parameters
        ----------
        document_id    : str — identifier (used only for logging)
        question       : str — the user's question
        document_title : str — display name for the document
        document_text  : str — full extracted text of the document

        Returns
        -------
        dict with keys: answer, citations, confidence, model
        """
        logger.debug("QAEngine.answer — document_id=%s question=%r", document_id, question[:80])

        try:
            if not document_text:
                logger.warning(
                    "QAEngine: empty document_text for document_id=%s — returning fallback",
                    document_id,
                )
                return {
                    "answer": (
                        "No text content is available for this document. "
                        "Ensure the document has been processed and text successfully extracted. "
                        "Scanned documents require OCR processing."
                    ),
                    "citations": [],
                    "confidence": 0.0,
                    "model": "offline-keyword-search",
                }

            keywords = self._extract_keywords(question)
            logger.debug(
                "QAEngine: extracted %d keywords from question for document_id=%s",
                len(keywords),
                document_id,
            )

            if not keywords:
                logger.warning(
                    "QAEngine: no meaningful keywords extracted for document_id=%s question=%r",
                    document_id,
                    question[:80],
                )
                return {
                    "answer": (
                        "Please ask a more specific question. Examples:\n"
                        "• 'What is the coverage limit?'\n"
                        "• 'What exclusions apply?'\n"
                        "• 'When does the policy expire?'\n"
                        "• 'Who is the insured party?'"
                    ),
                    "citations": [],
                    "confidence": 0.0,
                    "model": "offline-keyword-search",
                }

            results = self._score_sentences(document_text, keywords)
            logger.debug(
                "QAEngine: scored %d candidate sentences for document_id=%s",
                len(results),
                document_id,
            )

            if not results:
                logger.warning(
                    "QAEngine: zero documents retrieved for document_id=%s question=%r — returning fallback",
                    document_id,
                    question[:80],
                )
                return {
                    "answer": (
                        f"No relevant passages found for your question about '{question}'.\n\n"
                        "This may mean:\n"
                        "• The document does not cover this topic\n"
                        "• Text extraction quality is low (scanned document)\n"
                        "• Try rephrasing using specific terms like 'premium', "
                        "'exclusion', 'coverage', 'deductible', or 'expiry'"
                    ),
                    "citations": [],
                    "confidence": 0.0,
                    "model": "offline-keyword-search",
                }

            top = results[:3]
            answer_text = " ".join(sentence for _, sentence, _ in top)
            citations = [f"Sentence {idx + 1}" for _, _, idx in top]
            max_score = top[0][0]
            confidence = round(min(max_score / max(len(keywords), 1), 1.0), 2)

            title_part = f' from "{document_title}"' if document_title else ""
            full_answer = (
                f"Relevant passage{title_part}:\n\n{answer_text}\n\n"
                f"_(Source: {', '.join(citations)})_"
            )

            return {
                "answer": full_answer,
                "citations": citations,
                "confidence": confidence,
                "model": "offline-keyword-search",
            }

        except Exception as exc:
            logger.error(
                "QAEngine: unhandled exception for document_id=%s: %s",
                document_id,
                exc,
                exc_info=True,
            )
            raise

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract meaningful keywords from a question."""
        tokens = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        return [t for t in tokens if t not in _STOP_WORDS]

    def _score_sentences(
        self,
        text: str,
        keywords: list[str],
    ) -> list[tuple[float, str, int]]:
        """
        Score sentences by keyword overlap.
        Returns (score, sentence, original_index) sorted descending.
        """
        sentences = re.split(r'(?<=[.!?])\s+', text)
        scored: list[tuple[float, str, int]] = []

        for idx, sentence in enumerate(sentences):
            stripped = sentence.strip()
            if len(stripped) < 15:
                continue
            lower = stripped.lower()
            score = sum(1.0 for kw in keywords if kw in lower)
            if score > 0:
                score += len(stripped) / 2000.0
                scored.append((score, stripped, idx))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored
