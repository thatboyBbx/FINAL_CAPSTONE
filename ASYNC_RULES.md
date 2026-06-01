# ASYNC_RULES.md
## InsureIntel Zimbabwe — Async Job Structure Standards

---

## 1. Two Async Job Categories

The application uses two distinct patterns for deferred work:

| Category | Mechanism | Session ownership |
|---|---|---|
| **Request-attached background tasks** | FastAPI `BackgroundTasks` | Opens its own `SessionLocal()` |
| **Scheduled scraper/batch jobs** | `APScheduler` via `scraper_scheduler.py` | Opens its own `SessionLocal()` |

Both categories are fire-and-forget from the router's perspective. The router does not await
them or inspect their results.

---

## 2. Background Task Pattern (FastAPI BackgroundTasks)

Use `BackgroundTasks` for post-request work that completes within minutes and whose failure
does not need to be surfaced to the original HTTP caller.

**Router — enqueue only:**
```python
@router.post("/upload", status_code=202)
async def upload(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    doc = document_service.create_document_from_upload(db, file, ...)
    background_tasks.add_task(_process_document_background, doc.id)
    return {"document_id": doc.id, "status": "queued"}
```

**Background function — owns its own session:**
```python
def _process_document_background(doc_id: int) -> None:
    db = SessionLocal()
    try:
        document_service.process_document_full(db, doc_id)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Background processing failed: doc_id=%s", doc_id)
    finally:
        db.close()
```

Rules:
- Background functions must be **synchronous** unless the entire call chain is async.
- They must never accept or reuse the request's `db` session.
- They must log exceptions — `BackgroundTasks` swallows exceptions silently.
- They must update the document/record status (`"processing"` → `"processed"` or `"failed"`) so
  callers can poll.

---

## 3. Scheduled Job Pattern (APScheduler)

Scheduled jobs run on a cron or interval trigger. They run outside the HTTP request lifecycle.

**Structure:**
```python
def run_scraper_job() -> None:
    """Single scheduled job — owns session, logs progress, handles its own errors."""
    logger.info("Scraper job starting: %s", type(self).__name__)
    db = SessionLocal()
    try:
        results = self._scrape()
        self._persist(db, results)
        db.commit()
        logger.info("Scraper job completed: %d records", len(results))
    except Exception:
        db.rollback()
        logger.exception("Scraper job failed")
    finally:
        db.close()
```

Rules:
- Each job function must be self-contained: open session → do work → commit or rollback → close.
- Jobs must never call `db.commit()` on a session passed in from outside.
- If a job processes a collection, use per-item commits with per-item rollback (see
  `TRANSACTION_RULES.md §6`).
- Scheduled jobs must log start, completion, and item counts at `INFO` level.
- Scheduled jobs must catch and log all exceptions without re-raising, so the scheduler does
  not stop running subsequent ticks.

---

## 4. Async vs Sync

`async def` route handlers are correct when at least one `await` call is made (file I/O,
external HTTP, etc.). Do not mark route handlers `async def` if they only call synchronous
service/repo functions — this adds coroutine overhead without benefit.

```python
# Correct: file I/O requires async
async def upload(...):
    saved = await storage.save_upload_file(file)

# Correct: pure sync service call — no async needed
def list_insurers(db: Session = Depends(get_db)):
    return insurer_service.list_insurers(db)
```

---

## 5. Long-Running Jobs

Jobs that may run for more than 30 seconds must be tracked in a status table
(e.g., `ProcessingBatch`, `batch_jobs`). The status must be updated at the start (`"running"`),
on success (`"completed"`), and on failure (`"failed"`). This allows the UI and API to poll
for progress without the job holding an HTTP connection open.

---

## 6. Triggering Jobs from Routers

Routers may trigger background tasks or scheduled jobs, but must not `await` the job's
completion within the request. Return a `202 Accepted` with a job/batch ID for the caller to
poll.

The `app/modules/insurers/router.py` pattern of triggering `_run` on the scraper scheduler
directly inside a route handler is a known violation. It must be converted to a background
task with a `202` response.

---

## 7. No Thread-Local Sessions in Async Contexts

Do not pass SQLAlchemy sessions across thread boundaries. Each thread or async task must own
its own session. Using `SessionLocal()` inside a `BackgroundTasks` function is correct;
passing the request-scoped `db` session into a thread or background task is not.
