"""
QA Router — /api/qa endpoints for document Q&A via RAG.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/qa",
    tags=["qa"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    document_id: int
    question: str


class IndexResponse(BaseModel):
    document_id: int
    chunks_created: int
    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/ask")
def ask_question(payload: AskRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Answer a natural language question against a specific document using offline keyword search.
    """
    from app.modules.documents.model import Document
    from app.modules.qa.model import QASession
    from app.ai.rag.qa_engine import QAEngine

    # Validate document exists
    doc = db.get(Document, payload.document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document id={payload.document_id} not found.",
        )

    # Fetch document text from DB
    doc_text = getattr(doc, "extracted_text", "") or getattr(doc, "raw_text", "") or ""
    doc_title = getattr(doc, "title", None) or getattr(doc, "filename", "") or f"Document #{payload.document_id}"

    # Call offline engine
    engine = QAEngine()
    result = engine.answer(
        document_id=str(payload.document_id),
        question=payload.question,
        document_title=doc_title,
        document_text=doc_text,
    )

    # Persist the Q&A session
    session_id = None
    try:
        qa = QASession(
            document_id=payload.document_id,
            question=payload.question,
            answer=result["answer"],
            citations=result.get("citations", []),
            confidence=result.get("confidence"),
            retrieved_chunks=result.get("retrieved_chunks"),
            model_used=result.get("model"),
        )
        db.add(qa)
        db.commit()
        db.refresh(qa)
        session_id = qa.id
    except Exception as exc:
        logger.error("Failed to save QA session: %s", exc)
        db.rollback()

    return {**result, "session_id": session_id}


@router.post("/index/{document_id}", response_model=IndexResponse)
def index_document_endpoint(
    document_id: int, db: Session = Depends(get_db)
) -> IndexResponse:
    """Manually trigger RAG indexing for a specific document."""
    from app.modules.documents.model import Document
    from app.ai.rag.indexing_pipeline import index_document

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document id={document_id} not found.",
        )

    try:
        result = index_document(document_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        logger.error("Indexing failed for doc %d: %s", document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Indexing failed: {exc}",
        )

    return IndexResponse(**result)


@router.get("/sessions/{document_id}")
def get_sessions(document_id: int, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Return the last 20 Q&A sessions for a document, newest first."""
    from app.modules.qa.model import QASession

    sessions = (
        db.query(QASession)
        .filter(QASession.document_id == document_id)
        .order_by(QASession.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": s.id,
            "document_id": s.document_id,
            "question": s.question,
            "answer": s.answer,
            "citations": s.citations,
            "confidence": s.confidence,
            "retrieved_chunks": s.retrieved_chunks,
            "model_used": s.model_used,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sessions
    ]
