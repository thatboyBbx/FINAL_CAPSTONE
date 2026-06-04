"""
RAG Indexing Pipeline — chunks and embeds document text into ChromaDB.

Public API:
  index_document(document_id, db)        — first-time or incremental index
  reindex_document(document_id, db)      — delete existing embeddings, then re-embed
  reindex_all_documents(db)             — bulk reindex of un-indexed documents
  get_stale_document_ids(db, limit)     — documents indexed with an older model/version
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.ai.rag.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chunk metadata enrichment helpers
# ---------------------------------------------------------------------------

_CHARS_PER_PAGE: int = 3000

_SECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'\bexclusion', re.I), 'Exclusions'),
    (re.compile(r'\bcoverage\b|covered\s+peril|sum\s+insured', re.I), 'Coverage'),
    (re.compile(r'\bpremium\b', re.I), 'Premium'),
    (re.compile(r'\bclaim(s)?\b', re.I), 'Claims'),
    (re.compile(r'\bsettle(ment)?\b|\bpayment\b', re.I), 'Settlement'),
    (re.compile(r'\bdefinition(s)?\b', re.I), 'Definitions'),
    (re.compile(r'\bschedule\b', re.I), 'Schedule'),
    (re.compile(r'\bcondition(s)?\b', re.I), 'Conditions'),
    (re.compile(r'\bindemnity\b', re.I), 'Indemnity'),
    (re.compile(r'\bnotice\b|\breach\b', re.I), 'Notice'),
    (re.compile(r'\breinsurance\b|\breinsur', re.I), 'Reinsurance'),
    (re.compile(r'\bliabilit', re.I), 'Liability'),
]


def _detect_section_label(text: str) -> str:
    for pattern, label in _SECTION_PATTERNS:
        if pattern.search(text):
            return label
    return ''


def _estimate_page(char_start: int) -> int:
    return max(1, char_start // _CHARS_PER_PAGE + 1)


def _enrich_chunk_metadata(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach page_estimate, section_label, and word_count to each chunk dict."""
    for chunk in chunks:
        text = chunk.get("text", "")
        chunk["page_estimate"] = _estimate_page(chunk.get("char_start", 0))
        chunk["section_label"] = _detect_section_label(text)
        chunk["word_count"] = len(text.split())
    return chunks


def index_document(
    document_id: int,
    db: Session,
    vector_store: VectorStore | None = None,
) -> Dict[str, Any]:
    """
    Chunk, embed, and store a document's text.  Persists DocumentChunk records in
    the relational DB for version tracking and lifecycle management.
    Idempotent: calling twice replaces the previous chunk records and upserts
    ChromaDB entries.
    """
    from app.core.config import settings

    vs = vector_store or get_vector_store()

    from app.modules.documents.model import Document

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
    chunks = vs.chunk_document(
        str_doc_id,
        full_text,
        chunk_size=settings.rag_chunk_size,
        overlap=settings.rag_chunk_overlap,
    )
    chunks = _enrich_chunk_metadata(chunks)
    indexing_status = "indexed"
    try:
        count = vs.embed_and_store(
            chunks,
            batch_size=settings.embedding_batch_size,
            embedding_model=settings.embedding_model_name,
            embedding_version=settings.embedding_version,
        )
    except Exception as exc:
        logger.warning(
            "Embedding/vector indexing failed for document %d; persisting text chunks "
            "for offline keyword RAG instead: %s",
            document_id,
            exc,
        )
        count = len(chunks)
        indexing_status = "chunked"

    _persist_chunk_records(document_id, chunks, db, settings)

    try:
        doc.rag_indexed = True  # type: ignore[attr-defined]
        doc.rag_indexed_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]
        doc.chunk_count = count  # type: ignore[attr-defined]
        db.commit()
    except Exception as exc:
        logger.warning("Could not update rag_indexed on Document %d: %s", document_id, exc)
        db.rollback()

    logger.info("Indexed document %d — %d chunks stored.", document_id, count)
    return {"document_id": document_id, "chunks_created": count, "status": indexing_status}


def reindex_document(
    document_id: int,
    db: Session,
    vector_store: VectorStore | None = None,
) -> Dict[str, Any]:
    """
    Delete all existing embeddings for document_id, then re-embed from scratch.
    Used after an embedding model upgrade or when text extraction is updated.
    """
    vs = vector_store or get_vector_store()

    # Remove stale vectors from ChromaDB
    vs.delete_document(str(document_id))

    # Remove stale chunk records from the relational DB
    _delete_chunk_records(document_id, db)

    logger.info("Cleared existing embeddings for document %d — re-indexing.", document_id)
    return index_document(document_id, db, vs)


def get_stale_document_ids(db: Session, limit: int = 100) -> List[int]:
    """
    Return document IDs whose chunks were embedded with an older model or version
    than the one currently configured.  Used to drive bulk re-embedding workflows.
    """
    from app.core.config import settings
    from app.modules.embeddings.model import DocumentChunk

    rows = (
        db.query(DocumentChunk.document_id)
        .filter(
            (DocumentChunk.embedding_model != settings.embedding_model_name)
            | (DocumentChunk.embedding_version != settings.embedding_version)
        )
        .distinct()
        .limit(limit)
        .all()
    )
    return [row[0] for row in rows]


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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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
        from app.modules.circulars.extractor import clean_text
        from app.modules.documents import file_store
        from app.modules.documents.ingestion.pdf_extractor import extract_text_from_pdf

        file_path = file_store.resolve_existing_document_path(
            doc.file_path,
            stored_filename=getattr(doc, "stored_filename", None),
            original_filename=getattr(doc, "original_filename", None),
            file_size=getattr(doc, "file_size", None),
        )
        if str(file_path).replace("\\", "/") != doc.file_path and file_path.exists():
            doc.file_path = str(file_path).replace("\\", "/")
            db.commit()

        text = extract_text_from_pdf(file_path)
        return clean_text(text)
    except Exception as exc:
        logger.warning("File extraction fallback failed for doc %d: %s", document_id, exc)
        return ""


def _persist_chunk_records(document_id: int, chunks: list, db: Session, settings: Any) -> None:
    """
    Replace all DocumentChunk rows for this document with the freshly-embedded set.
    Deletes first so that chunk_id uniqueness is never violated on re-index.
    """
    from app.modules.embeddings.model import DocumentChunk

    # Clear previous records for this document
    _delete_chunk_records(document_id, db)

    now = datetime.now(timezone.utc)
    for chunk in chunks:
        text = chunk["text"]
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        db.add(DocumentChunk(
            document_id=document_id,
            chunk_id=chunk["chunk_id"],
            chunk_index=chunk["chunk_index"],
            char_start=chunk["char_start"],
            char_end=chunk["char_end"],
            text_hash=text_hash,
            embedding_model=settings.embedding_model_name,
            embedding_version=settings.embedding_version,
            embedded_at=now,
            chunk_text=text,
            page_estimate=chunk.get("page_estimate", 1),
            section_label=chunk.get("section_label", ""),
            word_count=chunk.get("word_count", 0),
        ))
    try:
        db.commit()
    except Exception as exc:
        logger.warning("Failed to persist chunk records for document %d: %s", document_id, exc)
        db.rollback()


def _delete_chunk_records(document_id: int, db: Session) -> None:
    from app.modules.embeddings.model import DocumentChunk
    try:
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        db.commit()
    except Exception as exc:
        logger.warning("Failed to delete chunk records for document %d: %s", document_id, exc)
        db.rollback()
