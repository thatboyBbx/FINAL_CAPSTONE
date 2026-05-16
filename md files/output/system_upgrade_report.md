# System Upgrade Report
**Project:** Insurance Document Intelligence Platform
**Student:** Bobojani Panashe S — R228131Q

---

## 1. Architecture Changes

### New Directories Created

| Directory | Purpose |
|-----------|---------|
| `app/ai/` | AI/ML subsystem root |
| `app/ai/models/` | Serialised model artifacts (.joblib/.pkl) |
| `app/ai/training/` | Training scripts and data generation utilities |
| `app/ai/inference/` | Classifier service, WCS scorer, XGBoost wrapper |
| `app/ai/rag/` | QA engine, vector store, indexing pipeline |
| `app/ai/multilingual/` | MarianMT translation, language detection |
| `app/infrastructure/` | Infrastructure services root |
| `app/infrastructure/scrapers/` | News/IPEC scrapers, APScheduler jobs |
| `app/infrastructure/storage/` | Storage layer root |
| `app/infrastructure/storage/training_data/` | CSV training datasets |
| `app/infrastructure/db/` | Database infrastructure placeholder |
| `app/domains/` | Domain model root |
| `app/domains/insurance/` | Insurance document domain |
| `app/domains/clients/` | Client management domain |
| `app/domains/compliance/` | Regulatory compliance domain |
| `app/domains/analytics/` | CSP analytics domain |

All directories created with `__init__.py` files.

---

### Files Moved (Canonical Locations)

#### app/ml/ → app/ai/inference/ and app/ai/training/

| Old Path | New Canonical Path | Notes |
|----------|-------------------|-------|
| `app/ml/csp_normalizer.py` | `app/ai/inference/csp_normalizer.py` | No import changes required |
| `app/ml/csp_wcs_scorer.py` | `app/ai/inference/csp_wcs_scorer.py` | Import updated |
| `app/ml/csp_xgboost_model.py` | `app/ai/inference/csp_xgboost_model.py` | No import changes |
| `app/ml/csp_nlg.py` | `app/ai/inference/csp_nlg.py` | Import updated |
| `app/ml/csp_training_pipeline.py` | `app/ai/training/csp_training_pipeline.py` | Import updated |

#### app/rag/ → app/ai/rag/

| Old Path | New Canonical Path | Notes |
|----------|-------------------|-------|
| `app/rag/qa_engine.py` | `app/ai/rag/qa_engine.py` | Enhanced with logging (Task 4) |
| `app/rag/vector_store.py` | `app/ai/rag/vector_store.py` | Enhanced with health_check (Task 4) |
| `app/rag/indexing_pipeline.py` | `app/ai/rag/indexing_pipeline.py` | Import updated |

#### app/multilingual/ → app/ai/multilingual/

| Old Path | New Canonical Path | Notes |
|----------|-------------------|-------|
| `app/multilingual/language_detector.py` | `app/ai/multilingual/language_detector.py` | No import changes |
| `app/multilingual/multilingual_pipeline.py` | `app/ai/multilingual/multilingual_pipeline.py` | No import changes |

#### app/scrapers/ → app/infrastructure/scrapers/

| Old Path | New Canonical Path | Notes |
|----------|-------------------|-------|
| `app/scrapers/base_scraper.py` | `app/infrastructure/scrapers/base_scraper.py` | No import changes |
| `app/scrapers/ipec_scraper.py` | `app/infrastructure/scrapers/ipec_scraper.py` | Imports updated |
| `app/scrapers/ipec_fsr1_scraper.py` | `app/infrastructure/scrapers/ipec_fsr1_scraper.py` | No import changes |
| `app/scrapers/news_scraper.py` | `app/infrastructure/scrapers/news_scraper.py` | Imports updated |
| `app/scrapers/scraper_utils.py` | `app/infrastructure/scrapers/scraper_utils.py` | No import changes |
| `app/scrapers/scraper_scheduler.py` | `app/infrastructure/scrapers/scraper_scheduler.py` | Imports updated |

---

### Imports Updated

#### Internal imports fixed in new canonical files

| File | Old import | New import |
|------|-----------|-----------|
| `app/ai/inference/csp_wcs_scorer.py` | `from app.ml.csp_normalizer import ...` | `from app.ai.inference.csp_normalizer import ...` |
| `app/ai/inference/csp_nlg.py` | `from app.ml.csp_wcs_scorer import CSPComponentScores` | `from app.ai.inference.csp_wcs_scorer import CSPComponentScores` |
| `app/ai/inference/csp_nlg.py` | `from app.ml.csp_wcs_scorer import WCSScorer` | `from app.ai.inference.csp_wcs_scorer import WCSScorer` |
| `app/ai/training/csp_training_pipeline.py` | `from app.ml.csp_xgboost_model import ...` | `from app.ai.inference.csp_xgboost_model import ...` |
| `app/ai/rag/indexing_pipeline.py` | `from app.rag.vector_store import ...` | `from app.ai.rag.vector_store import ...` |
| `app/infrastructure/scrapers/scraper_scheduler.py` | `"ipec": "app.scrapers.ipec_scraper:IPECScraper"` | `"ipec": "app.infrastructure.scrapers.ipec_scraper:IPECScraper"` |
| `app/infrastructure/scrapers/scraper_scheduler.py` | `"news": "app.scrapers.news_scraper:NewsScraper"` | `"news": "app.infrastructure.scrapers.news_scraper:NewsScraper"` |
| `app/infrastructure/scrapers/ipec_scraper.py` | `from app.scrapers.base_scraper import ...` | `from app.infrastructure.scrapers.base_scraper import ...` |
| `app/infrastructure/scrapers/ipec_scraper.py` | `from app.scrapers.scraper_utils import ...` | `from app.infrastructure.scrapers.scraper_utils import ...` |
| `app/infrastructure/scrapers/news_scraper.py` | `from app.scrapers.base_scraper import ...` | `from app.infrastructure.scrapers.base_scraper import ...` |
| `app/infrastructure/scrapers/news_scraper.py` | `from app.scrapers.scraper_utils import ...` | `from app.infrastructure.scrapers.scraper_utils import ...` |

#### app/main.py updated (router registration)

| Old import | New import |
|-----------|-----------|
| `from app.scrapers.scraper_scheduler import start_scheduler` | `from app.infrastructure.scrapers.scraper_scheduler import start_scheduler` |

#### Backward-compatibility stubs created at old locations

Stub files were written at each old path to ensure all existing consumers (batch/tasks.py,
comparison/clause_aligner.py, modules/qa/router.py, modules/multilingual/router.py, etc.)
continue to work without modification. Each stub re-exports all names from the new location:

- `app/ml/csp_normalizer.py` → re-exports from `app.ai.inference.csp_normalizer`
- `app/ml/csp_wcs_scorer.py` → re-exports from `app.ai.inference.csp_wcs_scorer`
- `app/ml/csp_xgboost_model.py` → re-exports from `app.ai.inference.csp_xgboost_model`
- `app/ml/csp_nlg.py` → re-exports from `app.ai.inference.csp_nlg`
- `app/ml/csp_training_pipeline.py` → re-exports from `app.ai.training.csp_training_pipeline`
- `app/rag/qa_engine.py` → re-exports from `app.ai.rag.qa_engine`
- `app/rag/vector_store.py` → re-exports from `app.ai.rag.vector_store`
- `app/rag/indexing_pipeline.py` → re-exports from `app.ai.rag.indexing_pipeline`
- `app/multilingual/language_detector.py` → re-exports from `app.ai.multilingual.language_detector`
- `app/multilingual/multilingual_pipeline.py` → re-exports from `app.ai.multilingual.multilingual_pipeline`
- `app/scrapers/scraper_scheduler.py` → re-exports from `app.infrastructure.scrapers.scraper_scheduler`
- `app/scrapers/base_scraper.py` → re-exports from `app.infrastructure.scrapers.base_scraper`
- `app/scrapers/scraper_utils.py` → re-exports from `app.infrastructure.scrapers.scraper_utils`
- `app/scrapers/ipec_scraper.py` → re-exports from `app.infrastructure.scrapers.ipec_scraper`
- `app/scrapers/ipec_fsr1_scraper.py` → re-exports from `app.infrastructure.scrapers.ipec_fsr1_scraper`
- `app/scrapers/news_scraper.py` → re-exports from `app.infrastructure.scrapers.news_scraper`

---

### Additional Cleanup Performed

- Deleted `app/ui_backup_20260427_010403/` (leftover from previous refactor session).

---

## 2. Startup Verification

```
INFO:     Started server process [18992]
INFO:     Waiting for application startup.
INFO apscheduler.scheduler Adding job tentatively...
INFO apscheduler.scheduler Scheduler started
INFO app.infrastructure.scrapers.scraper_scheduler Scraper scheduler started
INFO app.main Scraper scheduler started.
INFO app.main InsureIntel Zimbabwe started — env=dev
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000

GET /health → 200 OK
{"status":"ok","env":"dev"}
```

**Result:** Application starts successfully. The scheduler log line confirms the new import path
`app.infrastructure.scrapers.scraper_scheduler` is active. Health endpoint returns 200.

---

## 3. Synthetic Dataset

Script: `app/infrastructure/storage/training_data/generate_synthetic_data.py`
Output: `app/infrastructure/storage/training_data/insurance_synthetic.csv`

```
Generated: 1500 rows
Anomalies: 120 flagged
Risk distribution:
  strong      : 546 rows
  adequate    : 850 rows
  watch       : 104 rows
  distressed  : 0 rows
Saved to: app/infrastructure/storage/training_data/insurance_synthetic.csv
```

CSV row count verified: 1501 lines (1 header + 1500 data rows).

---

## 4. Knowledge Base Fixes

### qa_engine.py — changes applied
- Added DEBUG log call: query received (document_id, question truncated to 80 chars)
- Added DEBUG log call: number of keywords extracted
- Added DEBUG log call: number of candidate sentences scored
- Added WARNING log call: empty document_text → fallback path
- Added WARNING log call: no keywords extracted → fallback path
- Added WARNING log call: zero results retrieved → fallback path
- Added ERROR log call with exc_info=True: unhandled exception (re-raised after logging)
- Added module-level `_FALLBACK_EMPTY` dict with spec-required response structure
- Entire `answer()` body wrapped in try/except Exception with re-raise

### vector_store.py — changes applied
- ChromaDB `__init__` already had ImportError try/except — added additional bare Exception block
  raising descriptive `RuntimeError(f"VectorStore failed to initialise ChromaDB at '{persist_dir}': {exc}")`
- `collection.upsert()` already wrapped in try/except in `embed_and_store()` — confirmed
- `collection.query()` already wrapped in try/except in `query()`, returns `[]` on failure — confirmed
- `collection.delete()` already wrapped in try/except in `delete_document()` — confirmed
- Added `health_check() -> bool` method to `VectorStore` class: calls `self._col.count()`,
  returns True on success, logs WARNING and returns False on any exception

---

## 5. UI Fixes

### app/ui/templates/base.html
- Updated light-mode `.alert-error` rule: `background:#fff1f0; color:#ff4d4f; border-color:#ffccc7;`
  (was: `background:rgba(186,26,26,0.06); color:#ba1a1a;`)
- Added `.error-visible` CSS class: `color:#ff4d4f; background:#fff1f0; border:1px solid #ffccc7; border-radius:4px; padding:8px 12px;`

### app/ui/templates/login.html
- Updated inline `.alert-error` padding/border-radius to match spec: `padding:8px 12px; border-radius:4px;`
- Updated light-mode override: `color:#ff4d4f; background:#fff1f0; border:1px solid #ffccc7;`
  (was: `color:#dc2626;`)

### app/ui/templates/register.html
- Updated inline `.alert-error` padding/border-radius: `padding:8px 12px; border-radius:4px;`
- Updated light-mode override: `color:#ff4d4f; background:#fff1f0; border:1px solid #ffccc7;`
  (was: `color:#dc2626;`)

### Elements intentionally not modified
- `display:none` on accordion bodies (navigation sidebar) — not error display elements
- `display:none` on `#globalErrorModal` (base.html) — correctly hidden until JS fires
- `display:none` on `#upload-error` (upload.html) — correctly toggled by XHR JS handler;
  uses `.alert-error` which now inherits the corrected styles from base.html
