"""
BatchProcessor — creates batch records and queues document processing tasks.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.modules.documents.file_store import guess_mime_from_filename

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Manages batch uploads and processing status tracking."""

    def create_batch(
        self,
        db: Session,
        file_paths: List[str],
        portfolio_id: str,
        uploaded_by: str,
    ) -> Dict[str, Any]:
        """
        Create Document and ProcessingBatch rows for a list of uploaded files.
        Returns batch metadata; actual processing is triggered by the caller
        using FastAPI BackgroundTasks.
        """
        from app.modules.batch.model import ProcessingBatch
        from app.modules.documents.model import Document

        # Create the batch row
        batch = ProcessingBatch(
            portfolio_id=portfolio_id,
            uploaded_by=uploaded_by,
            total_documents=len(file_paths),
            status="queued",
        )
        db.add(batch)
        try:
            db.commit()
            db.refresh(batch)
        except Exception as exc:
            logger.error("Failed to create ProcessingBatch: %s", exc)
            db.rollback()
            raise

        doc_ids = []
        for fp in file_paths:
            fname = os.path.basename(fp)
            try:
                doc = Document(
                    title=fname,
                    original_filename=fname,
                    stored_filename=fname,
                    file_path=fp,
                    mime_type=guess_mime_from_filename(fname),
                    file_size=_safe_size(fp),
                    status="queued",
                    uploaded_by_user_id=0,  # set to 0 for batch uploads (no user context)
                    portfolio_id=portfolio_id,
                    batch_id=batch.id,
                )
                db.add(doc)
                db.commit()
                db.refresh(doc)
                doc_ids.append(doc.id)
            except Exception as exc:
                logger.error("Failed to create Document for %s: %s", fp, exc)
                db.rollback()

        return {
            "batch_id": batch.id,
            "document_count": len(doc_ids),
            "document_ids": doc_ids,
            "status": "queued",
            "portfolio_id": portfolio_id,
        }

    def get_batch_status(
        self, db: Session, batch_id: int
    ) -> Dict[str, Any]:
        """Return current processing status for a batch."""
        from app.modules.batch.model import ProcessingBatch
        from app.modules.documents.model import Document

        batch = db.query(ProcessingBatch).filter(ProcessingBatch.id == batch_id).first()
        if not batch:
            raise ValueError(f"Batch id={batch_id} not found.")

        # Count document statuses
        docs = (
            db.query(Document)
            .filter(Document.batch_id == batch_id)
            .all()
        )
        status_counts: Dict[str, int] = {}
        for d in docs:
            status_counts[d.status] = status_counts.get(d.status, 0) + 1

        total = batch.total_documents or 1
        complete = status_counts.get("complete", 0)
        failed   = status_counts.get("failed", 0)

        return {
            "batch_id": batch.id,
            "portfolio_id": batch.portfolio_id,
            "total": batch.total_documents,
            "queued": status_counts.get("queued", 0),
            "processing": status_counts.get("processing", 0),
            "complete": complete,
            "failed": failed,
            "progress_pct": round((complete + failed) / total * 100, 1),
            "status": batch.status,
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
            "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
        }


def _safe_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except Exception:
        return 0


