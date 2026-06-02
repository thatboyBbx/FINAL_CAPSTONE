# QA Pipeline Validation Report — RC-3 Fix
**Date:** 2026-06-02  
**Root cause addressed:** RC-3 from `CHROMA_ROOT_CAUSE.md` — `qa/router.py:61` read non-existent `doc.extracted_text`; Q&A always received empty text and returned the "No text content" fallback  
**Document under test:** ID=2, `Shelter_HO-4Renters` (HO-4 renters insurance policy, PDF)

---

## Fix Applied

**File:** `app/modules/qa/router.py`  
**Line:** 61 (was the one-liner `getattr(doc, "extracted_text", "")`)

### Before

```python
doc_text = getattr(doc, "extracted_text", "") or getattr(doc, "raw_text", "") or ""
```

`Document` has neither `extracted_text` nor `raw_text` columns. Both `getattr` calls returned `""`. The Q&A engine always received an empty string and returned:

> *"No text content is available for this document. Ensure the document has been processed and text successfully extracted."*

### After — three-tier text lookup

```
Priority 1: CircularAnalysis.extracted_text
            (populated by the batch pipeline — present for batch-processed docs)

Priority 2: DocumentChunk.chunk_text concatenated in chunk_index order
            (populated by process_document_full() after the RC-2 fix —
             present for any document processed via POST /process/sync)

Priority 3: extract_text_from_pdf(doc.file_path)
            (disk fallback — available for any document with a valid file_path,
             even if not yet indexed)
```

Each tier is wrapped in its own `try/except` so a failure at one level falls through to the next. The active tier is recorded in `text_source` and returned in the response payload.

### Response payload additions

Two fields are added to every `/api/qa/ask` response:

| Field | Description |
|-------|-------------|
| `text_source` | Which tier provided the text: `circular_analysis`, `document_chunks(N)`, `pdf_extraction`, or `none` |
| `text_length` | Character count of the text passed to the QA engine |

---

## Test Run

**Document:** `Shelter_HO-4Renters` (HO-4 renters policy, PDF)  
**Document ID:** 2  
**Question:** *"What are the coverage limits and exclusions?"*

---

### Stage 1 — Document

| Field | Value |
|-------|-------|
| Document ID | 2 |
| Title | `Shelter_HO-4Renters` |
| File path | `storage/documents/e4/e41b...fb182.pdf` |
| File on disk | Yes |
| Pre-stage status | `processed` (from prior RC-2 run) |

---

### Stage 2 — Process (RC-2 path)

`process_document_full(db, document_id=2)` called to simulate the sync processing path.

| Metric | Value |
|--------|-------|
| Processing time | ~73 000 ms |
| Post-process status | `processed` |
| `rag_chunk_count` | 289 |
| `rag_embedding_count` | 289 |
| `rag_indexing_status` | `indexed` |
| `rag_chroma_collection` | `document_chunks` |

---

### Stage 3 — Ask (RC-3 path)

Text lookup result:

| Field | Value |
|-------|-------|
| `text_source` | `document_chunks(289)` |
| `text_length` | **109 673 characters** |

Text was sourced from 289 `DocumentChunk` rows (chunk_text concatenated in chunk_index order). No `CircularAnalysis` row exists for this document because it was processed via the sync path, not the batch pipeline. This is the expected fallback path for sync-processed documents.

QA engine result:

| Field | Value |
|-------|-------|
| `model` | `offline-keyword-search` |
| `confidence` | `0.8` |
| `sources` | `Sentence 687`, `Sentence 633`, `Sentence 677` |

**Answer returned:**

```
Relevant passage from "Shelter_HO-4Renters":

SECTION II - PERSONAL LIABILITY AND MEDICAL PAYMENT PROTECTION COVERAGE E -
PERSONAL LIABILITY With respect to claims arising out of the use of INSURING
AGREEMENT watercraft not owned by an insured, our liability is Subject to the
limit of our liability stated in this limited to $100,000 per accident
regardless of the number of insureds, persons injured, or claims made,
regardless of the limits of liability stated in the Declarations under the
heading Personal Liability accident. In that instance, benefits will under
this provision will not be invalidated by: be payable under this policy only
to the extent the limits of the coverage provided under this policy exceed the
limits provided by the other policy. Appraisal covered property, in kind; or
Any appraisal that becomes necessary under the (d) pay the limit of coverage
stated in this terms of this policy will be handled in accordance policy as
applicable to the item, including any special limits, or limits this policy.

_(Source: Sentence 687, Sentence 633, Sentence 677)_
```

---

## Checkpoint Results

| # | Checkpoint | Expected | Actual | Result |
|---|-----------|---------|--------|--------|
| 1 | `document.status` | `"processed"` | `"processed"` | **PASS** |
| 2 | `text_length` | `> 0` | `109 673` | **PASS** |
| 3 | `text_source` | `!= "none"` | `document_chunks(289)` | **PASS** |
| 4 | Sources returned | `len > 0` | `3 sources` | **PASS** |
| 5 | Real answer (not fallback) | no "No text content" | Answered | **PASS** |

**Overall: ALL PASS**

---

## Log Lines Emitted

```
INFO  QA: doc_id=2 text_source=document_chunks(289) text_length=109673
      question='What are the coverage limits and exclusions?'
```

---

## Text Source Behaviour by Document State

| Document state | text_source | Notes |
|----------------|-------------|-------|
| Batch-processed (batch/tasks.py) | `circular_analysis` | `CircularAnalysis.extracted_text` populated by batch pipeline |
| Sync-processed (`/process/sync`) | `document_chunks(N)` | RC-2 fix stores `chunk_text` in `document_chunks` |
| Uploaded only (not processed) | `pdf_extraction` | PDF read directly from `doc.file_path` |
| File missing, not indexed | `none` | QA engine returns "No text content" fallback — expected |

---

## Remaining Open Items

RC-3 is resolved. One root cause from `CHROMA_ROOT_CAUSE.md` remains:

| # | Root cause | Status |
|---|-----------|--------|
| RC-1 | Missing tables in active DB | Fixed (`DATABASE_MIGRATION_REPORT.md`) |
| RC-2 | `process_document_full()` never called `index_document()` | Fixed (`INDEXING_VALIDATION_REPORT.md`) |
| **RC-3** | Q&A read non-existent `doc.extracted_text` | **Fixed (this report)** |
| RC-4 | Worker processes never started — async queue path dead | Open |

The sync path (`POST /api/documents/{id}/process/sync`) is now fully functional end-to-end:  
upload → process → index → ask → real answer.
