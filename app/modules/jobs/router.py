"""
Jobs admin router — /api/admin/jobs/**

Endpoints for monitoring queue state, viewing per-document step progress,
and re-driving dead-letter jobs.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.audit.audit_logger import AuditLogger, get_audit_logger
from app.modules.auth.dependencies import get_current_user, require_role
from app.modules.jobs import repo
from app.modules.users.model import User

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/admin/jobs",
    tags=["jobs-admin"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/stats")
def get_queue_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Return per-queue status counts and dead-letter summary."""
    return repo.queue_stats(db)


@router.get("/health")
def get_queue_health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Operator launch-dashboard signal: per-queue depth, oldest queued age,
    stuck-processing count, and dead-letter volume over the last 24h.
    """
    return repo.queue_health(db)


@router.get("/steps/{document_id}")
def get_document_steps(
    document_id: int, db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Return all job step records for a specific document."""
    return repo.get_steps_for_document(db, document_id)


@router.get("/batch/{batch_id}/steps")
def get_batch_steps(
    batch_id: int, db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Return all job step records for every document in a batch."""
    return repo.get_steps_for_batch(db, batch_id)


@router.get("/dead-letter")
def list_dead_letter(
    queue: str | None = None,
    redriven: bool | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List dead-lettered jobs, optionally filtered by queue or redrive status."""
    return repo.list_dead_letter(db, queue=queue, redriven=redriven, limit=min(limit, 200))


@router.post("/dead-letter/{dead_letter_id}/redrive")
def redrive_dead_letter(
    request: Request,
    dead_letter_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
) -> Dict[str, Any]:
    """
    Re-enqueue a dead-lettered job from the beginning (resets attempt counter).
    The original dead-letter row is kept for audit; redriven=True is set on it.
    """
    from datetime import datetime, timezone

    from app.queue import get_job_queue

    dl = repo.get_dead_letter(db, dead_letter_id)
    if not dl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dead-letter job id={dead_letter_id} not found.",
        )
    if dl.redriven:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dead-letter job id={dead_letter_id} has already been redriven.",
        )

    import json

    payload = json.loads(dl.job_payload)
    jq = get_job_queue()
    new_job_id = jq.enqueue(
        dl.queue,
        dl.fn_name,
        document_id=dl.document_id,
        **payload,
    )

    dl.redriven = True
    dl.redriven_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(
        "Dead-letter job %d redriven → new job_id=%s (queue=%s fn=%s)",
        dead_letter_id, new_job_id, dl.queue, dl.fn_name,
    )
    get_audit_logger().log(
        db,
        event_type=AuditLogger.ADMIN_ACTION,
        actor=admin.staff_id,
        ip_address=request.client.host if request.client else None,
        details={
            "action": "redrive_dead_letter",
            "dead_letter_id": dead_letter_id,
            "new_job_id": new_job_id,
            "queue": dl.queue,
            "fn_name": dl.fn_name,
        },
    )
    return {"redriven": True, "new_job_id": new_job_id, "dead_letter_id": dead_letter_id}
