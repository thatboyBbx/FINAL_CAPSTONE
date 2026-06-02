import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.pagination import normalize_pagination
from app.modules.compliance.model import ComplianceResult
from app.modules.documents import file_store, repo
from app.modules.documents.file_store import DuplicateFileError
from app.modules.documents.model import Document, ExtractedEntity
from app.modules.documents.schemas import DocumentCreate, DocumentUpdate

logger = logging.getLogger(__name__)


def _build_compliance_result(document_id: int, result: dict) -> ComplianceResult:
    """Construct the canonical compliance result row from a checker result dict."""
    return ComplianceResult(
        document_id=document_id,
        compliance_score=result["compliance_score"],
        clause_results=json.dumps(result["mandatory_clauses"]),
        missing_mandatory_clauses=json.dumps(result["mandatory_clauses"]["missing"]),
        prohibited_terms_found=json.dumps(result["prohibited_terms"]["violations"]),
        passes_minimum=result["compliance_score"] >= 70,
        summary=json.dumps(result["recommendations"]),
        checked_at=datetime.now(timezone.utc),
    )


def create_document(db, payload: DocumentCreate) -> Document:
    normalized_stored_filename = payload.stored_filename.strip()
    normalized_title = payload.title.strip()
    normalized_original_filename = payload.original_filename.strip()
    normalized_file_path = payload.file_path.strip()
    normalized_mime_type = payload.mime_type.strip().lower()
    normalized_status = payload.status.strip().lower()
    normalized_document_category = (
        payload.document_category.strip().lower()
        if payload.document_category
        else None
    )
    normalized_notes = payload.notes.strip() if payload.notes else None

    existing_document = repo.get_document_by_stored_filename(db, normalized_stored_filename)
    if existing_document:
        raise ValueError("A document with this stored filename already exists.")

    normalized_payload = DocumentCreate(
        title=normalized_title,
        original_filename=normalized_original_filename,
        stored_filename=normalized_stored_filename,
        file_path=normalized_file_path,
        mime_type=normalized_mime_type,
        file_size=payload.file_size,
        status=normalized_status,
        document_category=normalized_document_category,
        notes=normalized_notes,
        uploaded_by_user_id=payload.uploaded_by_user_id,
        client_id=payload.client_id,
    )

    return repo.create_document(db, normalized_payload)


async def create_document_from_upload(
    db,
    file: UploadFile,
    title: str,
    uploaded_by_user_id: int,
    document_category: str | None = None,
    notes: str | None = None,
    status: str = "uploaded",
    client_id: int | None = None,
) -> Document:
    staged = await file_store.stage_upload(file)

    # Everything after the upload stage is synchronous I/O (sha256 dedupe
    # query, file commit, DB insert).  Running it inline blocks the asyncio
    # event loop and stalls every other in-flight request during burst
    # uploads — push it to the threadpool so the event loop stays free.
    def _commit() -> Document:
        existing = repo.get_document_by_sha256(db, staged.sha256)
        if existing is not None:
            file_store.abort_staged(staged)
            raise DuplicateFileError(existing.id, staged.sha256)

        final_path = file_store.commit_staged(staged)
        stored_filename = final_path.name

        payload = DocumentCreate(
            title=title.strip(),
            original_filename=staged.original_filename,
            stored_filename=stored_filename,
            file_path=str(final_path).replace("\\", "/"),
            mime_type=staged.mime_type,
            file_size=staged.file_size,
            status=status,
            document_category=document_category,
            notes=notes,
            uploaded_by_user_id=uploaded_by_user_id,
            client_id=client_id,
            sha256_hash=staged.sha256,
        )

        try:
            return create_document(db, payload)
        except Exception:
            try:
                final_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning(
                    "create_document_from_upload: DB insert failed; could not remove file %s: %s",
                    final_path, exc,
                )
            raise

    return await run_in_threadpool(_commit)


def get_document_by_id(db, document_id: int) -> Document | None:
    return repo.get_document_by_id(db, document_id)


def get_document_file_path(db, document_id: int) -> tuple[Document, Path]:
    document = repo.get_document_by_id(db, document_id)
    if not document:
        raise ValueError("Document not found.")

    file_path = Path(document.file_path)
    if not file_path.exists():
        raise ValueError("Stored file not found on disk.")

    return document, file_path


def list_documents(
    db,
    status: str | None = None,
    document_category: str | None = None,
    uploaded_by_user_id: int | None = None,
    client_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Document]:
    normalized_status = status.strip().lower() if status else None
    normalized_document_category = document_category.strip().lower() if document_category else None

    skip, limit = normalize_pagination(skip, limit)

    if (
        normalized_status
        or normalized_document_category
        or uploaded_by_user_id is not None
        or client_id is not None
    ):
        return repo.list_documents_filtered(
            db,
            status=normalized_status,
            document_category=normalized_document_category,
            uploaded_by_user_id=uploaded_by_user_id,
            client_id=client_id,
            skip=skip,
            limit=limit,
        )

    return repo.list_documents(db, skip=skip, limit=limit)


def list_documents_by_uploader(
    db,
    uploaded_by_user_id: int,
    skip: int = 0,
    limit: int = 100,
) -> list[Document]:
    skip, limit = normalize_pagination(skip, limit)
    return repo.list_documents_by_uploader(db, uploaded_by_user_id, skip=skip, limit=limit)


def update_document(db, document_id: int, payload: DocumentUpdate) -> Document:
    document = repo.get_document_by_id(db, document_id)
    if not document:
        raise ValueError("Document not found.")

    normalized_title = payload.title.strip() if payload.title is not None else None
    normalized_status = payload.status.strip().lower() if payload.status is not None else None
    normalized_document_category = (
        payload.document_category.strip().lower()
        if payload.document_category is not None
        else None
    )
    normalized_notes = payload.notes.strip() if payload.notes is not None else None

    normalized_payload = DocumentUpdate(
        title=normalized_title,
        status=normalized_status,
        document_category=normalized_document_category,
        notes=normalized_notes,
    )

    return repo.update_document(db, document, normalized_payload)


def archive_document(db, document_id: int) -> Document:
    document = repo.get_document_by_id(db, document_id)
    if not document:
        raise ValueError("Document not found.")

    payload = DocumentUpdate(status="archived")
    return repo.update_document(db, document, payload)


def restore_document(db, document_id: int) -> Document:
    document = repo.get_document_by_id(db, document_id)
    if not document:
        raise ValueError("Document not found.")

    payload = DocumentUpdate(status="uploaded")
    return repo.update_document(db, document, payload)


def delete_document(db: Session, document_id: int) -> None:
    document = repo.get_document_by_id(db, document_id)
    if not document:
        raise ValueError("Document not found.")

    try:
        file_path = Path(document.file_path)
        if file_path.exists():
            file_path.unlink()
    except Exception as exc:
        logger.warning("delete_document: could not remove file for document %d: %s", document_id, exc)

    repo.delete_document(db, document)


# ---------------------------------------------------------------------------
# NER — entity extraction pipeline
# ---------------------------------------------------------------------------

def process_document_full(
    db: Session,
    document_id: int,
) -> dict[str, Any]:
    """
    Run the full NER extraction pipeline for a single document.

    Steps:
      1. Retrieve the Document record; raise ValueError if not found.
      2. Extract plain text from the PDF file on disk.
      3. Run the EntityExtractionService to identify and save entities.
      4. Mark the document status as "processed" on success, or
         "extraction_failed" when no text can be extracted.

    Returns a summary dict with keys:
      document_id, text_length, entities_extracted, entities_by_type,
      processing_time_ms.
    """
    # ── Lazy import keeps startup fast when spaCy is unavailable ────────────
    from app.modules.documents.entity_extraction_service import EntityExtractionService  # noqa: PLC0415
    from app.modules.documents.ingestion.pdf_extractor import extract_text_from_pdf  # noqa: PLC0415

    document = repo.get_document_by_id(db, document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found.")

    # ── Extract text ────────────────────────────────────────────────────────
    logger.info("process_document_full: extracting text from document %d", document_id)
    text = extract_text_from_pdf(document.file_path)

    if not text or len(text.strip()) < 50:
        # Mark as failed so the user knows something went wrong
        document.status = "extraction_failed"
        db.commit()
        logger.warning(
            "process_document_full: insufficient text in document %d "
            "(extracted %d chars) — marked as extraction_failed",
            document_id, len(text) if text else 0,
        )
        return {
            "document_id":        document_id,
            "error":              "Insufficient text extracted from document.",
            "entities_extracted": 0,
        }

    # ── Classify document ───────────────────────────────────────────────────
    logger.info("process_document_full: classifying document %d", document_id)
    try:
        from app.modules.documents.classifier_service import DocumentClassifierService  # noqa: PLC0415
        classifier = DocumentClassifierService()
        classification_result = classifier.classify(text)
        document.document_category = classification_result["category"]
        document.classification_confidence = classification_result["confidence"]
        document.classification_method = classification_result["method"]
        document.classified_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(
            "process_document_full: document %d classified as %s (%.2f%% confidence, method=%s)",
            document_id,
            classification_result["category"],
            classification_result["confidence"] * 100,
            classification_result["method"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "process_document_full: classification failed for document %d — %s",
            document_id, exc,
        )
        classification_result = {"category": "unknown", "confidence": 0.0, "method": "failed"}

    # ── Run NER extraction ──────────────────────────────────────────────────
    logger.info(
        "process_document_full: running NER on document %d (%d chars)",
        document_id, len(text),
    )
    extractor = EntityExtractionService()
    extraction_result = extractor.extract_entities(
        document_id=document_id,
        text=text,
        db=db,
    )

    # ── Compliance check ────────────────────────────────────────────────────
    compliance_result: dict | None = None
    try:
        from app.modules.compliance.service import get_compliance_checker  # noqa: PLC0415
        compliance_result = get_compliance_checker().check_compliance(
            document_text=text,
            document_type="all",
        )
        db.add(_build_compliance_result(document_id, compliance_result))
        logger.info(
            "process_document_full: compliance check for document %d — "
            "score=%.2f status=%s",
            document_id,
            compliance_result["compliance_score"],
            compliance_result["status"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "process_document_full: compliance check failed for document %d — %s",
            document_id, exc,
        )

    # ── Update document status ──────────────────────────────────────────────
    document.status = "processed"
    db.commit()

    logger.info(
        "process_document_full: document %d processed — "
        "%d entities extracted in %.1f ms",
        document_id,
        extraction_result["entities_found"],
        extraction_result["processing_time_ms"],
    )

    # ── RAG indexing ────────────────────────────────────────────────────────
    rag_result: dict = {"chunks_created": 0, "status": "skipped"}
    try:
        from app.ai.rag.indexing_pipeline import index_document  # noqa: PLC0415
        rag_result = index_document(document_id=document_id, db=db)
        logger.info(
            "process_document_full: RAG indexing complete — "
            "document_id=%d chunk_count=%d embedding_count=%d "
            "chroma_collection=document_chunks indexing_status=%s",
            document_id,
            rag_result["chunks_created"],
            rag_result["chunks_created"],
            rag_result["status"],
        )
    except Exception as exc:  # noqa: BLE001
        rag_result = {"chunks_created": 0, "status": "failed"}
        logger.warning(
            "process_document_full: RAG indexing failed — "
            "document_id=%d chunk_count=0 embedding_count=0 "
            "chroma_collection=document_chunks indexing_status=failed error=%s",
            document_id, exc,
        )

    return {
        "document_id":               document_id,
        "text_length":               len(text),
        "document_category":         classification_result["category"],
        "classification_confidence": classification_result["confidence"],
        "classification_method":     classification_result["method"],
        "entities_extracted":        extraction_result["entities_found"],
        "entities_by_type":          extraction_result["entities_by_type"],
        "processing_time_ms":        extraction_result["processing_time_ms"],
        "compliance_score":          compliance_result["compliance_score"] if compliance_result else None,
        "compliance_status":         compliance_result["status"] if compliance_result else None,
        "rag_chunk_count":           rag_result["chunks_created"],
        "rag_embedding_count":       rag_result["chunks_created"],
        "rag_chroma_collection":     "document_chunks",
        "rag_indexing_status":       rag_result["status"],
    }


def extract_document_text(db: Session, document_id: int) -> str:
    """
    Return the plain-text content of a document, or an empty string if
    the file cannot be read.  Used by the UI to render highlighted text.
    """
    from app.modules.documents.ingestion.pdf_extractor import extract_text_from_pdf  # noqa: PLC0415

    document = repo.get_document_by_id(db, document_id)
    if not document:
        return ""

    try:
        return extract_text_from_pdf(document.file_path)
    except Exception as exc:
        logger.error(
            "extract_document_text: failed to extract text from document %d — %s",
            document_id, exc,
        )
        return ""


def get_document_entities(
    db: Session,
    document_id: int,
    entity_type: str | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve all extracted entities for a document, optionally filtered by
    ``entity_type``.

    Returns a list of dicts serialisable to JSON.
    """
    query = (
        db.query(ExtractedEntity)
        .filter(ExtractedEntity.document_id == document_id)
    )
    if entity_type:
        query = query.filter(ExtractedEntity.entity_type == entity_type.upper())

    entities = query.order_by(ExtractedEntity.start_char).all()

    return [
        {
            "id":            e.id,
            "entity_type":   e.entity_type,
            "entity_value":  e.entity_value,
            "start_char":    e.start_char,
            "end_char":      e.end_char,
            "confidence":    e.confidence_score,
            "is_correct":    e.is_correct,
            "extracted_at":  e.extracted_at.isoformat() if e.extracted_at else None,
        }
        for e in entities
    ]


def submit_entity_feedback(
    db: Session,
    entity_id: int,
    is_correct: bool,
    feedback_by_user_id: int,
    corrected_type: str | None = None,
    corrected_value: str | None = None,
) -> dict[str, Any]:
    """
    Record a reviewer's feedback on an extracted entity.

    When ``is_correct`` is False the reviewer should supply ``corrected_type``
    and/or ``corrected_value`` so the correction can be used for active
    learning / model retraining.

    Raises ValueError if the entity does not exist.
    Returns the updated entity as a dict.
    """
    entity = db.query(ExtractedEntity).filter(ExtractedEntity.id == entity_id).first()
    if not entity:
        raise ValueError(f"Entity {entity_id} not found.")

    entity.is_correct           = is_correct
    entity.corrected_type       = corrected_type
    entity.corrected_value      = corrected_value
    entity.feedback_by_user_id  = feedback_by_user_id
    entity.feedback_at          = datetime.now(timezone.utc)

    db.commit()
    db.refresh(entity)

    logger.info(
        "submit_entity_feedback: entity %d marked is_correct=%s by user %d",
        entity_id, is_correct, feedback_by_user_id,
    )

    return {
        "id":                   entity.id,
        "entity_type":          entity.entity_type,
        "entity_value":         entity.entity_value,
        "is_correct":           entity.is_correct,
        "corrected_type":       entity.corrected_type,
        "corrected_value":      entity.corrected_value,
        "feedback_by_user_id":  entity.feedback_by_user_id,
        "feedback_at":          entity.feedback_at.isoformat() if entity.feedback_at else None,
    }
