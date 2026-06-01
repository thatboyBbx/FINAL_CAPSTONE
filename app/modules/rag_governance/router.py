"""
app/modules/rag_governance/router.py
======================================
Deterministic RAG governance API — /api/rag/**

Endpoints:
  POST /api/rag/query                      — governed semantic query with audit trail
  GET  /api/rag/audit                      — list audit log (filterable by document_id)
  GET  /api/rag/audit/{log_id}             — single audit entry
  GET  /api/rag/audit/document/{doc_id}    — all queries for a specific document
  POST /api/rag/reindex/stale              — enqueue re-embedding jobs for stale documents
  GET  /api/rag/config                     — current model / confidence config
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.rag_governance.schemas import (
    AuditLogEntry,
    GovernedQueryRequest,
    GovernedQueryResponse,
    RAGConfigResponse,
    StaleReindexResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/rag",
    tags=["rag-governance"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/query", response_model=GovernedQueryResponse)
def governed_query(
    req: GovernedQueryRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> GovernedQueryResponse:
    """
    Execute a governed RAG query against a document.

    Retrieves the top-K most relevant chunks from ChromaDB, applies confidence
    scoring, hallucination-risk detection, and returns citations alongside the
    answer.  Every call is recorded in the RetrievalAuditLog.
    """
    from app.ai.rag.governance import get_governance_engine
    from app.modules.documents.model import Document

    doc = db.query(Document).filter(Document.id == req.document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # Resolve document text for keyword fallback
    document_text = (
        getattr(doc, "extracted_text", None)
        or getattr(doc, "raw_text", None)
        or getattr(doc, "content", None)
        or ""
    )

    user_id: int | None = getattr(current_user, "id", None)

    engine = get_governance_engine()
    result = engine.governed_query(
        document_id=req.document_id,
        question=req.question,
        db=db,
        user_id=user_id,
        min_confidence=req.min_confidence,
        top_k=req.top_k,
        require_embedding_version=req.require_embedding_version,
        document_text=document_text,
    )
    return GovernedQueryResponse(**result.as_dict())


@router.get("/audit", response_model=list[AuditLogEntry])
def list_audit_log(
    document_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[AuditLogEntry]:
    """List recent audit log entries, optionally filtered by document_id."""
    from app.modules.rag_governance.model import RetrievalAuditLog

    q = db.query(RetrievalAuditLog).order_by(RetrievalAuditLog.queried_at.desc())
    if document_id is not None:
        q = q.filter(RetrievalAuditLog.document_id == document_id)
    rows = q.offset(offset).limit(limit).all()
    return [AuditLogEntry.model_validate(row) for row in rows]


@router.get("/audit/document/{doc_id}", response_model=list[AuditLogEntry])
def list_audit_for_document(
    doc_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[AuditLogEntry]:
    """Return all audit log entries for a specific document, most recent first."""
    from app.modules.rag_governance.model import RetrievalAuditLog

    rows = (
        db.query(RetrievalAuditLog)
        .filter(RetrievalAuditLog.document_id == doc_id)
        .order_by(RetrievalAuditLog.queried_at.desc())
        .limit(limit)
        .all()
    )
    return [AuditLogEntry.model_validate(row) for row in rows]


@router.get("/audit/{log_id}", response_model=AuditLogEntry)
def get_audit_entry(
    log_id: int,
    db: Session = Depends(get_db),
) -> AuditLogEntry:
    """Return a single audit log entry by ID."""
    from app.modules.rag_governance.model import RetrievalAuditLog

    row = db.query(RetrievalAuditLog).filter(RetrievalAuditLog.id == log_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit entry not found.")
    return AuditLogEntry.model_validate(row)


@router.post("/reindex/stale", response_model=StaleReindexResponse, status_code=status.HTTP_202_ACCEPTED)
def reindex_stale_documents(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> StaleReindexResponse:
    """
    Enqueue re-embedding jobs for all documents indexed with an outdated
    model or version.  Run the embedding_queue worker to process them.
    """
    from app.ai.rag.indexing_pipeline import get_stale_document_ids
    from app.core.config import settings
    from app.queue.factory import get_job_queue

    stale_ids = get_stale_document_ids(db, limit=limit)
    queued = 0
    failed_ids = []
    jq = get_job_queue()

    for doc_id in stale_ids:
        try:
            jq.enqueue(
                "embedding_queue",
                "embed_document",
                document_id=doc_id,
                reindex=True,
                max_attempts=settings.job_max_attempts,
            )
            queued += 1
        except Exception as exc:
            logger.warning("Could not enqueue reindex for doc %d: %s", doc_id, exc)
            failed_ids.append(doc_id)

    logger.info("Stale reindex: %d queued, %d failed.", queued, len(failed_ids))
    return StaleReindexResponse(
        queued=queued,
        document_ids=stale_ids,
        current_model=settings.embedding_model_name,
        current_version=settings.embedding_version,
    )


@router.get("/config", response_model=RAGConfigResponse)
def get_rag_config() -> RAGConfigResponse:
    """Return the active embedding model, version, and governance defaults."""
    from app.core.config import settings

    return RAGConfigResponse(
        embedding_model=settings.embedding_model_name,
        embedding_version=settings.embedding_version,
        min_confidence_default=float(settings.rag_min_confidence),
        top_k_default=int(settings.rag_top_k),
    )
