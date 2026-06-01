"""
Queue factory — returns the active JobQueue implementation based on settings.

Usage:
    from app.queue import get_job_queue
    jq = get_job_queue()
    job_id = jq.enqueue("ingestion_queue", "process_document", document_id=42)

The instance is cached at module level (process-singleton).
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.queue.protocol import JobQueue

logger = logging.getLogger(__name__)

_instance: JobQueue | None = None


def get_job_queue() -> JobQueue:
    global _instance
    if _instance is not None:
        return _instance

    backend = getattr(settings, "queue_backend", "sqlite").lower()

    if backend == "arq":
        from app.queue.arq_queue import ARQJobQueue

        redis_url = getattr(settings, "redis_url", "redis://localhost:6379/0")
        _instance = ARQJobQueue(redis_url=redis_url)
        logger.info("[queue] using ARQ backend (redis_url=%s)", redis_url)

    else:
        from app.queue.sqlite_queue import SQLiteJobQueue

        retry_base = getattr(settings, "job_retry_backoff_base_seconds", 60)
        _instance = SQLiteJobQueue(retry_base_seconds=retry_base)
        if backend != "sqlite":
            logger.warning(
                "[queue] unknown QUEUE_BACKEND=%r — falling back to sqlite", backend
            )
        else:
            logger.info("[queue] using SQLite backend")

    return _instance
