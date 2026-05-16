"""
Batch/Portfolio Router — /api/batch and /api/portfolio endpoints.
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.batch.batch_processor import BatchProcessor
from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user

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
    background_tasks: BackgroundTasks,
    portfolio_id: str = Form(...),
    uploaded_by: str = Form(default="unknown"),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Accept multiple file uploads, create batch + document records,
    and enqueue background processing for each file.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded.",
        )

    # Save files to a temp directory so we have persistent paths
    saved_paths = []
    upload_dir = os.path.join("storage", "uploads", portfolio_id)
    os.makedirs(upload_dir, exist_ok=True)

    for upload in files:
        dest = os.path.join(upload_dir, upload.filename or "document")
        try:
            content = await upload.read()
            with open(dest, "wb") as f:
                f.write(content)
            saved_paths.append(dest)
        except Exception as exc:
            logger.error("Failed to save upload %s: %s", upload.filename, exc)

    if not saved_paths:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="All file saves failed.",
        )

    # Create batch record
    batch_info = _processor.create_batch(db, saved_paths, portfolio_id, uploaded_by)

    # Enqueue processing for each document
    from app.batch.tasks import process_single_document
    for doc_id in batch_info["document_ids"]:
        background_tasks.add_task(process_single_document, doc_id)

    return batch_info


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
