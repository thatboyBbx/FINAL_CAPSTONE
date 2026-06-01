"""
JobQueue protocol and sentinel exception types.

All queue implementations (SQLite, ARQ) must satisfy this interface.
"""
from __future__ import annotations

from typing import Any


class JobStatus:
    """String constants for job/step status values shared across queue and worker code."""

    QUEUED = "queued"
    CLAIMED = "claimed"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class PermanentJobError(Exception):
    """
    Raise inside a job function to skip retries and go straight to dead-letter.
    Use for errors that no amount of retrying will fix (e.g. document not found,
    corrupt file with 0 bytes).
    """


class JobQueue:
    """
    Abstract base for queue implementations.

    Concrete implementations: SQLiteJobQueue, ARQJobQueue.
    Obtain the active instance via app.queue.factory.get_job_queue().
    """

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
        """
        Publish a job.

        Args:
            queue:        Queue name (e.g. "ocr_queue", "ingestion_queue").
            fn_name:      Name of the registered function to call.
            document_id:  Optional document this job belongs to (for step tracking).
            step_name:    Optional step label for DocumentJobStep visibility.
            batch_id:     Optional batch this job belongs to.
            max_attempts: Maximum retry attempts before dead-letter (default 3).
            **kwargs:     Payload forwarded as keyword arguments to the job function.

        Returns:
            Integer job_id for status polling.
        """
        raise NotImplementedError

    def job_status(self, job_id: int) -> str:
        """Return the current status string for a job_id."""
        raise NotImplementedError
