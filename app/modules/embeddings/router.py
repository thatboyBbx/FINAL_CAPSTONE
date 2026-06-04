"""
Embeddings router — /api/embeddings/**

Endpoints for inspecting and managing document chunk embeddings:
  GET  /api/embeddings/{document_id}/status   — chunk count, model, version, embedded_at
  POST /api/embeddings/{document_id}/reindex  — enqueue an async re-embedding job
  GET  /api/embeddings/stale                  — list document IDs with outdated embeddings
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.access_control import can_access_document, require_document_access
from app.modules.auth.dependencies import get_current_user
from app.modules.users.model import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/embeddings",
    tags=["embeddings"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/stale")
def list_stale_documents(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Return document IDs whose embeddings were generated with an older model or
    version than currently configured.  Use this to drive bulk re-embedding.
    """
    from app.ai.rag.indexing_pipeline import get_stale_document_ids
    from app.core.config import settings
    from app.modules.documents.model import Document

    doc_ids = [
        doc_id for doc_id in get_stale_document_ids(db, limit=limit)
        if can_access_document(db, current_user, db.get(Document, doc_id))
    ]
    return {
        "stale_document_ids": doc_ids,
        "count": len(doc_ids),
        "current_model": settings.embedding_model_name,
        "current_version": settings.embedding_version,
    }


@router.get("/{document_id}/status")
def get_embedding_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Return the embedding state for a document: chunk count, model, version, and
    when it was last embedded.  Returns 404 if the document has never been indexed.
    """
    from app.modules.embeddings.model import DocumentChunk
    from app.modules.documents.model import Document

    require_document_access(db, current_user, document_id)

    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )

    if not chunks:
        return {
            "document_id": document_id,
            "rag_indexed": False,
            "chunk_count": 0,
            "embedding_model": None,
            "embedding_version": None,
            "embedded_at": None,
        }

    latest = max(chunks, key=lambda c: c.embedded_at)
    return {
        "document_id": document_id,
        "rag_indexed": True,
        "chunk_count": len(chunks),
        "embedding_model": latest.embedding_model,
        "embedding_version": latest.embedding_version,
        "embedded_at": latest.embedded_at.isoformat(),
    }


@router.post("/{document_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
def reindex_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Enqueue an async re-embedding job for this document.  The worker will delete
    existing ChromaDB vectors and chunk records, then re-embed with the currently
    configured model.

    Run the worker with:
        python -m app.workers.sqlite_worker --queue embedding_queue
    """
    from app.modules.documents.model import Document
    from app.queue.factory import get_job_queue
    from app.core.config import settings

    require_document_access(db, current_user, document_id)

    job_id = get_job_queue().enqueue(
        "embedding_queue",
        "embed_document",
        document_id=document_id,
        reindex=True,
        max_attempts=settings.job_max_attempts,
    )

    logger.info("Document %d queued for re-embedding — job_id=%d", document_id, job_id)

    return {
        "message": "Re-embedding queued — run the embedding_queue worker to process.",
        "document_id": document_id,
        "job_id": job_id,
        "status": "queued",
    }
