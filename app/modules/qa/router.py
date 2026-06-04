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

    # Fetch document text — three-tier lookup in descending preference:
    #   1. CircularAnalysis.extracted_text (batch-processed documents)
    #   2. DocumentChunk.chunk_text concatenated in order (available after RC-2 sync indexing)
    #   3. Direct PDF extraction from disk (fallback for un-indexed documents)
    doc_text = ""
    text_source = "none"

    try:
        from app.modules.circulars.model import CircularAnalysis  # noqa: PLC0415
        analysis = (
            db.query(CircularAnalysis)
            .filter(CircularAnalysis.document_id == payload.document_id)
            .first()
        )
        if analysis and analysis.extracted_text:
            doc_text = analysis.extracted_text
            text_source = "circular_analysis"
    except Exception as exc:  # noqa: BLE001
        logger.warning("QA: CircularAnalysis lookup failed for doc %d: %s", payload.document_id, exc)

    if not doc_text:
        try:
            from app.modules.embeddings.model import DocumentChunk  # noqa: PLC0415
            chunks = (
                db.query(DocumentChunk)
                .filter(
                    DocumentChunk.document_id == payload.document_id,
                    DocumentChunk.chunk_text.isnot(None),
                )
                .order_by(DocumentChunk.chunk_index)
                .all()
            )
            if chunks:
                doc_text = " ".join(c.chunk_text for c in chunks if c.chunk_text)
                text_source = f"document_chunks({len(chunks)})"
        except Exception as exc:  # noqa: BLE001
            logger.warning("QA: DocumentChunk lookup failed for doc %d: %s", payload.document_id, exc)

    if not doc_text:
        try:
            from app.modules.documents import file_store  # noqa: PLC0415
            from app.modules.documents.ingestion.pdf_extractor import extract_text_from_pdf  # noqa: PLC0415
            if doc.file_path:
                file_path = file_store.resolve_existing_document_path(
                    doc.file_path,
                    stored_filename=getattr(doc, "stored_filename", None),
                    original_filename=getattr(doc, "original_filename", None),
                    file_size=getattr(doc, "file_size", None),
                )
                if str(file_path).replace("\\", "/") != doc.file_path and file_path.exists():
                    doc.file_path = str(file_path).replace("\\", "/")
                    db.commit()
                doc_text = extract_text_from_pdf(file_path) or ""
                if doc_text:
                    text_source = "pdf_extraction"
        except Exception as exc:  # noqa: BLE001
            logger.warning("QA: PDF extraction fallback failed for doc %d: %s", payload.document_id, exc)

    logger.info(
        "QA: doc_id=%d text_source=%s text_length=%d question=%r",
        payload.document_id, text_source, len(doc_text), payload.question[:80],
    )

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

    return {
        **result,
        "session_id": session_id,
        "text_source": text_source,
        "text_length": len(doc_text),
    }


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
