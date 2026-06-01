"""
app/modules/rag_governance/schemas.py
========================================
Pydantic schemas for the RAG governance API endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GovernedQueryRequest(BaseModel):
    document_id: int
    question: str = Field(..., min_length=3, max_length=1000)
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, ge=1, le=20)
    require_embedding_version: str | None = None


class CitationOut(BaseModel):
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


class GovernedQueryResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    confidence: float
    hallucination_flags: list[str]
    retrieval_stats: dict[str, Any]
    embedding_model: str
    embedding_version: str
    audit_log_id: int | None
    answer_returned: bool


class AuditLogEntry(BaseModel):
    id: int
    queried_at: datetime
    document_id: int | None
    user_id: int | None
    query_text: str
    retrieval_method: str
    chunks_retrieved: int
    chunks_above_threshold: int
    top_confidence: float | None
    mean_confidence: float | None
    answer_confidence: float | None
    embedding_model: str | None
    embedding_version: str | None
    chunk_ids_json: str | None
    hallucination_flags_json: str | None
    filters_applied_json: str | None
    answer_returned: bool

    model_config = {"from_attributes": True}


class StaleReindexResponse(BaseModel):
    queued: int
    document_ids: list[int]
    current_model: str
    current_version: str


class RAGConfigResponse(BaseModel):
    embedding_model: str
    embedding_version: str
    min_confidence_default: float
    top_k_default: int
