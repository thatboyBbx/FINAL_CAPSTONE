"""
Batch/Portfolio Router — /api/batch and /api/portfolio endpoints.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.batch.batch_processor import BatchProcessor
from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.documents.file_store import sanitize_filename

logger = logging.getLogger(__name__)
router = APIRouter(
    tags=["batch"],
    dependencies=[Depends(get_current_user)],
)

_processor = BatchProcessor()


# ---------------------------------------------------------------------------
# Batch endpoints
# ---------------------------------------------------------------------------

@router.post("/api/batch/upload")
async def batch_upload(
    portfolio_id: str = Form(...),
    uploaded_by: str = Form(default="unknown"),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
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
    batch_info = _processor.create_batch(db, saved_paths, portfolio_id, uploaded_by)

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


@router.get("/api/batch/{batch_id}/status")
def get_batch_status(
    batch_id: int, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Return progress for a batch."""
    try:
        return _processor.get_batch_status(db, batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# Portfolio endpoints removed — app/portfolio/ is out of scope for thesis demo.
