"""
BaseWorker — shared logic for all worker process types.

Provides:
  - Job execution with retry/dead-letter handling
  - Memory RSS guard (optional, requires psutil)
  - Structured logging per job lifecycle event
  - session_scope() awareness (workers do not share the API's session pool)

Concrete workers inherit from BaseWorker and implement a run() method that
calls poll_and_execute() in a loop.
"""
from __future__ import annotations

import logging
import os
import socket
import threading
from typing import Any, Callable, Dict

from app.queue.protocol import PermanentJobError
from app.queue.sqlite_queue import JobSnapshot, SQLiteJobQueue

logger = logging.getLogger(__name__)


class BaseWorker:
    """
    Execute queued jobs with retry, dead-letter handling, and optional memory
    guarding.

    Args:
        queue:        Queue name this worker consumes (e.g. "ingestion_queue").
        registry:     Mapping of fn_name → callable.  The callable receives the
                      job payload as keyword arguments.
        queue_impl:   The JobQueue implementation (default: SQLiteJobQueue).
        max_rss_mb:   Optional RSS limit in MB.  0 = disabled.  If exceeded,
                      the worker logs a warning and sets _should_stop so the
                      outer loop can restart the process cleanly.
    """

    def __init__(
        self,
        queue: str,
        registry: Dict[str, Callable],
        queue_impl: SQLiteJobQueue | None = None,
        max_rss_mb: int = 0,
        job_timeout_seconds: int = 0,
    ) -> None:
        self.queue = queue
        self.registry = registry
        self.max_rss_mb = max_rss_mb
        self.job_timeout_seconds = job_timeout_seconds
        self._should_stop = False

        if queue_impl is None:
            from app.queue.sqlite_queue import SQLiteJobQueue as _SQ
            from app.core.config import settings
            retry_base = getattr(settings, "job_retry_backoff_base_seconds", 60)
            queue_impl = _SQ(retry_base_seconds=retry_base)
        self._queue = queue_impl

        # Unique worker identity for DB records and log lines
        self.worker_id = f"{socket.gethostname()}-{os.getpid()}-{queue}"

    # ── Main execution unit ───────────────────────────────────────────────────

    def poll_and_execute(self) -> bool:
        """
        Claim and execute one job.

        Returns True if a job was processed (caller can poll again immediately),
        False if the queue was empty (caller should sleep before next poll).
        """
        if self._check_memory_limit():
            return False

        job = self._queue.claim_next(self.queue, self.worker_id)
        if job is None:
            return False

        self._execute(job)
        return True

    # ── Job lifecycle ─────────────────────────────────────────────────────────

    def _execute(self, job: JobSnapshot) -> None:
        fn = self.registry.get(job.fn_name)
        if fn is None:
            logger.error(
                "[%s] unknown fn_name=%r for job_id=%d — sending to dead-letter",
                self.worker_id, job.fn_name, job.id,
            )
            self._queue.mark_failed(
                job.id,
                f"No handler registered for fn_name={job.fn_name!r}",
                "UnregisteredFunction",
                permanent=True,
            )
            return

        self._queue.mark_processing(job.id, self.worker_id)
        log_prefix = f"[{self.worker_id}] job_id={job.id} fn={job.fn_name}"

        logger.info("%s attempt=%d/%d — starting", log_prefix, job.attempt + 1, job.max_attempts)

        try:
            if self.job_timeout_seconds > 0:
                self._run_with_timeout(fn, job.payload, self.job_timeout_seconds)
            else:
                fn(**job.payload)
            self._queue.mark_complete(job.id)
            logger.info("%s — complete", log_prefix)

        except PermanentJobError as exc:
            logger.warning("%s — permanent failure: %s", log_prefix, exc)
            self._queue.mark_failed(
                job.id, str(exc), type(exc).__name__, permanent=True
            )

        except Exception as exc:
            logger.error(
                "%s attempt=%d/%d — transient failure: %s",
                log_prefix, job.attempt + 1, job.max_attempts, exc,
                exc_info=True,
            )
            self._queue.mark_failed(job.id, str(exc), type(exc).__name__)

    # ── Timeout enforcement ───────────────────────────────────────────────────

    def _run_with_timeout(self, fn: Callable, payload: dict, timeout_seconds: int) -> None:
        """
        Run fn(**payload) in a daemon thread.  Raises TimeoutError if it does not
        complete within timeout_seconds.  Raises the original exception if fn fails.

        The daemon thread may continue running after a timeout — pdfplumber/spaCy
        work cannot be force-killed.  The memory guard will catch runaway resource
        usage on the next poll cycle.
        """
        exc_holder: list[BaseException | None] = [None]
        done_event = threading.Event()

        def _target() -> None:
            try:
                fn(**payload)
            except BaseException as exc:  # noqa: BLE001
                exc_holder[0] = exc
            finally:
                done_event.set()

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        finished = done_event.wait(timeout=timeout_seconds)

        if not finished:
            raise TimeoutError(
                f"Job exceeded {timeout_seconds}s timeout — the worker thread will "
                "continue in the background until it completes or the process restarts."
            )
        if exc_holder[0] is not None:
            raise exc_holder[0]  # re-raise original; preserves PermanentJobError type

    # ── Memory guard ─────────────────────────────────────────────────────────

    def _check_memory_limit(self) -> bool:
        """
        Returns True if memory limit is exceeded (caller should stop polling).
        Logs a warning and sets _should_stop so the polling loop can exit cleanly.
        """
        if not self.max_rss_mb:
            return False
        try:
            import psutil
            rss_mb = psutil.Process().memory_info().rss / (1024 * 1024)
            if rss_mb > self.max_rss_mb:
                logger.warning(
                    "[%s] RSS %.0f MB exceeds limit %d MB — stopping after current job",
                    self.worker_id, rss_mb, self.max_rss_mb,
                )
                self._should_stop = True
                return True
        except ImportError:
            pass
        return False
