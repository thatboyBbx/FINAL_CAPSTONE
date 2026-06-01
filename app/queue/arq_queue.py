"""
ARQ (asyncio + Redis) job queue implementation.

Optional dependency: requires `arq` and `redis` packages.
Only used when QUEUE_BACKEND=arq in settings.

Job status visibility (DocumentJobStep) is written by the worker, not here,
because ARQ workers are async and run in separate processes with their own
session management.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.queue.protocol import JobQueue

logger = logging.getLogger(__name__)


class ARQJobQueue(JobQueue):
    """
    Enqueues jobs into a Redis-backed ARQ queue.

    Workers are defined in app/workers/arq_worker.py and started via:
        arq app.workers.arq_worker.WorkerSettings

    Note: enqueue() must be called from synchronous code only.  Calling it
    from an already-running event loop will raise RuntimeError.
    """

    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url

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
        Publish a job to ARQ/Redis.

        Note: ARQ job IDs are strings (UUIDs); this method returns 0 as a placeholder
        integer (ARQ exposes the job ID only via the returned ArqJob object but we
        discard it to match the synchronous JobQueue interface).  Use DocumentJobStep
        for status tracking when using ARQ.
        """
        try:
            import arq
        except ImportError:
            raise RuntimeError(
                "ARQ queue requires 'arq' and 'redis' packages: pip install arq redis"
            )

        redis_url = self.redis_url
        payload = {
            "document_id": document_id,
            "step_name": step_name,
            "batch_id": batch_id,
            **kwargs,
        }

        async def _run() -> str | None:
            pool = await arq.create_pool(arq.connections.RedisSettings.from_dsn(redis_url))
            try:
                job = await pool.enqueue_job(fn_name, **payload, _queue_name=queue)
                return job.job_id if job else None
            finally:
                await pool.close()

        job_id = asyncio.run(_run())
        logger.debug("[arq] enqueued fn=%s queue=%s doc=%s job_id=%s", fn_name, queue, document_id, job_id)
        return 0  # ARQ job IDs are strings; caller should use DocumentJobStep for tracking

    def job_status(self, job_id: int) -> str:
        return "unknown"  # ARQ status is tracked via DocumentJobStep, not job_id
