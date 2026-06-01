"""
SQLite-backed job queue — no Redis required.

Suitable for development, thesis demo, and low-concurrency deployments.

Enqueue: INSERT into queued_jobs + INSERT into document_job_steps (if document_id given).
Claim:   Atomic UPDATE with status='queued' guard to prevent double-claim.
Retry:   Reschedules job with exponential backoff (base * 2^attempt seconds).
DLQ:     Inserts into dead_letter_jobs after max_attempts is reached.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import update

from app.core.db import session_scope
from app.modules.jobs.model import DeadLetterJob, DocumentJobStep, QueuedJob
from app.queue.protocol import JobQueue, JobStatus

logger = logging.getLogger(__name__)


@dataclass
class JobSnapshot:
    """Detached view of a QueuedJob — safe to pass across session boundaries."""

    id: int
    queue: str
    fn_name: str
    payload: dict
    attempt: int
    max_attempts: int
    document_id: int | None = None
    step_name: str | None = None
    batch_id: int | None = None


class SQLiteJobQueue(JobQueue):
    """
    Persistent job queue backed by the application SQLite (or PostgreSQL) database.

    Thread-safety: Each method opens its own session_scope() transaction.
    Claim atomicity: Uses a WHERE status='queued' guard on the UPDATE so that
    two concurrent workers racing to claim the same job will produce at most
    one winner (the other gets rowcount=0 and backs off).
    """

    def __init__(
        self,
        retry_base_seconds: int = 60,
        retry_max_seconds: int = 1800,
    ) -> None:
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds

    # ── Public API ────────────────────────────────────────────────────────────

    def enqueue(
        self,
        queue: str,
        fn_name: str,
        *,
        document_id: int | None = None,
        step_name: str | None = None,
        batch_id: int | None = None,
        max_attempts: int = 3,
        **kwargs: Any,
    ) -> int:
        now = datetime.now(timezone.utc)
        with session_scope() as db:
            job = QueuedJob(
                queue=queue,
                fn_name=fn_name,
                payload=json.dumps(kwargs),
                status=JobStatus.QUEUED,
                attempt=0,
                max_attempts=max_attempts,
                document_id=document_id,
                step_name=step_name,
                scheduled_for=now,
            )
            db.add(job)
            db.flush()  # get job.id before committing

            if document_id is not None and step_name:
                step = DocumentJobStep(
                    document_id=document_id,
                    batch_id=batch_id,
                    queue=queue,
                    step_name=step_name,
                    status=JobStatus.QUEUED,
                    max_attempts=max_attempts,
                    queued_at=now,
                    queued_job_id=job.id,
                )
                db.add(step)

            job_id = job.id

        logger.debug("[queue] enqueued job_id=%d queue=%s fn=%s doc=%s", job_id, queue, fn_name, document_id)
        return job_id

    def job_status(self, job_id: int) -> str:
        with session_scope() as db:
            job = db.query(QueuedJob).filter(QueuedJob.id == job_id).first()
            return job.status if job else "not_found"

    # ── Worker-facing operations ──────────────────────────────────────────────

    def claim_next(self, queue: str, worker_id: str) -> JobSnapshot | None:
        """
        Atomically claim the next available job for the given queue.
        Returns None if no job is available or the claim lost a race.
        """
        now = datetime.now(timezone.utc)
        with session_scope() as db:
            # Find the oldest eligible job (not yet claimed)
            candidate = (
                db.query(QueuedJob.id)
                .filter(
                    QueuedJob.queue == queue,
                    QueuedJob.status == JobStatus.QUEUED,
                    QueuedJob.scheduled_for <= now,
                )
                .order_by(QueuedJob.scheduled_for)
                .first()
            )
            if not candidate:
                return None

            # Atomic claim: only succeeds if status is still 'queued'
            result = db.execute(
                update(QueuedJob)
                .where(QueuedJob.id == candidate[0], QueuedJob.status == JobStatus.QUEUED)
                .values(status=JobStatus.CLAIMED, claimed_at=now, worker_id=worker_id)
            )

            if result.rowcount == 0:
                return None  # another worker claimed it first

            job = db.query(QueuedJob).filter(QueuedJob.id == candidate[0]).one()
            snapshot = JobSnapshot(
                id=job.id,
                queue=job.queue,
                fn_name=job.fn_name,
                payload=json.loads(job.payload),
                attempt=job.attempt,
                max_attempts=job.max_attempts,
                document_id=job.document_id,
                step_name=job.step_name,
            )

        return snapshot

    def mark_processing(self, job_id: int, worker_id: str) -> None:
        now = datetime.now(timezone.utc)
        with session_scope() as db:
            db.execute(
                update(QueuedJob)
                .where(QueuedJob.id == job_id)
                .values(status=JobStatus.PROCESSING, worker_id=worker_id)
            )
            self._update_step(db, job_id, status=JobStatus.PROCESSING, started_at=now, worker_id=worker_id)

    def mark_complete(self, job_id: int) -> None:
        now = datetime.now(timezone.utc)
        with session_scope() as db:
            db.execute(
                update(QueuedJob)
                .where(QueuedJob.id == job_id)
                .values(status=JobStatus.COMPLETE, completed_at=now)
            )
            self._update_step(db, job_id, status=JobStatus.COMPLETE, completed_at=now)

    def mark_failed(
        self,
        job_id: int,
        error_msg: str,
        error_type: str,
        *,
        permanent: bool = False,
    ) -> None:
        """
        Increment the attempt counter.  If max_attempts reached (or permanent=True),
        move to dead-letter.  Otherwise reschedule with exponential backoff.
        """
        with session_scope() as db:
            job = db.query(QueuedJob).filter(QueuedJob.id == job_id).one_or_none()
            if not job:
                logger.warning("[queue] mark_failed: job_id=%d not found", job_id)
                return

            new_attempt = job.attempt + 1
            truncated_error = error_msg[:2000]

            if permanent or new_attempt >= job.max_attempts:
                self._move_to_dead_letter(db, job, truncated_error, error_type, new_attempt)
                self._update_step(
                    db, job_id, status=JobStatus.DEAD_LETTER,
                    completed_at=datetime.now(timezone.utc),
                    error_msg=truncated_error,
                )
                logger.warning(
                    "[queue] dead-letter job_id=%d queue=%s fn=%s attempt=%d/%d error=%s",
                    job_id, job.queue, job.fn_name, new_attempt, job.max_attempts,
                    error_type,
                )
            else:
                delay = min(
                    self.retry_base_seconds * (2 ** (new_attempt - 1)),
                    self.retry_max_seconds,
                )
                retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                db.execute(
                    update(QueuedJob)
                    .where(QueuedJob.id == job_id)
                    .values(
                        status=JobStatus.QUEUED,
                        attempt=new_attempt,
                        scheduled_for=retry_at,
                        error_msg=truncated_error,
                        worker_id=None,
                        claimed_at=None,
                    )
                )
                self._update_step(
                    db, job_id, status=JobStatus.QUEUED,
                    attempt=new_attempt,
                    error_msg=truncated_error,
                )
                logger.info(
                    "[queue] retry scheduled job_id=%d attempt=%d/%d delay=%ds",
                    job_id, new_attempt, job.max_attempts, delay,
                )

    def reclaim_stuck_jobs(self, stale_after_seconds: int) -> int:
        """
        Reset jobs whose worker died mid-flight back to ``queued``.

        Any row in ``claimed`` or ``processing`` whose ``claimed_at`` is older
        than ``stale_after_seconds`` is assumed abandoned by a dead worker.
        Its attempt counter is incremented (so it is subject to the normal
        max_attempts ceiling) and it is rescheduled for immediate pickup.

        Returns the number of rows reclaimed.
        """
        if stale_after_seconds <= 0:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
        reclaimed = 0
        with session_scope() as db:
            stuck = (
                db.query(QueuedJob)
                .filter(
                    QueuedJob.status.in_([JobStatus.CLAIMED, JobStatus.PROCESSING]),
                    QueuedJob.claimed_at.isnot(None),
                    QueuedJob.claimed_at < cutoff,
                )
                .all()
            )
            now = datetime.now(timezone.utc)
            for job in stuck:
                new_attempt = job.attempt + 1
                if new_attempt >= job.max_attempts:
                    # Treat as final failure — dead-letter so it doesn't loop
                    self._move_to_dead_letter(
                        db, job, "worker timeout / abandoned", "StuckJob", new_attempt
                    )
                    self._update_step(
                        db, job.id, status=JobStatus.DEAD_LETTER,
                        completed_at=now, error_msg="worker timeout / abandoned",
                    )
                else:
                    db.execute(
                        update(QueuedJob)
                        .where(QueuedJob.id == job.id)
                        .values(
                            status=JobStatus.QUEUED,
                            attempt=new_attempt,
                            scheduled_for=now,
                            worker_id=None,
                            claimed_at=None,
                            error_msg="reclaimed: previous worker did not finish",
                        )
                    )
                    self._update_step(
                        db, job.id, status=JobStatus.QUEUED,
                        attempt=new_attempt,
                        error_msg="reclaimed: previous worker did not finish",
                    )
                reclaimed += 1
        if reclaimed:
            logger.warning("[queue] reclaimed %d stuck job(s) (stale_after=%ds)",
                           reclaimed, stale_after_seconds)
        return reclaimed

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _move_to_dead_letter(
        self, db: Any, job: QueuedJob, error_msg: str, error_type: str, attempt: int
    ) -> None:
        dl = DeadLetterJob(
            queue=job.queue,
            fn_name=job.fn_name,
            document_id=job.document_id,
            job_payload=job.payload,
            error_msg=error_msg,
            error_type=error_type,
            attempt_count=attempt,
        )
        db.add(dl)
        db.execute(
            update(QueuedJob)
            .where(QueuedJob.id == job.id)
            .values(status=JobStatus.DEAD_LETTER, attempt=attempt, error_msg=error_msg)
        )

    def _update_step(
        self,
        db: Any,
        job_id: int,
        *,
        status: str,
        attempt: int | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        worker_id: str | None = None,
        error_msg: str | None = None,
    ) -> None:
        """Update the DocumentJobStep row that references this job, if one exists."""
        step = (
            db.query(DocumentJobStep)
            .filter(DocumentJobStep.queued_job_id == job_id)
            .first()
        )
        if not step:
            return
        step.status = status
        if attempt is not None:
            step.attempt = attempt
        if started_at is not None:
            step.started_at = started_at
        if completed_at is not None:
            step.completed_at = completed_at
        if worker_id is not None:
            step.worker_id = worker_id
        if error_msg is not None:
            step.error_msg = error_msg[:2000]
