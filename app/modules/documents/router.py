import json
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.pagination import normalize_pagination
from app.modules.compliance.model import ComplianceResult
from app.modules.documents import service
from app.modules.documents.file_store import DuplicateFileError, MimeValidationError
from app.modules.documents.schemas import DocumentCreate, DocumentRead, DocumentUpdate
from app.modules.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def create_document(payload: DocumentCreate, db: Session = Depends(get_db)):
    try:
        document = service.create_document(db, payload)
        return document
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    title: str = Form(...),
    uploaded_by_user_id: int = Form(...),
    document_category: str | None = Form(None),
    notes: str | None = Form(None),
    client_id: int | None = Form(None),
    status_value: str = Form("uploaded"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        document = await service.create_document_from_upload(
            db=db,
            file=file,
            title=title,
            uploaded_by_user_id=uploaded_by_user_id,
            document_category=document_category,
            notes=notes,
            status=status_value,
            client_id=client_id,
        )
        return document
    except DuplicateFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "duplicate_file",
                "message": str(exc),
                "existing_document_id": exc.existing_document_id,
            },
        )
    except MimeValidationError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("", response_model=list[DocumentRead])
def list_documents(
    status_value: str | None = Query(default=None),
    document_category: str | None = Query(default=None),
    uploaded_by_user_id: int | None = Query(default=None),
    client_id: int | None = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    skip, limit = normalize_pagination(skip, limit)
    return service.list_documents(
        db,
        status=status_value,
        document_category=document_category,
        uploaded_by_user_id=uploaded_by_user_id,
        client_id=client_id,
        skip=skip,
        limit=limit,
    )


@router.get("/uploader/{uploaded_by_user_id}", response_model=list[DocumentRead])
def list_documents_by_uploader(
    uploaded_by_user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    skip, limit = normalize_pagination(skip, limit)
    return service.list_documents_by_uploader(db, uploaded_by_user_id, skip=skip, limit=limit)


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: int, db: Session = Depends(get_db)):
    document = service.get_document_by_id(db, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return document


@router.get("/{document_id}/download")
def download_document(document_id: int, db: Session = Depends(get_db)):
    try:
        document, file_path = service.get_document_file_path(db, document_id)
        return FileResponse(
            path=file_path,
            filename=document.original_filename,
            media_type=document.mime_type,
        )
    except ValueError as exc:
        if str(exc) == "Document not found.":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/{document_id}", response_model=DocumentRead)
def update_document(document_id: int, payload: DocumentUpdate, db: Session = Depends(get_db)):
    try:
        document = service.update_document(db, document_id, payload)
        return document
    except ValueError as exc:
        if str(exc) == "Document not found.":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/{document_id}/archive", response_model=DocumentRead)
def archive_document(document_id: int, db: Session = Depends(get_db)):
    try:
        document = service.archive_document(db, document_id)
        return document
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/{document_id}/restore", response_model=DocumentRead)
def restore_document(document_id: int, db: Session = Depends(get_db)):
    try:
        document = service.restore_document(db, document_id)
        return document
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    try:
        service.delete_document(db, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# FOLDER MANAGEMENT — PATCH /{document_id}/folder
# ---------------------------------------------------------------------------

from pydantic import BaseModel as _BaseModel

class _FolderUpdate(_BaseModel):
    """Request body for the folder-move endpoint."""
    folder: str


class _ClientAssign(_BaseModel):
    """Request body for the client-assignment endpoint."""
    client_id: int | None = None


@router.patch("/{document_id}/folder")
def update_document_folder(
    document_id: int,
    payload: _FolderUpdate,
    db: Session = Depends(get_db),
) -> dict:
    """
    Move a document to a different folder.
    Creates the folder implicitly — no prior folder-creation step required.
    The ``folder`` value is stored on the Document row as a free-text string.
    """
    from app.modules.documents.model import Document as _Doc  # noqa: PLC0415
    doc = db.query(_Doc).filter(_Doc.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    folder_name = payload.folder.strip() or "Uncategorised"

    # folder column may not yet exist on older DB schemas — add it gracefully
    try:
        doc.folder = folder_name  # type: ignore[attr-defined]
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The 'folder' column is not yet present on this database. "
                   "Run the Alembic migration add_document_folder_client_id first.",
        )

    db.commit()
    db.refresh(doc)
    return {"id": document_id, "folder": folder_name, "message": "Folder updated."}


@router.patch("/{document_id}/assign-client")
def assign_document_client(
    document_id: int,
    payload: _ClientAssign,
    db: Session = Depends(get_db),
) -> dict:
    """Link (or unlink) a document to a client. Pass client_id=null to unlink."""
    from app.modules.documents.model import Document as _Doc  # noqa: PLC0415
    doc = db.query(_Doc).filter(_Doc.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    try:
        doc.client_id = payload.client_id  # type: ignore[attr-defined]
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The 'client_id' column is not yet present. Run the Alembic migration first.",
        )
    db.commit()
    db.refresh(doc)
    return {"id": document_id, "client_id": payload.client_id, "message": "Client assignment updated."}


# ---------------------------------------------------------------------------
# NER — entity extraction endpoints
# ---------------------------------------------------------------------------

@router.post("/{document_id}/process", status_code=status.HTTP_202_ACCEPTED)
def trigger_document_processing(
    document_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Enqueue a document for full pipeline processing.

    The job is written to the persistent queue (queued_jobs table) and picked
    up by the worker process.  The HTTP response returns immediately.

    Poll ``GET /documents/{document_id}`` and wait for ``status`` to become
    ``"complete"`` or ``"failed"``.  Use ``GET /api/admin/jobs/steps/{document_id}``
    for per-step granularity.

    Run the worker with:
        python -m app.workers.sqlite_worker --queue ingestion_queue
    """
    from app.queue.factory import get_job_queue
    from app.core.config import settings

    doc = service.get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    job_id = get_job_queue().enqueue(
        "ingestion_queue",
        "process_document",
        document_id=document_id,
        step_name="full_pipeline",
        max_attempts=settings.job_max_attempts,
    )

    logger.info("Document %d enqueued for processing — job_id=%d", document_id, job_id)

    return {
        "message":     "Processing queued — poll GET /documents/{id} for status.",
        "document_id": document_id,
        "job_id":      job_id,
        "status":      "queued",
    }


@router.post("/{document_id}/process/sync")
def trigger_document_processing_sync(
    document_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Synchronous variant of entity extraction — blocks until complete.

    Useful for small documents or scripted pipelines where the caller can
    wait for the result.  For production use prefer the async ``/process``
    endpoint.
    """
    try:
        result = service.process_document_full(db=db, document_id=document_id)
        return result
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {exc}",
        )


@router.get("/{document_id}/text")
def get_document_text(
    document_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return the plain-text content extracted from a document file.

    The text is used by the UI to render highlighted entity spans at the
    correct character offsets stored in the extracted_entities table.
    """
    doc = service.get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    text = service.extract_document_text(db, document_id)
    return {
        "document_id": document_id,
        "text":        text,
        "char_count":  len(text),
    }


@router.get("/{document_id}/entities")
def get_document_entities(
    document_id: int,
    entity_type: str | None = Query(default=None, description="Filter by entity type"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return all extracted entities for a document, optionally filtered by type.

    Query parameters
    ----------------
    entity_type : str, optional
        One of COVERAGE_AMOUNT, PREMIUM, DEDUCTIBLE, POLICY_PERIOD,
        POLICY_NUMBER, INSURER, INSURED, EXCLUSION.

    Response shape
    --------------
    {
        "document_id":    123,
        "total_entities": 42,
        "entities_by_type": {"COVERAGE_AMOUNT": 5, "PREMIUM": 3, ...},
        "entities": [
            {
                "id": 1, "entity_type": "COVERAGE_AMOUNT",
                "entity_value": "$1,000,000", "start_char": 245,
                "end_char": 255, "confidence": 0.92,
                "is_correct": null, "extracted_at": "..."
            },
            ...
        ]
    }
    """
    doc = service.get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    entities = service.get_document_entities(
        db, document_id=document_id, entity_type=entity_type
    )

    # Build per-type counts from the result set
    by_type: dict[str, int] = {}
    for ent in entities:
        by_type[ent["entity_type"]] = by_type.get(ent["entity_type"], 0) + 1

    return {
        "document_id":    document_id,
        "total_entities": len(entities),
        "entities_by_type": by_type,
        "entities":       entities,
    }


@router.post("/entities/{entity_id}/feedback")
def submit_entity_feedback(
    entity_id: int,
    is_correct: bool,
    feedback_by_user_id: int,
    corrected_type: str | None = None,
    corrected_value: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Submit reviewer feedback on a single extracted entity.

    This powers the active-learning loop: corrections are stored against the
    entity record and can be used to retrain the NER model via
    ``scripts/train_ner_model.py``.

    Body parameters (query params for simplicity)
    -----------------------------------------------
    is_correct           : bool — was the extraction correct?
    feedback_by_user_id  : int  — reviewer's user ID
    corrected_type       : str, optional — the right entity type
    corrected_value      : str, optional — the correct entity text
    """
    try:
        updated = service.submit_entity_feedback(
            db=db,
            entity_id=entity_id,
            is_correct=is_correct,
            feedback_by_user_id=feedback_by_user_id,
            corrected_type=corrected_type,
            corrected_value=corrected_value,
        )
        return updated
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# Compliance endpoints
# ---------------------------------------------------------------------------

@router.get("/compliance/statistics")
def get_compliance_statistics(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Aggregate compliance statistics across the latest check for every document.

    Returns
    -------
    {
        "total_documents_checked": int,
        "compliant": int,
        "non_compliant": int,
        "needs_review": int,
        "average_compliance_score": float,
        "common_violations": [{"term": str, "count": int}, ...]
    }
    """
    # Sub-query: latest checked_at per document
    latest_sq = (
        db.query(
            ComplianceResult.document_id,
            func.max(ComplianceResult.checked_at).label("max_date"),
        )
        .group_by(ComplianceResult.document_id)
        .subquery()
    )

    checks = (
        db.query(ComplianceResult)
        .join(
            latest_sq,
            (ComplianceResult.document_id == latest_sq.c.document_id)
            & (ComplianceResult.checked_at == latest_sq.c.max_date),
        )
        .all()
    )

    if not checks:
        return {
            "total_documents_checked": 0,
            "compliant": 0,
            "non_compliant": 0,
            "needs_review": 0,
            "average_compliance_score": 0.0,
            "common_violations": [],
        }

    status_counts: dict[str, int] = {"compliant": 0, "non_compliant": 0, "needs_review": 0}
    scores: list[float] = []
    all_violation_terms: list[str] = []

    for check in checks:
        status_counts[check.status] = status_counts.get(check.status, 0) + 1
        scores.append(check.compliance_score)
        if check.prohibited_terms_found:
            try:
                violations = json.loads(check.prohibited_terms_found)
                all_violation_terms.extend(v["term"] for v in violations)
            except (json.JSONDecodeError, KeyError):
                pass

    common_violations = [
        {"term": term, "count": count}
        for term, count in Counter(all_violation_terms).most_common(10)
    ]

    return {
        "total_documents_checked": len(checks),
        "compliant": status_counts.get("compliant", 0),
        "non_compliant": status_counts.get("non_compliant", 0),
        "needs_review": status_counts.get("needs_review", 0),
        "average_compliance_score": round(sum(scores) / len(scores), 2),
        "common_violations": common_violations,
    }


@router.get("/{document_id}/compliance")
def get_document_compliance(
    document_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return the most recent compliance check result for a document.

    Raises 404 if no compliance check has been run yet.
    """
    compliance = (
        db.query(ComplianceResult)
        .filter(ComplianceResult.document_id == document_id)
        .order_by(ComplianceResult.checked_at.desc())
        .first()
    )

    if not compliance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No compliance check found. Process the document first.",
        )

    clause_results = json.loads(compliance.clause_results) if compliance.clause_results else {}
    violations = (
        json.loads(compliance.prohibited_terms_found)
        if compliance.prohibited_terms_found
        else []
    )
    recommendations = json.loads(compliance.summary) if compliance.summary else []

    return {
        "compliance_score": compliance.compliance_score,
        "status": compliance.status,
        "mandatory_clauses": {
            "total_required": clause_results.get("total_required", 0),
            "found": clause_results.get("found", 0),
            "missing": json.loads(compliance.missing_mandatory_clauses)
            if compliance.missing_mandatory_clauses
            else [],
            "present": clause_results.get("present", []),
        },
        "prohibited_terms": {
            "found": len(violations),
            "violations": violations,
        },
        "recommendations": recommendations,
        "checked_at": compliance.checked_at.isoformat(),
    }


@router.post("/{document_id}/sandbox-eligibility")
def check_document_sandbox_eligibility(
    document_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Run the 6-criterion IPEC Sandbox Eligibility Pre-Check against a document.

    Fetches the document's text from disk and passes it to
    check_sandbox_eligibility(), which applies the Annexure 1 keyword rules.

    Returns a structured result with per-criterion pass/fail, overall status
    (ELIGIBLE / LIKELY_ELIGIBLE / NOT_ELIGIBLE), and a plain-English summary.

    Dissertation Methodology Note (Chapter 3):
    This endpoint exposes the rule-based Annexure 1 checker as a REST API so
    that the InsureIntel UI can surface eligibility assessments without
    requiring the broker to re-upload the document.

    References:
        IPEC (2025). Regulatory Sandbox Guidelines for the Insurance and
        Pensions Industry. Insurance and Pensions Commission of Zimbabwe.
        Effective Q4 2025. Retrieved from ipec.co.zw.
    """
    from app.modules.compliance.service import check_sandbox_eligibility  # noqa: PLC0415
    from app.modules.documents.ingestion.pdf_extractor import extract_text_from_pdf  # noqa: PLC0415

    # Verify the document exists using the established pattern in this router
    doc = service.get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Extract plain text from the document file on disk
    try:
        text = extract_text_from_pdf(doc.file_path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not extract text from document: {exc}",
        )

    # Run eligibility check and return structured result
    result = check_sandbox_eligibility(text)
    result["document_id"] = document_id
    return result


@router.post("/{document_id}/compliance/recheck")
def recheck_document_compliance(
    document_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Re-run compliance check on a document (e.g. after manual edits).

    Returns the same shape as GET /{document_id}/compliance.
    """
    from app.modules.compliance.service import get_compliance_checker  # noqa: PLC0415
    from app.modules.documents.ingestion.pdf_extractor import extract_text_from_pdf  # noqa: PLC0415

    doc = service.get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    text = extract_text_from_pdf(doc.file_path)
    if not text or len(text.strip()) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot re-check compliance — text extraction failed.",
        )

    result = get_compliance_checker().check_compliance(document_text=text, document_type="all")
    db.add(service._build_compliance_result(document_id, result))
    db.commit()

    return result


# ---------------------------------------------------------------------------
# Classification endpoints
# ---------------------------------------------------------------------------

@router.get("/statistics/categories")
def get_category_statistics(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Return document category distribution statistics.

    Response:
        {
            "total_documents": int,
            "classified": int,
            "unclassified": int,
            "by_category": {"policy_wording": int, ...},
            "average_confidence": float,
        }
    """
    from app.modules.documents.model import Document  # noqa: PLC0415

    try:
        total = db.query(func.count(Document.id)).scalar() or 0
        classified = (
            db.query(func.count(Document.id))
            .filter(Document.document_category.isnot(None))
            .scalar()
        ) or 0
        unclassified = total - classified

        category_counts = (
            db.query(Document.document_category, func.count(Document.id))
            .group_by(Document.document_category)
            .all()
        )
        by_category = {(cat or "unknown"): cnt for cat, cnt in category_counts}

        avg_confidence = (
            db.query(func.avg(Document.classification_confidence))
            .filter(
                Document.classification_confidence.isnot(None),
                Document.document_category != "unknown",
            )
            .scalar()
        )

        return {
            "total_documents": total,
            "classified": classified,
            "unclassified": unclassified,
            "by_category": by_category,
            "average_confidence": round(float(avg_confidence or 0.0), 4),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "Statistics Error",
                "error_msg": str(exc),
                "user_action": "Refresh the page. If the problem persists, check server logs.",
            },
        )


@router.get("/{document_id}/classification")
def get_document_classification(
    document_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return the current classification details for a document.

    Raises 404 if the document has not been classified yet.
    """
    from app.modules.documents.model import Document  # noqa: PLC0415

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if not doc.document_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not yet classified. Run document processing first.",
        )

    return {
        "document_id": document_id,
        "category": doc.document_category,
        "confidence": doc.classification_confidence,
        "method": doc.classification_method,
        "classified_at": doc.classified_at.isoformat() if doc.classified_at else None,
    }


@router.post("/{document_id}/reclassify")
def reclassify_document(
    document_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Re-run classification on a document using the current ML model.

    Useful after training data improvements or model updates.
    """
    from app.modules.documents.model import Document  # noqa: PLC0415
    from app.modules.documents.classifier_service import DocumentClassifierService  # noqa: PLC0415
    from app.modules.documents.ingestion.pdf_extractor import extract_text_from_pdf  # noqa: PLC0415

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    try:
        text = extract_text_from_pdf(doc.file_path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_type": "Text Extraction Failed",
                "error_msg": str(exc),
                "user_action": "Ensure the document file exists and is a valid PDF.",
            },
        )

    if not text or len(text.strip()) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_type": "Insufficient Text",
                "error_msg": "Cannot classify — text extraction returned fewer than 50 characters.",
                "user_action": "Check the document is not a scanned image without OCR enabled.",
            },
        )

    try:
        classifier = DocumentClassifierService()
        result = classifier.classify(text)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "Classification Error",
                "error_msg": str(exc),
                "user_action": "Ensure the classifier model is trained. Run: python scripts/train_document_classifier.py",
            },
        )

    doc.document_category = result["category"]
    doc.classification_confidence = result["confidence"]
    doc.classification_method = result["method"]
    doc.classified_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "document_id": document_id,
        "category": result["category"],
        "confidence": result["confidence"],
        "method": result["method"],
        "probabilities": result["probabilities"],
        "classified_at": doc.classified_at.isoformat(),
    }
