# Sync-Mode Operation Guide
**Date:** 2026-06-02  
**Context:** RC-4 (async worker processes never started) remains open.  
This document answers: can the system operate fully without worker processes, and if so, how?

---

## Executive Summary

**Yes — the system is fully operational in sync mode without worker processes.**

Every feature that matters for end-to-end document intelligence is available through synchronous endpoints. The async queue path (`POST /process`) is the only dead code path; it can be safely ignored or avoided by always using `POST /process/sync` instead.

---

## The Two Processing Paths

### Path A — Async queue (requires workers, currently broken)

```
POST /api/documents/{id}/process
```

1. Inserts a row into `queued_jobs` (status = `"queued"`)
2. Also inserts a row into `document_job_steps`
3. Returns HTTP 202 immediately — **does not process the document**
4. A worker process must be running to claim and execute the job

**Without workers:** The job row sits in `queued_jobs` indefinitely. The document's `status` column never advances past its pre-call value. No processing occurs.

### Path B — Sync (no workers required, fully functional)

```
POST /api/documents/{id}/process/sync
```

1. Calls `service.process_document_full()` directly in the request thread
2. Runs the complete pipeline in-process (blocks until done, ~60-120 s for a typical PDF)
3. Returns HTTP 200 with the full result dict
4. No dependency on `queued_jobs`, workers, or background processes

**Pipeline steps executed by the sync path:**

| Step | Action | Output |
|------|--------|--------|
| 1 | PDF text extraction | raw text string |
| 2 | Document classification | `document_category`, `classification_confidence` |
| 3 | NER entity extraction | rows in `extracted_entities` |
| 4 | Compliance check | row in `compliance_results` |
| 5 | Mark status = `"processed"` | `documents.status` updated |
| 6 | RAG indexing (RC-2) | 289+ rows in `document_chunks`, embeddings in ChromaDB |

After this call completes, the document is ready for Q&A.

---

## Running the Application Without Workers

### Start the server

```powershell
cd C:\Users\lenovo\Desktop\CODEX2\EXPERIMENT
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

No additional processes are needed.

### Document workflow (sync-only)

```
1. Upload:   POST /api/documents/upload         (multipart/form-data, returns document_id)
2. Process:  POST /api/documents/{id}/process/sync   (blocks; ~60-120 s)
3. Ask:      POST /api/qa/ask                   {"document_id": N, "question": "..."}
```

Do **not** use `POST /api/documents/{id}/process` (async). It will return HTTP 202 and enqueue a job that will never be executed.

### Re-indexing only (if needed)

```
POST /api/qa/index/{document_id}
```

This triggers `index_document()` directly with no queue dependency.

---

## Endpoint Availability Matrix

### Fully available without workers

| Endpoint group | Notes |
|----------------|-------|
| Auth — `/auth/*` | No worker dependency |
| Documents — upload, list, get, download, update, archive, delete, folder, assign-client | No worker dependency |
| **`POST /documents/{id}/process/sync`** | The sync pipeline; fully functional after RC-2/RC-3 |
| Documents — text, entities, compliance, classification, reclassify, compliance/recheck | Read/compute from DB and disk |
| Q&A — `POST /api/qa/ask` | Three-tier text lookup; no worker dependency |
| Q&A — `POST /api/qa/index/{id}` | Direct RAG indexing; no worker dependency |
| Q&A — `GET /api/qa/sessions/{id}` | DB read |
| Insurers, financials, news, intel, settlement | No worker dependency |
| Batch, tracker, multilingual, chatbot, reports | No worker dependency |
| Admin jobs — `/api/admin/jobs/stats`, `/health`, `/steps/{id}`, `/dead-letter` | Read `queued_jobs` table; works without workers (just shows idle queue) |
| All other API routes | No worker dependency |

### Broken without workers

| Endpoint | Failure mode |
|----------|-------------|
| `POST /api/documents/{id}/process` | Returns HTTP 202, enqueues job. **Document is never processed.** Status stays at `"uploaded"` forever. |
| `POST /api/admin/jobs/dead-letter/{id}/redrive` | Re-enqueues the job successfully, but the redriven job is also never executed. |

---

## queued_jobs Table Behavior Without Workers

If `POST /api/documents/{id}/process` is called at all, rows accumulate in `queued_jobs` with `status = "queued"`. Key points:

- **No blocking effect.** The growing table does not affect any other endpoint.
- **No FK cascade.** `document_job_steps` rows are appended alongside job rows; both tables are append-only from the API's perspective.
- **No attempt increments.** Jobs are never claimed, so `attempt` stays at 0. Max-attempts logic never triggers. The dead-letter queue remains empty.
- **No data loss.** Documents themselves are unaffected; only their processing is skipped.
- **Observable via monitoring.** `GET /api/admin/jobs/health` will report growing queue depth and increasing "oldest queued age" — a clear signal that no worker is running.

To avoid accumulation: simply do not call `POST /api/documents/{id}/process`. Use the sync endpoint exclusively.

---

## Limitations of Sync-Only Mode

| Limitation | Impact | Workaround |
|------------|--------|------------|
| Processing blocks the HTTP request thread for ~60-120 s per document | Not suitable for concurrent batch uploads | Process documents sequentially; use scripted loops |
| No per-step progress visibility during processing | Cannot poll job step status mid-run | Poll `GET /api/documents/{id}` after the call returns |
| No retry on failure | If the sync call fails (network drop, timeout), the caller must re-call manually | Client-side retry with idempotent re-call |
| `POST /api/admin/jobs/stats` reports a growing backlog if async endpoint was called | Dashboard looks alarming | Ignore queue metrics; use `document.status` as the ground truth |
| Batch pipeline (`app/batch/tasks.py`) runs only via workers | `CircularAnalysis.extracted_text` is only populated by the worker path | For documents processed via sync, Q&A uses the `document_chunks` fallback (RC-3 fix); behavior is correct |

---

## Text Source Behaviour by Processing Path

The Q&A engine (RC-3 fix) uses a three-tier lookup regardless of how the document was processed:

| Processing path | text_source returned by /api/qa/ask | Notes |
|-----------------|-------------------------------------|-------|
| Sync (`/process/sync`) | `document_chunks(N)` | RC-2 stores chunks during sync; RC-3 reads them back |
| Async worker path (batch pipeline) | `circular_analysis` | Worker populates `CircularAnalysis.extracted_text` |
| Uploaded only, not processed | `pdf_extraction` | Fallback reads file directly from disk |
| File missing or unprocessed, no disk file | `none` | Q&A returns "No text content" fallback — expected |

In sync-only mode all documents land in tier 2 (`document_chunks`). This is functionally identical to tier 1 for Q&A purposes; both provide the full document text.

---

## Verification Checklist

Run these checks to confirm sync mode is operational:

```
[ ] Server starts without errors:  GET /health -> {"status": "ok"}
[ ] Upload succeeds:               POST /api/documents/upload -> document_id returned
[ ] Sync process succeeds:         POST /api/documents/{id}/process/sync
                                     -> rag_indexing_status == "indexed"
                                     -> rag_chunk_count > 0
[ ] Q&A returns real answer:       POST /api/qa/ask
                                     -> text_source != "none"
                                     -> text_length > 0
                                     -> answer does not contain "No text content"
[ ] Queue shows idle (not broken): GET /api/admin/jobs/health
                                     -> queued count == 0 (if async endpoint not used)
```

---

## Current Root Cause Status

| # | Root cause | Status |
|---|-----------|--------|
| RC-1 | Missing tables in active DB | Fixed (`DATABASE_MIGRATION_REPORT.md`) |
| RC-2 | `process_document_full()` never called `index_document()` | Fixed (`INDEXING_VALIDATION_REPORT.md`) |
| RC-3 | Q&A read non-existent `doc.extracted_text` | Fixed (`QA_VALIDATION_REPORT.md`) |
| RC-4 | Worker processes never started — async queue path dead | Fixed (in-process thread worker, see below) |

## RC-4 Fix Summary

An in-process background thread worker is now started automatically on server startup.

**Files changed:**

| File | Change |
|------|--------|
| `app/workers/sqlite_worker.py` | Added `run_worker_thread(queue, stop_event, ...)` — thread-safe polling loop using `threading.Event` instead of OS signal handlers |
| `app/core/config.py` | Added `AUTO_START_WORKERS` (default `true`) and `WORKER_POLL_INTERVAL` (default `3.0` s) settings |
| `app/main.py` | `lifespan()` now starts an `ingestion-worker` daemon thread on startup and joins it on shutdown |

**Behaviour:**

- Server start: `[thread-worker] started — queue=ingestion_queue` appears in logs
- `POST /api/documents/{id}/process` now works end-to-end: job is enqueued, worker claims it within `WORKER_POLL_INTERVAL` seconds, `process_single_document()` runs the full batch pipeline
- Graceful shutdown: `_worker_stop.set()` wakes the idle sleep immediately; thread joins within the current job's duration (up to 30 s timeout)
- Memory guard and stuck-job reclaim are active, same as the standalone worker process

**To disable auto-start** (e.g. when running dedicated external worker processes):

```
AUTO_START_WORKERS=false
```

Both paths are now fully functional end-to-end:

- Async: `POST /process` -> worker picks up job -> `process_single_document()` (batch pipeline, populates `CircularAnalysis`)
- Sync:  `POST /process/sync` -> inline `process_document_full()` (NER pipeline, populates `document_chunks`)
