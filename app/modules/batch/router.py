"""
Batch/Portfolio Router — /api/batch and /api/portfolio endpoints.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.batch.batch_processor import BatchProcessor
from app.core.db import get_db
from app.modules.auth.access_control import can_access_document, is_admin
from app.modules.auth.dependencies import get_current_user
from app.modules.documents.file_store import sanitize_filename
from app.modules.users.model import User

logger = logging.getLogger(__name__)
router = APIRouter(
    tags=["batch"],
    dependencies=[Depends(get_current_user)],
)

_processor = BatchProcessor()


class BatchStartRequest(BaseModel):
    name: str
    analysis_type: str | None = None
    portfolio: str | None = None


# ---------------------------------------------------------------------------
# Batch endpoints
# ---------------------------------------------------------------------------

@router.post("/api/batch/upload")
async def batch_upload(
    portfolio_id: str = Form(...),
    uploaded_by: str = Form(default="unknown"),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Accept multiple file uploads, create batch + document records,
    and enqueue persistent background processing for each file.

    Jobs are written to queued_jobs and survive server restarts.
    Run: python -m app.workers.sqlite_worker --queue ingestion_queue
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded.",
        )

    # Stage files to persistent storage before any processing begins
    saved_paths = []
    upload_dir = Path("storage") / "uploads" / portfolio_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    for upload in files:
        safe_name = sanitize_filename(upload.filename or "document")
        dest = upload_dir / safe_name
        try:
            content = await upload.read()
            dest.write_bytes(content)
            saved_paths.append(str(dest))
        except Exception as exc:
            logger.error("Failed to stage upload %s: %s", upload.filename, exc)

    if not saved_paths:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="All file saves failed.",
        )

    # Create batch + document DB records
    batch_info = _processor.create_batch(
        db,
        saved_paths,
        portfolio_id,
        current_user.staff_id or uploaded_by,
        current_user.id,
    )

    # Enqueue each document into the persistent job queue
    from app.queue.factory import get_job_queue
    from app.core.config import settings
    job_queue = get_job_queue()
    job_ids: list[int] = []
    for doc_id in batch_info["document_ids"]:
        jid = job_queue.enqueue(
            "ingestion_queue",
            "process_document",
            document_id=doc_id,
            step_name="full_pipeline",
            batch_id=batch_info["batch_id"],
            max_attempts=settings.job_max_attempts,
        )
        job_ids.append(jid)

    logger.info(
        "Batch %d: enqueued %d jobs for portfolio=%s",
        batch_info["batch_id"], len(job_ids), portfolio_id,
    )

    return {**batch_info, "job_ids": job_ids}


@router.post("/api/batch/start")
def batch_start(
    payload: BatchStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create an empty batch record for the current UI's start action."""
    from app.modules.batch.model import ProcessingBatch

    if not payload.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Batch name is required.")

    batch = ProcessingBatch(
        portfolio_id=(payload.portfolio or payload.name).strip(),
        uploaded_by=current_user.staff_id,
        total_documents=0,
        status="queued",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return {
        "id": batch.id,
        "batch_id": batch.id,
        "name": payload.name,
        "analysis_type": payload.analysis_type,
        "portfolio_id": batch.portfolio_id,
        "status": batch.status,
    }


@router.get("/api/batch/{batch_id}/status")
def get_batch_status(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return progress for a batch."""
    try:
        from app.modules.documents.model import Document
        from app.modules.batch.model import ProcessingBatch

        batch = db.get(ProcessingBatch, batch_id)
        if batch and not is_admin(current_user) and batch.uploaded_by != current_user.staff_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Batch access denied.")
        docs = db.query(Document).filter(Document.batch_id == batch_id).all()
        if docs and not is_admin(current_user) and not all(can_access_document(db, current_user, doc) for doc in docs):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Batch access denied.")
        return _processor.get_batch_status(db, batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# Portfolio endpoints removed — app/portfolio/ is out of scope for thesis demo.
