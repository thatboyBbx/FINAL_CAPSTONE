"""
app/ai/nlp/text_utils.py
=========================
Shared NLP text utilities used by QAEngine and the chatbot router.

Previously duplicated in:
  - app/ai/rag/qa_engine.py
  - app/modules/chatbot/router.py
"""
from __future__ import annotations

import re

STOP_WORDS: frozenset[str] = frozenset({
    "what", "is", "are", "the", "a", "an", "in", "of", "to", "for",
    "and", "or", "how", "does", "do", "this", "that", "it", "its",
    "with", "on", "at", "by", "from", "was", "be", "been", "has",
    "have", "had", "will", "would", "could", "should", "may", "might",
    "which", "who", "when", "where", "why", "about", "clause", "me",
    "tell", "explain", "show", "find", "give", "please",
})


def extract_keywords(text: str) -> list[str]:
    """Return meaningful tokens from *text*, excluding stop words."""
    tokens = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    return [t for t in tokens if t not in STOP_WORDS]


def score_sentences(
    text: str,
    keywords: list[str],
    min_length: int = 15,
) -> list[tuple[float, str, int]]:
    """
    Score sentences in *text* by keyword overlap.

    Returns a list of (score, sentence, original_index) sorted descending.
    The length bonus (len/2000) slightly favours more informative sentences.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    scored: list[tuple[float, str, int]] = []

    for idx, sentence in enumerate(sentences):
        stripped = sentence.strip()
        if len(stripped) < min_length:
            continue
        lower = stripped.lower()
        score = sum(1.0 for kw in keywords if kw in lower)
        if score > 0:
            score += len(stripped) / 2000.0
            scored.append((score, stripped, idx))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def search_text(text: str, question: str, max_sentences: int = 3) -> str | None:
    """
    Return the top *max_sentences* most relevant sentences from *text* for
    *question*, or ``None`` if no relevant sentences are found.
    """
    if not text or not question:
        return None
    keywords = extract_keywords(question)
    if not keywords:
        return None
    results = score_sentences(text, keywords)
    if not results:
        return None
    return " ".join(sentence for _, sentence, _ in results[:max_sentences])
