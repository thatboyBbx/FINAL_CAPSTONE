"""
SQLite worker process — polls the queued_jobs table and executes registered jobs.

Run as a standalone process:

    python -m app.workers.sqlite_worker --queue ingestion_queue
    python -m app.workers.sqlite_worker --queue ocr_queue --poll-interval 2 --max-rss-mb 800
    python -m app.workers.sqlite_worker --queue embedding_queue --max-rss-mb 0

The worker will run until:
  - SIGINT / SIGTERM is received (graceful: finishes the current job then exits)
  - Memory limit is exceeded (sets _should_stop, exits after current job)
  - --max-jobs N is given (exits after processing N jobs — useful for tests)

Each queue has a registry of fn_name → callable defined at the bottom of this file.
Add entries there when new job types are introduced.
"""
from __future__ import annotations

import argparse
import gc
import logging
import signal
import sys
import threading
import time

logger = logging.getLogger(__name__)


# ── Job function registry ─────────────────────────────────────────────────────
#
# Maps fn_name (stored in queued_jobs.fn_name) to the callable that executes it.
# The callable receives the job payload as keyword arguments.
#
# Populated lazily: imports happen inside the lambda so that model-loading
# libraries are only pulled in for the queues that actually need them.
# ─────────────────────────────────────────────────────────────────────────────

def _check_document_size(document_id: int) -> None:
    """
    Refuse the job if the document exceeds MAX_DOCUMENT_SIZE_MB, or if its
    size cannot be confirmed.

    Failing closed (rather than warning and continuing) is the production-safe
    default: an unknown-size file could be arbitrarily large and would happily
    consume all available RAM in pdfplumber / Tesseract before failing.
    """
    from app.queue.protocol import PermanentJobError
    from app.core.config import settings
    from app.core.db import SessionLocal
    from app.modules.documents.model import Document

    max_mb = getattr(settings, "max_document_size_mb", 0)
    if not max_mb:
        return

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
    finally:
        db.close()

    if not doc:
        raise PermanentJobError(
            f"Document {document_id} not found — cannot run size check."
        )
    if not doc.file_size or doc.file_size <= 0:
        raise PermanentJobError(
            f"Document {document_id} has no recorded file_size — refusing to "
            "process unknown-size payload."
        )
    if doc.file_size > max_mb * 1024 * 1024:
        size_mb = doc.file_size // (1024 * 1024)
        raise PermanentJobError(
            f"Document {document_id} is {size_mb}MB — exceeds limit of {max_mb}MB. "
            "Split the document or raise MAX_DOCUMENT_SIZE_MB."
        )


def _process_document(**kwargs):
    from app.batch.tasks import process_single_document
    from app.queue.protocol import PermanentJobError
    document_id = kwargs.get("document_id")
    if document_id is None:
        raise PermanentJobError("process_document requires document_id in payload")
    _check_document_size(document_id)
    return process_single_document(document_id)


def _embed_document(**kwargs):
    """
    Standalone embedding job — chunks and embeds a single document.
    Used for re-embedding workflows (model upgrade, forced reindex) and for
    embedding documents that were ingested without going through the full pipeline.

    Payload keys:
      document_id (int, required)
      reindex     (bool, default True)  — if True, delete existing embeddings first
    """
    from app.queue.protocol import PermanentJobError
    from app.core.db import SessionLocal

    document_id = kwargs.get("document_id")
    if document_id is None:
        raise PermanentJobError("embed_document requires document_id in payload")

    reindex = kwargs.get("reindex", True)

    from app.ai.rag.indexing_pipeline import index_document, reindex_document
    db = SessionLocal()
    try:
        if reindex:
            reindex_document(document_id, db)
        else:
            index_document(document_id, db)
    except ValueError as exc:
        # Missing document or missing text — permanent failure, no point retrying
        raise PermanentJobError(str(exc)) from exc
    finally:
        db.close()


# Registry per queue name
QUEUE_REGISTRIES: dict[str, dict[str, callable]] = {
    "document_queue": {
        "process_document": _process_document,
    },
    "ingestion_queue": {
        "process_document": _process_document,
    },
    "embedding_queue": {
        "embed_document": _embed_document,
    },
}


# ── Worker loop ───────────────────────────────────────────────────────────────

def run_worker(
    queue: str,
    poll_interval: float = 3.0,
    max_rss_mb: int = 0,
    max_jobs: int = 0,
    job_timeout_seconds: int = 0,
) -> None:
    """
    Main worker loop.  Blocks until stopped.

    Args:
        queue:               Queue name to consume.
        poll_interval:       Seconds to sleep when the queue is empty.
        max_rss_mb:          RSS memory limit in MB.  0 = disabled.
        max_jobs:            Exit after processing this many jobs.  0 = run forever.
        job_timeout_seconds: Per-job wall-clock timeout in seconds.  0 = disabled.
    """
    from app.workers.base_worker import BaseWorker
    from app.queue.sqlite_queue import SQLiteJobQueue
    from app.core.config import settings

    registry = QUEUE_REGISTRIES.get(queue)
    if registry is None:
        logger.error("[worker] No registry defined for queue=%r — known queues: %s", queue, list(QUEUE_REGISTRIES))
        sys.exit(1)

    retry_base = getattr(settings, "job_retry_backoff_base_seconds", 60)
    retry_max = getattr(settings, "job_retry_backoff_max_seconds", 1800)
    timeout = job_timeout_seconds or getattr(settings, "job_timeout_seconds", 0)
    queue_impl = SQLiteJobQueue(
        retry_base_seconds=retry_base,
        retry_max_seconds=retry_max,
    )

    # Stuck-job reclaim configuration (recovery for dead-worker scenarios)
    reclaim_interval = getattr(settings, "stuck_job_reclaim_interval_seconds", 60)
    reclaim_multiplier = getattr(settings, "stuck_job_timeout_multiplier", 2)
    # If no per-job timeout is configured, fall back to 30 min so stuck rows
    # do not pile up forever waiting on a never-set ceiling.
    effective_timeout = timeout or 1800
    stale_after = max(reclaim_multiplier * effective_timeout, 120)
    last_reclaim = time.monotonic()
    worker = BaseWorker(
        queue=queue,
        registry=registry,
        queue_impl=queue_impl,
        max_rss_mb=max_rss_mb,
        job_timeout_seconds=timeout,
    )

    # ── Signal handling ───────────────────────────────────────────────────────
    _stop = {"flag": False}

    def _handle_signal(signum, frame):
        logger.info("[%s] received signal %d — will stop after current job", worker.worker_id, signum)
        _stop["flag"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # ── Main poll loop ────────────────────────────────────────────────────────
    jobs_processed = 0
    logger.info(
        "[%s] started — queue=%s poll_interval=%.1fs max_rss_mb=%d max_jobs=%d timeout=%ds",
        worker.worker_id, queue, poll_interval, max_rss_mb, max_jobs, timeout,
    )

    while not _stop["flag"] and not worker._should_stop:
        # Periodic stuck-job janitor — reclaims rows abandoned by dead workers
        if reclaim_interval and (time.monotonic() - last_reclaim) >= reclaim_interval:
            try:
                queue_impl.reclaim_stuck_jobs(stale_after_seconds=stale_after)
            except Exception:
                logger.exception("[%s] stuck-job reclaim failed", worker.worker_id)
            last_reclaim = time.monotonic()

        did_work = worker.poll_and_execute()

        if did_work:
            jobs_processed += 1
            gc.collect()  # help pdfplumber/spaCy release large object graphs
            if max_jobs and jobs_processed >= max_jobs:
                logger.info("[%s] reached max_jobs=%d — exiting", worker.worker_id, max_jobs)
                break
        else:
            time.sleep(poll_interval)

    logger.info("[%s] stopped (jobs_processed=%d)", worker.worker_id, jobs_processed)


# ── In-process thread variant ─────────────────────────────────────────────────

def run_worker_thread(
    queue: str,
    stop_event: threading.Event,
    poll_interval: float = 3.0,
    max_rss_mb: int = 0,
    job_timeout_seconds: int = 0,
) -> None:
    """
    Thread-safe worker loop.  Identical to run_worker() but uses a
    threading.Event for stop signalling instead of OS signal handlers
    (signal.signal() is only permitted on the main thread).

    Intended for use from app/main.py:lifespan() to start an in-process
    ingestion worker alongside the FastAPI server.

    Args:
        queue:               Queue name to consume.
        stop_event:          Set this event to request a graceful stop.
        poll_interval:       Seconds to wait when the queue is empty.
        max_rss_mb:          RSS memory limit in MB.  0 = disabled.
        job_timeout_seconds: Per-job wall-clock timeout in seconds.  0 = disabled.
    """
    from app.workers.base_worker import BaseWorker
    from app.queue.sqlite_queue import SQLiteJobQueue
    from app.core.config import settings

    registry = QUEUE_REGISTRIES.get(queue)
    if registry is None:
        logger.error("[thread-worker] No registry for queue=%r — known: %s", queue, list(QUEUE_REGISTRIES))
        return

    retry_base = getattr(settings, "job_retry_backoff_base_seconds", 60)
    retry_max = getattr(settings, "job_retry_backoff_max_seconds", 1800)
    timeout = job_timeout_seconds or getattr(settings, "job_timeout_seconds", 0)
    queue_impl = SQLiteJobQueue(
        retry_base_seconds=retry_base,
        retry_max_seconds=retry_max,
    )

    reclaim_interval = getattr(settings, "stuck_job_reclaim_interval_seconds", 60)
    reclaim_multiplier = getattr(settings, "stuck_job_timeout_multiplier", 2)
    effective_timeout = timeout or 1800
    stale_after = max(reclaim_multiplier * effective_timeout, 120)
    last_reclaim = time.monotonic()

    worker = BaseWorker(
        queue=queue,
        registry=registry,
        queue_impl=queue_impl,
        max_rss_mb=max_rss_mb,
        job_timeout_seconds=timeout,
    )

    jobs_processed = 0
    logger.info(
        "[thread-worker] started — queue=%s poll_interval=%.1fs max_rss_mb=%d timeout=%ds",
        queue, poll_interval, max_rss_mb, timeout,
    )

    while not stop_event.is_set() and not worker._should_stop:
        if reclaim_interval and (time.monotonic() - last_reclaim) >= reclaim_interval:
            try:
                queue_impl.reclaim_stuck_jobs(stale_after_seconds=stale_after)
            except Exception:
                logger.exception("[thread-worker] stuck-job reclaim failed")
            last_reclaim = time.monotonic()

        did_work = worker.poll_and_execute()
        if did_work:
            jobs_processed += 1
            gc.collect()
        else:
            # Interruptible sleep — stop_event.wait() wakes immediately when set
            stop_event.wait(timeout=poll_interval)

    logger.info("[thread-worker] stopped — queue=%s jobs_processed=%d", queue, jobs_processed)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="InsureIntel SQLite queue worker")
    parser.add_argument("--queue", required=True, help="Queue name to consume")
    parser.add_argument("--poll-interval", type=float, default=3.0, metavar="SECONDS",
                        help="Sleep time (s) when queue is empty (default 3)")
    parser.add_argument("--max-rss-mb", type=int, default=0, metavar="MB",
                        help="RSS memory limit in MB; 0 = disabled (default 0)")
    parser.add_argument("--max-jobs", type=int, default=0, metavar="N",
                        help="Exit after N jobs; 0 = run forever (default 0)")
    parser.add_argument("--timeout", type=int, default=0, metavar="SECONDS",
                        help="Per-job wall-clock timeout in seconds; 0 = use JOB_TIMEOUT_SECONDS env (default 0)")
    args = parser.parse_args()

    # Bootstrap logging via the app's logging setup
    try:
        from app.core.logging import setup_logging
        setup_logging()
    except Exception:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

    run_worker(
        queue=args.queue,
        poll_interval=args.poll_interval,
        max_rss_mb=args.max_rss_mb,
        max_jobs=args.max_jobs,
        job_timeout_seconds=args.timeout,
    )


if __name__ == "__main__":
    main()
