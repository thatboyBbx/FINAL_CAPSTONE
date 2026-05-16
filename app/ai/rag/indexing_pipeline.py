"""
RAG Indexing Pipeline — chunks and embeds document text into ChromaDB.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.ai.rag.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)


def index_document(
    document_id: int,
    db: Session,
    vector_store: VectorStore | None = None,
) -> Dict[str, Any]:
    vs = vector_store or get_vector_store()

    from app.modules.documents.model import Document
    from app.modules.circulars.model import CircularAnalysis

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document id={document_id} not found.")

    full_text = _get_document_text(document_id, doc, db)

    if not full_text or not full_text.strip():
        raise ValueError(
            f"No text available for document id={document_id}. "
            "Run analysis first or check the file path."
        )

    str_doc_id = str(document_id)
    chunks = vs.chunk_document(str_doc_id, full_text, chunk_size=400, overlap=80)
    count = vs.embed_and_store(chunks)

    try:
        doc.rag_indexed = True  # type: ignore[attr-defined]
        doc.rag_indexed_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]
        doc.chunk_count = count  # type: ignore[attr-defined]
        db.commit()
    except Exception as exc:
        logger.warning("Could not update rag_indexed on Document %d: %s", document_id, exc)
        db.rollback()

    logger.info("Indexed document %d — %d chunks stored.", document_id, count)
    return {"document_id": document_id, "chunks_created": count, "status": "indexed"}


def _get_document_text(document_id: int, doc: Any, db: Session) -> str:
    try:
        from app.modules.circulars.model import CircularAnalysis
        analysis = (
            db.query(CircularAnalysis)
            .filter(CircularAnalysis.document_id == document_id)
            .first()
        )
        if analysis and analysis.extracted_text:
            return analysis.extracted_text
    except Exception as exc:
        logger.warning("Could not fetch CircularAnalysis for doc %d: %s", document_id, exc)

    try:
        from app.modules.circulars.extractor import extract_text, clean_text
        text = extract_text(doc.file_path)
        return clean_text(text)
    except Exception as exc:
        logger.warning("File extraction fallback failed for doc %d: %s", document_id, exc)
        return ""


def reindex_all_documents(
    db: Session,
    vector_store: VectorStore | None = None,
) -> Dict[str, Any]:
    from app.modules.documents.model import Document

    vs = vector_store or get_vector_store()

    try:
        pending = (
            db.query(Document)
            .filter(
                (Document.rag_indexed == False) | (Document.rag_indexed == None)  # noqa: E712
            )
            .all()
        )
    except Exception:
        return {"indexed": 0, "errors": 0, "status": "column_not_ready"}

    indexed = 0
    errors = 0
    for doc in pending:
        try:
            index_document(doc.id, db, vs)
            indexed += 1
        except Exception as exc:
            logger.warning("Failed to index document %d: %s", doc.id, exc)
            errors += 1

    logger.info("Bulk reindex complete: %d indexed, %d errors.", indexed, errors)
    return {"indexed": indexed, "errors": errors, "status": "complete"}
