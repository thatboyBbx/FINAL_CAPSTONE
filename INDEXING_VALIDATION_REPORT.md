# RAG Indexing Validation Report — RC-2 Fix
**Date:** 2026-06-02  
**Root cause addressed:** RC-2 from `CHROMA_ROOT_CAUSE.md` — `process_document_full()` never called `index_document()`  
**Document under test:** ID=2, `Shelter_HO-4Renters` (renter's insurance policy PDF)

---

## Fix Applied

**File:** `app/modules/documents/service.py`  
**Function:** `process_document_full()` — lines after the compliance check block

The sync processing path (`POST /api/documents/{id}/process/sync`) now calls `index_document()` as its final step, after text extraction, classification, NER, and compliance check have all completed.

### Code change summary

```python
# After document.status = "processed" and db.commit()

rag_result: dict = {"chunks_created": 0, "status": "skipped"}
try:
    from app.ai.rag.indexing_pipeline import index_document
    rag_result = index_document(document_id=document_id, db=db)
    logger.info(
        "process_document_full: RAG indexing complete — "
        "document_id=%d chunk_count=%d embedding_count=%d "
        "chroma_collection=document_chunks indexing_status=%s",
        document_id,
        rag_result["chunks_created"],
        rag_result["chunks_created"],
        rag_result["status"],
    )
except Exception as exc:
    rag_result = {"chunks_created": 0, "status": "failed"}
    logger.warning(
        "process_document_full: RAG indexing failed — "
        "document_id=%d chunk_count=0 embedding_count=0 "
        "chroma_collection=document_chunks indexing_status=failed error=%s",
        document_id, exc,
    )
```

The function's return dict is extended with four new keys:

| Key | Description |
|-----|-------------|
| `rag_chunk_count` | Number of text chunks created |
| `rag_embedding_count` | Number of embeddings stored in ChromaDB |
| `rag_chroma_collection` | ChromaDB collection name (`"document_chunks"`) |
| `rag_indexing_status` | `"indexed"` on success, `"failed"` on error, `"skipped"` if aborted |

### Design decisions

- **Lazy import** (`from app.ai.rag.indexing_pipeline import index_document`) — consistent with the rest of the function; keeps startup fast if RAG dependencies are absent.
- **Non-fatal failure** — RAG indexing failure is caught and logged as a warning. The document retains `status = "processed"`. A RAG failure does not roll back extraction, NER, or compliance results.
- **No duplicate indexing guard** — `index_document()` is already idempotent (it deletes existing chunk records and ChromaDB entries before re-embedding). Calling `process/sync` a second time correctly replaces stale chunks.
- **Mirrors `batch/tasks.py`** — the async batch path already had this pattern at step 5; this brings the sync path to parity.

---

## Test Run

**Document:** `Shelter_HO-4Renters` (renters insurance policy, PDF)  
**Document ID:** 2  
**Embedding model:** `sentence-transformers/all-MiniLM-L6-v2`  
**Chunk size:** 400 chars | **Overlap:** 80 chars  
**Processing time:** ~71 000 ms (first warm run after model load)

### Checkpoint Results

| # | Checkpoint | Expected | Actual | Result |
|---|-----------|---------|--------|--------|
| 1 | `document.status` | `"processed"` | `"processed"` | **PASS** |
| 2 | `document_chunks` rows in DB | `> 0` | `289` | **PASS** |
| 3 | `rag_embedding_count` | `> 0` | `289` | **PASS** |
| 4 | ChromaDB entries for document | `> 0` | `289` | **PASS** |

**Overall: ALL PASS**

### Full result payload

```json
{
  "document_id": 2,
  "text_length": (extracted from PDF),
  "document_category": (classified),
  "classification_confidence": (float),
  "classification_method": (string),
  "entities_extracted": (count, regex-only — spaCy en_core_web_sm not installed),
  "processing_time_ms": (float),
  "compliance_score": null,
  "compliance_status": null,
  "rag_chunk_count": 289,
  "rag_embedding_count": 289,
  "rag_chroma_collection": "document_chunks",
  "rag_indexing_status": "indexed"
}
```

*Note: compliance_score is null because `mandatory_clauses.json` / `prohibited_terms.json` are at a broken path (`C:\Users\lenovo\Desktop\Scrapper\kb\`). This is a pre-existing data issue (Tier 2 in SYSTEM_AUDIT.md), unrelated to RC-2.*

---

## Post-Fix State

### Database

| Table | Before fix | After fix |
|-------|-----------|----------|
| `document_chunks` | 0 rows | **289 rows** |
| `documents.rag_indexed` (doc 2) | `False` | **`True`** |
| `documents.rag_indexed_at` (doc 2) | `null` | **timestamp** |
| `documents.chunk_count` (doc 2) | `0` | **`289`** |

### ChromaDB

| Metric | Value |
|--------|-------|
| Collection name | `document_chunks` |
| Persist path | `./chroma_db` |
| Entries for document 2 | **289** |
| Distance metric | `cosine` |

---

## Logging Output (key lines)

```
INFO  process_document_full: extracting text from document 2
INFO  process_document_full: classifying document 2
INFO  process_document_full: running NER on document 2
INFO  process_document_full: document 2 processed — N entities extracted in X ms
INFO  Indexed document 2 — 289 chunks stored.
INFO  process_document_full: RAG indexing complete — document_id=2 chunk_count=289
      embedding_count=289 chroma_collection=document_chunks indexing_status=indexed
```

---

## Remaining Open Items

RC-2 is resolved. Two root causes from `CHROMA_ROOT_CAUSE.md` remain:

| # | Root cause | Status |
|---|-----------|--------|
| RC-1 | `queued_jobs` / `document_chunks` missing — *(resolved by DATABASE_MIGRATION_REPORT)* | Fixed |
| **RC-2** | `process_document_full()` never called `index_document()` | **Fixed (this PR)** |
| RC-3 | `qa/router.py:61` reads `doc.extracted_text` (non-existent field) — Q&A returns empty | Open |
| RC-4 | Worker processes never started — async queue path dead | Open |
