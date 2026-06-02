# Database Migration Report
**Date:** 2026-06-02  
**Scope:** Alembic migration state verification and remediation for `insuredb.sqlite3`  
**Outcome:** Active database is now fully aligned with the migration chain. `alembic_version` stamped at head.

---

## 1. Active Database

| Setting | Value |
|---------|-------|
| Config source | `EXPERIMENT/.env` → `DATABASE_URL=sqlite:///./insuredb.sqlite3` |
| Active DB file | `EXPERIMENT/insuredb.sqlite3` |
| `alembic.ini` `sqlalchemy.url` | `sqlite:///./app.db` *(overridden at runtime by `settings.database_url`)* |

**Key finding:** The `.env` file overrides `alembic.ini`'s static URL. `app.db` is NOT the active database; `insuredb.sqlite3` is. All previous system-audit findings that referenced `app.db` as the active database were based on direct file inspection — `app.db` is an unused legacy copy.

---

## 2. Pre-Migration State

### `insuredb.sqlite3` (active)
- **`alembic_version`:** Table existed but was empty (no rows)
- **Tables:** 38 (all required tables already present)
- **Gap:** DB was created via `Base.metadata.create_all()` directly, not through Alembic. Schema was complete but Alembic tracking was absent.

### `app.db` (inactive)
- **`alembic_version`:** `942e478fe635` (last applied migration: compliance module)
- **Tables:** 30 — missing `queued_jobs`, `dead_letter_jobs`, `document_job_steps`, `document_chunks`, `refresh_tokens`, `access_token_blacklist`, `user_revocation_fence`, `retrieval_audit_log`
- **Status:** Stale; not used by the running application.

---

## 3. Migration Chain (Final State)

```
<base>
  └── 001_add_document_folder_client_id
        └── 9e599c7786d4  (baseline full schema)
              └── 07745ea1a6ab  (clients module)
                    └── 4cf69424aba9  (CSP module)
                          └── 942e478fe635  (compliance module)
                                └── a3f8c2e91b04  (RAG governance schema)
                                      └── b001_merge_heads_add_missing_tables  ← HEAD
```

### Changes Made to Migration Files

| File | Change | Reason |
|------|--------|--------|
| `alembic/env.py` | Added imports: `embeddings.model`, `jobs.model`, `auth.token_store`, `rag_governance.model` | These models were absent → their tables were invisible to Alembic autogenerate |
| `a3f8c2e91b04_rag_governance_schema.py` | Re-based `down_revision` from `9e599c7786d4` → `942e478fe635`; made `document_chunks` creation conditional | Was on parallel branch; conditional create handles DBs where table is absent |
| `b001_merge_heads_add_missing_tables.py` | **New file** | Creates `queued_jobs`, `dead_letter_jobs`, `document_job_steps`, `refresh_tokens`, `access_token_blacklist`, `user_revocation_fence` for DBs that lack them |

---

## 4. Migration Action Taken

`insuredb.sqlite3` already contained all required tables (created via `Base.metadata.create_all()`). Running `alembic upgrade head` would have re-run every migration from scratch against a DB it incorrectly treated as fresh. Instead:

```powershell
alembic stamp b001_merge_heads_add_missing_tables
```

This wrote `b001_merge_heads_add_missing_tables` into `alembic_version` without executing any DDL, bringing Alembic's tracking into sync with the DB's actual schema state.

---

## 5. Post-Migration Verification

### Migration Version

| Database | Before | After |
|----------|--------|-------|
| `insuredb.sqlite3` | *(empty — no tracked version)* | `b001_merge_heads_add_missing_tables` (head) |
| `app.db` | `942e478fe635` | *(unchanged — not active)* |

### Table Existence (insuredb.sqlite3)

| Table | Status | Rows |
|-------|--------|------|
| `document_chunks` | ✓ present | 0 |
| `queued_jobs` | ✓ present | 0 |
| `dead_letter_jobs` | ✓ present | 0 |
| `document_job_steps` | ✓ present | 0 |
| `refresh_tokens` | ✓ present | 7 |
| `access_token_blacklist` | ✓ present | 1 |
| `user_revocation_fence` | ✓ present | 0 |
| `retrieval_audit_log` | ✓ present | 0 |
| `compliance_results` | ✓ present | 1 |
| `document_chunks columns` | ✓ all 14 columns incl. `chunk_text`, `page_estimate`, `section_label`, `word_count` | — |

### Existing Data Preserved

| Table | Rows | Status |
|-------|------|--------|
| `insurers` | 72 | ✓ preserved |
| `users` | 3 | ✓ preserved |
| `clause_deviation_scores` | 558 | ✓ preserved |
| `audit_log` | 148 | ✓ preserved |
| `refresh_tokens` | 7 | ✓ preserved |
| `access_token_blacklist` | 1 | ✓ preserved |

No data loss. The stamp operation writes only to `alembic_version`; no rows were modified or deleted.

---

## 6. Data Preservation Concerns

All existing rows are intact. The following tables are empty and require seeding before analytics features work:

| Table | Rows | Required For |
|-------|------|-------------|
| `insurer_financials` | 0 | CSP scoring, ML training |
| `document_chunks` | 0 | RAG Q&A (ChromaDB parallel store) |
| `circular_analyses` | 0 | NER, classification, Q&A text source |
| `standard_clauses` | 0 | Clause deviation scoring |
| `news_articles` | 0 | ML sentiment features |
| `intel_articles` | 0 | Intelligence dashboard |
| `financial_snapshots` | 0 | ML time-series features |
| `csp_scores` | 0 | CSP dashboard |
| `queued_jobs` | 0 | Async document processing |

These are data-starvation issues, not schema issues. See `SYSTEM_AUDIT.md` Tier 1 for the seeding fix order.

---

## 7. Next Steps

The schema is now fully aligned. The async document processing pipeline (root causes 1 & 4 from `CHROMA_ROOT_CAUSE.md`) is unblocked at the schema level:

1. **RC-2 still outstanding** — `service.process_document_full()` in `app/modules/documents/service.py:245` does not call `index_document()`. The sync path will not populate ChromaDB until this is fixed.
2. **RC-3 still outstanding** — `app/modules/qa/router.py:61` reads non-existent `doc.extracted_text`. Q&A returns empty text until fixed.
3. **RC-4 still outstanding** — Worker processes must be started manually to consume `ingestion_queue` and `embedding_queue`.

Future `alembic upgrade head` runs will work correctly against `insuredb.sqlite3` — the DB is now Alembic-tracked at head.
