"""
Job repository — read-side queries for admin visibility endpoints.
Write operations (status transitions) belong to the queue implementation.
"""
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.modules.jobs.model import DeadLetterJob, DocumentJobStep


def get_steps_for_document(db: Session, document_id: int) -> List[Dict[str, Any]]:
    steps = (
        db.query(DocumentJobStep)
        .filter(DocumentJobStep.document_id == document_id)
        .order_by(DocumentJobStep.queued_at.desc())
        .all()
    )
    return [_step_dict(s) for s in steps]


def get_steps_for_batch(db: Session, batch_id: int) -> List[Dict[str, Any]]:
    steps = (
        db.query(DocumentJobStep)
        .filter(DocumentJobStep.batch_id == batch_id)
        .order_by(DocumentJobStep.document_id, DocumentJobStep.queued_at)
        .all()
    )
    return [_step_dict(s) for s in steps]


def list_dead_letter(
    db: Session, queue: str | None = None, redriven: bool | None = None, limit: int = 50
) -> List[Dict[str, Any]]:
    q = db.query(DeadLetterJob)
    if queue:
        q = q.filter(DeadLetterJob.queue == queue)
    if redriven is not None:
        q = q.filter(DeadLetterJob.redriven == redriven)
    items = q.order_by(DeadLetterJob.failed_at.desc()).limit(limit).all()
    return [_dead_letter_dict(d) for d in items]


def get_dead_letter(db: Session, dead_letter_id: int) -> DeadLetterJob | None:
    return db.query(DeadLetterJob).filter(DeadLetterJob.id == dead_letter_id).first()


def queue_health(db: Session) -> Dict[str, Any]:
    """
    Operator-facing health snapshot for the launch dashboard.

    For every queue:
      depth                       — number of rows in status='queued'
      oldest_queued_age_seconds   — age of the oldest queued row (None if empty)
      stuck_processing_count      — claimed/processing rows older than 2x timeout

    Also returns the count of dead-letter jobs in the last 24h.
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func
    from app.core.config import settings
    from app.modules.jobs.model import QueuedJob

    now = datetime.now(timezone.utc)
    job_timeout = getattr(settings, "job_timeout_seconds", 0) or 1800
    multiplier = getattr(settings, "stuck_job_timeout_multiplier", 2)
    stuck_cutoff = now - timedelta(seconds=multiplier * job_timeout)
    day_cutoff = now - timedelta(hours=24)

    queue_names = [
        row[0]
        for row in db.query(QueuedJob.queue).distinct().all()
    ]

    queues: Dict[str, Dict[str, Any]] = {}
    for q in queue_names:
        depth = (
            db.query(func.count(QueuedJob.id))
            .filter(QueuedJob.queue == q, QueuedJob.status == "queued")
            .scalar()
            or 0
        )
        oldest = (
            db.query(func.min(QueuedJob.scheduled_for))
            .filter(QueuedJob.queue == q, QueuedJob.status == "queued")
            .scalar()
        )
        stuck = (
            db.query(func.count(QueuedJob.id))
            .filter(
                QueuedJob.queue == q,
                QueuedJob.status.in_(["claimed", "processing"]),
                QueuedJob.claimed_at.isnot(None),
                QueuedJob.claimed_at < stuck_cutoff,
            )
            .scalar()
            or 0
        )
        queues[q] = {
            "depth": depth,
            "oldest_queued_age_seconds": (
                int((now - oldest).total_seconds()) if oldest else None
            ),
            "stuck_processing_count": stuck,
        }

    dead_letter_24h = (
        db.query(func.count(DeadLetterJob.id))
        .filter(DeadLetterJob.failed_at >= day_cutoff)
        .scalar()
        or 0
    )

    return {
        "queues": queues,
        "dead_letter_count_24h": dead_letter_24h,
        "checked_at": now.isoformat(),
    }


def queue_stats(db: Session) -> Dict[str, Any]:
    from sqlalchemy import func
    from app.modules.jobs.model import QueuedJob

    rows = (
        db.query(QueuedJob.queue, QueuedJob.status, func.count(QueuedJob.id))
        .group_by(QueuedJob.queue, QueuedJob.status)
        .all()
    )
    stats: Dict[str, Dict[str, int]] = {}
    for queue, status, count in rows:
        stats.setdefault(queue, {})[status] = count

    dead_count = db.query(func.count(DeadLetterJob.id)).scalar() or 0
    pending_redrive = (
        db.query(func.count(DeadLetterJob.id))
        .filter(DeadLetterJob.redriven == False)  # noqa: E712
        .scalar()
        or 0
    )

    return {
        "queues": stats,
        "dead_letter_total": dead_count,
        "dead_letter_pending_redrive": pending_redrive,
    }


def _step_dict(s: DocumentJobStep) -> Dict[str, Any]:
    return {
        "id": s.id,
        "document_id": s.document_id,
        "batch_id": s.batch_id,
        "queue": s.queue,
        "step_name": s.step_name,
        "status": s.status,
        "attempt": s.attempt,
        "max_attempts": s.max_attempts,
        "error_msg": s.error_msg,
        "worker_id": s.worker_id,
        "queued_at": s.queued_at.isoformat() if s.queued_at else None,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
    }


def _dead_letter_dict(d: DeadLetterJob) -> Dict[str, Any]:
    return {
        "id": d.id,
        "queue": d.queue,
        "fn_name": d.fn_name,
        "document_id": d.document_id,
        "job_payload": d.job_payload,
        "error_msg": d.error_msg,
        "error_type": d.error_type,
        "attempt_count": d.attempt_count,
        "failed_at": d.failed_at.isoformat() if d.failed_at else None,
        "redriven": d.redriven,
        "redriven_at": d.redriven_at.isoformat() if d.redriven_at else None,
    }
