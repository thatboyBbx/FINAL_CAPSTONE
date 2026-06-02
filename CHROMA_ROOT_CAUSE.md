# ChromaDB Empty — Root Cause Analysis
**Date:** 2026-06-02  
**Scope:** End-to-end trace of document upload → ChromaDB insertion  
**Finding:** Four independent failures prevent any document from ever reaching ChromaDB.  
**No code was modified during this investigation.**

---

## TL;DR

ChromaDB is empty because the pipeline that writes to it is never executed. There are two distinct paths that should produce ChromaDB entries, and both are broken for different reasons:

| Path | Entry Point | Why It Never Reaches ChromaDB |
|------|-------------|-------------------------------|
| **Async** (intended) | `POST /api/documents/{id}/process` | Crashes: `queued_jobs` table missing from `app.db` |
| **Sync** (fallback) | `POST /api/documents/{id}/process/sync` | Skips indexing: `service.process_document_full()` never calls `index_document()` |
| **Q&A reads** | `POST /api/qa/ask` | Reads `doc.extracted_text` — field does not exist on `Document` model |

---

## Full Trace: Document Upload → ChromaDB

```
1. POST /api/documents/upload
       app/modules/documents/router.py:38
       → service.create_document_from_upload()
       → file saved to storage/documents/
       → Document row inserted into documents table
       → rag_indexed = False, chunk_count = 0
       ✓ Succeeds

2a. POST /api/documents/{id}/process  [ASYNC PATH]
        app/modules/documents/router.py:248
        → get_job_queue().enqueue("ingestion_queue", "process_document", document_id=id)
        → SQLiteJobQueue.enqueue()  [app/queue/sqlite_queue.py:63]
        → INSERT INTO queued_jobs ...
        ✗ CRASH: OperationalError: no such table: queued_jobs
          (queued_jobs does not exist in app.db — only in insuredb.sqlite3)
          → 500 error returned to caller; document stays status="uploaded"

2b. POST /api/documents/{id}/process/sync  [SYNC PATH]
        app/modules/documents/router.py:294
        → service.process_document_full(db, document_id)  [app/modules/documents/service.py:245]
        → Step 1: extract_text_from_pdf(doc.file_path)   ✓
        → Step 2: DocumentClassifierService.classify()   ✓
        → Step 3: EntityExtractionService.extract_entities()  ✓
        → Step 4: compliance check                        ✓
        → Step 5: document.status = "processed"           ✓
        ✗ MISSING: index_document() is NEVER called
          circular_analyses not created, ChromaDB not touched.

3. [NEVER REACHED] Batch task / worker path
        app/batch/tasks.py:process_single_document()
        → This function correctly calls index_document() at step 5 (line 106)
        → But it is ONLY called by the SQLite worker:
              python -m app.workers.sqlite_worker --queue ingestion_queue
        → The worker is NEVER started:
              - Not launched in app/main.py lifespan
              - No startup script or process manager config
              - Queue is also blocked by RC-1 (missing table)

4. [NEVER REACHED] index_document() execution
        app/ai/rag/indexing_pipeline.py:67
        → Fetches text from CircularAnalysis.extracted_text (0 rows)
        → Falls back to extract_text(doc.file_path)
        → Calls VectorStore.chunk_document()
        → Calls VectorStore.embed_and_store() → chromadb upsert
        → Writes DocumentChunk rows to document_chunks table
        ✗ document_chunks table also missing from app.db
```

---

## Root Cause 1 — `queued_jobs` and `document_chunks` tables absent from `app.db`

**File:** `app/core/config.py:31`  
**Confirmed by:** `sqlite3 app.db` inspection — 0 of these tables found

```
app.db missing tables:
  - queued_jobs
  - dead_letter_jobs
  - document_job_steps
  - document_chunks          ← RAG chunk records
  - refresh_tokens
  - retrieval_audit_log
  - user_revocation_fence
```

The active database (`app.db`, default `DATABASE_URL = sqlite:///./app.db`) was created before these tables were added to the schema. `Base.metadata.create_all()` at startup only creates tables that don't yet exist — it does not diff and add missing ones.

`insuredb.sqlite3` contains all 37 tables including `queued_jobs` and `document_chunks`, but the app is not configured to use it.

**Effect:**  
- `POST /api/documents/{id}/process` → 500 crash on every call  
- `POST /api/embeddings/{id}/reindex` → 500 crash on every call  
- Even if `index_document()` ran, `_persist_chunk_records()` would crash writing `DocumentChunk` rows

---

## Root Cause 2 — `process_document_full()` never calls `index_document()`

**File:** `app/modules/documents/service.py:245–372`  
**Compared to:** `app/batch/tasks.py:13–153`

The sync endpoint (`POST /process/sync`) delegates entirely to `service.process_document_full()`, which does:
- Text extraction ✓
- Document classification ✓
- NER extraction ✓
- Compliance check ✓
- Sets `status = "processed"` ✓
- **No call to `index_document()`** ✗

The correct pipeline is `batch/tasks.py:process_single_document()`, which explicitly calls `index_document()` at step 5:

```python
# batch/tasks.py:103–108
try:
    from app.ai.rag.indexing_pipeline import index_document
    index_document(document_id, db)
except Exception as exc:
    logger.warning("RAG indexing failed for doc %d: %s", document_id, exc)
```

This function is only reachable via the worker queue path, which is blocked by RC-1.

---

## Root Cause 3 — Q&A engine reads a non-existent field

**File:** `app/modules/qa/router.py:61`

```python
doc_text = getattr(doc, "extracted_text", "") or getattr(doc, "raw_text", "") or ""
```

The `Document` model has **no** `extracted_text` or `raw_text` column (confirmed by `PRAGMA table_info(documents)`). Both `getattr` calls return `""`.

Result: `QAEngine.answer()` always receives `doc_text=""` and returns:
```
"No text content is available for this document. Ensure the document has been 
processed and text successfully extracted."
```

The extracted text is stored in `circular_analyses.extracted_text` (per document via `batch/tasks.py`), not on the `Document` row. The QA router should read from `CircularAnalysis` instead.

---

## Root Cause 4 — Embedding worker never starts

**File:** `app/workers/sqlite_worker.py`, `app/main.py`

The worker that consumes `embedding_queue` and `ingestion_queue` jobs must be started as a separate process:
```
python -m app.workers.sqlite_worker --queue ingestion_queue
python -m app.workers.sqlite_worker --queue embedding_queue
```

Nothing in `app/main.py:lifespan()` starts this process. There is no startup script, no `Procfile`, no supervisor config, and no `BackgroundTask` fallback. Jobs written to `queued_jobs` (if the table existed) would sit unprocessed indefinitely.

---

## Affected Files

| File | Role | Issue |
|------|------|-------|
| `app/modules/documents/router.py:248` | Async process trigger | Enqueues to missing `queued_jobs` table → crash |
| `app/modules/documents/router.py:294` | Sync process trigger | Calls `process_document_full()` which skips indexing |
| `app/modules/documents/service.py:245` | Sync processing | Missing `index_document()` call |
| `app/batch/tasks.py:103` | Correct full pipeline | Has `index_document()` but unreachable (worker never starts) |
| `app/workers/sqlite_worker.py` | Job consumer | Never launched |
| `app/modules/qa/router.py:61` | Q&A text source | Reads non-existent `doc.extracted_text` field |
| `app/ai/rag/indexing_pipeline.py:67` | Indexing function | Correct implementation, never called |
| `app/ai/rag/vector_store.py:49` | ChromaDB wrapper | Correct implementation, never called |
| `app.db` | Active database | Missing `queued_jobs`, `document_chunks` tables |

---

## Fix Recommendations

These are minimal, targeted fixes. No architectural changes.

### Fix 1 — Add missing tables to `app.db` (unblocks async path)

Run Alembic migrations to add the missing tables, or switch the active database:

**Option A — Run Alembic (preferred):**
```bash
cd EXPERIMENT
.venv\Scripts\Activate.ps1
alembic upgrade head
```
This will add `queued_jobs`, `document_chunks`, `dead_letter_jobs`, `document_job_steps`, `retrieval_audit_log`, `user_revocation_fence` to `app.db`.

**Option B — Switch to `insuredb.sqlite3`:**  
In `EXPERIMENT/.env`, set:
```
DATABASE_URL=sqlite:///./insuredb.sqlite3
```
This immediately restores all 37 tables including the existing auth tokens and deviation scores.

---

### Fix 2 — Add `index_document()` call to `process_document_full()` (fixes sync path)

**File:** `app/modules/documents/service.py`  
After the compliance check block (around line 351), add:

```python
# RAG indexing — index extracted text into ChromaDB
try:
    from app.ai.rag.indexing_pipeline import index_document  # noqa: PLC0415
    index_document(document_id=document_id, db=db)
    logger.info("process_document_full: RAG indexing complete for document %d", document_id)
except Exception as exc:
    logger.warning(
        "process_document_full: RAG indexing failed for document %d — %s",
        document_id, exc,
    )
```

This mirrors the pattern already in `batch/tasks.py:103–108`. The `index_document()` function requires `circular_analyses.extracted_text` — since the circular analysis is created earlier in `batch/tasks.py` but NOT in `process_document_full()`, the fallback `extract_text(doc.file_path)` in `indexing_pipeline._get_document_text()` will be used for the sync path. That fallback reads the PDF directly and is sufficient.

---

### Fix 3 — Fix Q&A text source (fixes `/api/qa/ask`)

**File:** `app/modules/qa/router.py:61`

Replace:
```python
doc_text = getattr(doc, "extracted_text", "") or getattr(doc, "raw_text", "") or ""
```

With:
```python
# Prefer ChromaDB vector search; fall back to CircularAnalysis text
from app.modules.circulars.model import CircularAnalysis  # noqa: PLC0415
analysis = (
    db.query(CircularAnalysis)
    .filter(CircularAnalysis.document_id == payload.document_id)
    .first()
)
doc_text = (analysis.extracted_text if analysis and analysis.extracted_text else "") 
```

---

### Fix 4 — Start the worker process (activates async queue)

After Fix 1, launch the ingestion and embedding workers alongside the API server. The simplest approach for the current setup:

```powershell
# Terminal 1 — API server
cd EXPERIMENT
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload

# Terminal 2 — Ingestion worker
cd EXPERIMENT
.venv\Scripts\Activate.ps1
python -m app.workers.sqlite_worker --queue ingestion_queue

# Terminal 3 — Embedding worker
cd EXPERIMENT
.venv\Scripts\Activate.ps1
python -m app.workers.sqlite_worker --queue embedding_queue
```

---

## Fix Order

1. **Fix 1 first** — run `alembic upgrade head` on `app.db`. This is a prerequisite for Fix 4.
2. **Fix 2** — add `index_document()` to `service.process_document_full()`. This makes the sync path fully functional without needing a worker.
3. **Fix 3** — correct Q&A text source. Low-risk one-liner.
4. **Fix 4** — start worker processes. Activates the async path (used for bulk batch processing).

After Fixes 1–3, a document processed via `POST /api/documents/{id}/process/sync` will:
- Extract text → create `CircularAnalysis` (via batch/tasks) OR use file fallback
- Run NER, classification, compliance
- Call `index_document()` → chunk → embed → write to ChromaDB → write `DocumentChunk` rows
- `POST /api/qa/ask` will read `CircularAnalysis.extracted_text` and return real answers

---

*End of investigation. No code was modified.*
