"""
app/ai/rag/citation_tracker.py
================================
Structured citation records that bind each RAG answer passage to its source chunk.

Each CitationRecord carries byte-exact provenance (char_start/char_end), human-readable
location hints (page_estimate, section_label), and a confidence_score so downstream
consumers can apply their own quality thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_MAX_EXCERPT_CHARS = 200


@dataclass(frozen=True)
class CitationRecord:
    chunk_id: str
    document_id: int
    chunk_index: int
    char_start: int
    char_end: int
    page_estimate: int
    section_label: str
    confidence_score: float
    text_excerpt: str
    embedding_model: str
    embedding_version: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "page_estimate": self.page_estimate,
            "section_label": self.section_label,
            "confidence_score": self.confidence_score,
            "text_excerpt": self.text_excerpt,
            "embedding_model": self.embedding_model,
            "embedding_version": self.embedding_version,
        }


def build_citations(
    chunks: list[dict[str, Any]],
    document_id: int,
) -> list[CitationRecord]:
    """Build CitationRecord list from scored VectorStore query-result chunks."""
    records: list[CitationRecord] = []
    for chunk in chunks:
        text = chunk.get("text", "")
        excerpt = text[:_MAX_EXCERPT_CHARS].rstrip()
        if len(text) > _MAX_EXCERPT_CHARS:
            excerpt += "..."
        records.append(CitationRecord(
            chunk_id=chunk.get("chunk_id", ""),
            document_id=document_id,
            chunk_index=chunk.get("chunk_index", 0),
            char_start=chunk.get("char_start", 0),
            char_end=chunk.get("char_end", 0),
            page_estimate=chunk.get("page_estimate", 1),
            section_label=chunk.get("section_label", ""),
            confidence_score=chunk.get("confidence_score", 0.0),
            text_excerpt=excerpt,
            embedding_model=chunk.get("embedding_model", ""),
            embedding_version=chunk.get("embedding_version", ""),
        ))
    return records


def inline_citation_footer(citations: list[CitationRecord]) -> str:
    """Format a concise citation footer for appending to a governed RAG answer."""
    if not citations:
        return ""
    lines: list[str] = []
    for i, c in enumerate(citations, 1):
        parts = [f"Chunk {c.chunk_index + 1}"]
        if c.section_label:
            parts.append(f"[{c.section_label}]")
        if c.page_estimate:
            parts.append(f"p.{c.page_estimate}")
        parts.append(f"conf = {c.confidence_score:.0%}")
        lines.append(f"[{i}] " + " ".join(parts))
    return "\n".join(lines)
