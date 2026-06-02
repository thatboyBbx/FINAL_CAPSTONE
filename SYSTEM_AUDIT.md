# SYSTEM AUDIT — InsureIntel Zimbabwe
**Date:** 2026-06-02  
**Auditor:** Claude Code (automated read-only audit, no code modified)  
**Scope:** Full repository — `EXPERIMENT/` directory  

---

## 1. CURRENT ARCHITECTURE

### Overview
InsureIntel Zimbabwe is a FastAPI application that processes Zimbabwean insurance regulatory documents, analyzes insurer financial data, and provides AI-powered risk analytics. It has six core functional domains:

| Domain | Entry Point | Purpose |
|--------|-------------|---------|
| Knowledge Base | `app/modules/deviation/knowledge_base_seeder.py` | Standard insurance clause library |
| RAG | `app/ai/rag/` | Document Q&A and clause retrieval |
| Insurance Intel | `app/modules/intel/` | News ingestion, risk classification |
| CSP Scoring | `app/modules/csp/service.py` + `app/ai/inference/` | Claims Settlement Power analytics |
| ML Analytics | `app/modules/ml/` | Financial risk prediction, forecasting |
| Clause Deviations | `app/modules/deviation/` | Policy clause deviation from standard |

### Tech Stack
- **API:** FastAPI, SQLAlchemy (SQLite), Alembic migrations  
- **ML:** scikit-learn (GBDT, LogReg, TF-IDF+SGD), XGBoost, sentence-transformers  
- **RAG:** ChromaDB (vector store), sentence-transformers/all-MiniLM-L6-v2  
- **NLP:** spaCy, keyword extraction (offline — no LLM API calls)  
- **Data Sources:** IPEC scrapers, GDELT news API, uploaded PDFs  
- **Auth:** JWT access/refresh tokens, RBAC, rate limiting  

### Active Database
- **Primary:** `app.db` (SQLite, 2.1 MB, 30 tables)  
- **Secondary:** `insuredb.sqlite3` (SQLite, 788 KB, 37 tables)  
- **Issue:** Two databases exist. `insuredb.sqlite3` has 7 additional tables (refresh_tokens, document_chunks, queued_jobs, dead_letter_jobs, document_job_steps, retrieval_audit_log, user_revocation_fence). The app starts with `app.db` via the default DATABASE_URL and is missing these newer tables. Schema is diverged.

---

## 2. MODULE LOCATIONS

### 2.1 Knowledge Base Source Documents
```
EXPERIMENT/sources/downloads/insurance_circulars/   ← IPEC circulars 2006–2026 (~300 PDFs)
EXPERIMENT/sources/downloads/SOURCES/               ← Insurance Act, Technical Standards, QRTs
EXPERIMENT/sources/downloads/insurancedocuments/    ← Policy document samples
EXPERIMENT/sources/kb/                              ← Knowledge base raw documents
EXPERIMENT/storage/documents/                       ← Uploaded documents (6 in DB)
```
**Standard clause definitions (in-code):** `app/modules/deviation/knowledge_base_seeder.py:29` — 11 built-in Zimbabwe/IAIS clauses  
**Corpus manifest:** `storage/datasets/app/rag_document_manifest.json` — 650 entries (source PDFs mapped, not yet DB-loaded)

### 2.2 RAG Implementation
```
app/ai/rag/qa_engine.py           ← Q&A engine (offline keyword-search mode)
app/ai/rag/vector_store.py        ← ChromaDB wrapper + SentenceTransformer embeddings
app/ai/rag/indexing_pipeline.py   ← Chunk + embed pipeline
app/ai/rag/retrieval_scorer.py    ← Relevance scoring
app/ai/rag/citation_tracker.py    ← Source attribution
app/ai/rag/governance.py          ← Confidence filtering
app/modules/qa/router.py          ← /qa endpoints
app/modules/embeddings/router.py  ← /embeddings endpoints
app/modules/rag_governance/router.py ← Audit log endpoints
```

### 2.3 Insurance Intel Module
```
app/modules/intel/router.py           ← /intel endpoints (ingest, articles, stats, train)
app/modules/intel/repo.py             ← DB queries
app/modules/intel/classifier.py       ← TF-IDF + LR risk classifier
app/modules/intel/gdelt.py            ← GDELT news ingestion
app/modules/intel/advisory_service.py ← Multi-signal advisory engine
app/modules/intel/settlement_router.py ← /intel/settlement endpoints
```
**Note:** No `service.py` exists. The router calls repo/classifier/gdelt directly.

### 2.4 CSP Scoring Module
```
app/modules/csp/service.py             ← CSP orchestrator (scoring, lookup, refresh)
app/modules/csp/model.py               ← CSPScore ORM model
app/ai/inference/csp_wcs_scorer.py     ← Weighted Composite Score engine
app/ai/inference/csp_xgboost_model.py  ← XGBoost anomaly detection
app/ai/inference/csp_nlg.py            ← Natural language summary generator
app/ai/inference/csp_normalizer.py     ← Feature normalization
app/api/routes/csp_routes.py           ← /analytics/settlement-power/ endpoints
```

### 2.5 ML Analytics Module
```
app/modules/ml/trainer.py              ← GBDT/LogReg training (19 features)
app/modules/ml/predictor.py            ← Per-insurer risk prediction
app/modules/ml/forecaster.py           ← MLP financial time-series forecasting
app/modules/ml/explain.py              ← SHAP explanations
app/modules/ml/router.py               ← /ml endpoints
app/modules/ml/training_orchestrator.py ← Corpus build + classifier + settlement model
app/modules/ml/circular_classifier.py  ← TF-IDF + SGD circular classifier
app/modules/scoring/fusion.py          ← ML + news + circular signal fusion
storage/models/app/model.joblib        ← Trained settlement risk model (app profile)
storage/models/demo/model.joblib       ← Trained settlement risk model (demo profile)
```

### 2.6 Clause Deviations Module
```
app/modules/deviation/clause_scorer.py         ← Cosine-similarity clause scorer
app/modules/deviation/knowledge_base_seeder.py ← KB seeder (IAIS + Kaggle + built-ins)
app/modules/deviation/model.py                 ← StandardClause + ClauseDeviationScore ORM
app/modules/deviation/router.py                ← /api/deviation endpoints
app/modules/shared/clause_classifier.py        ← Keyword-based clause type classifier
```

---

## 3. COMPLETE FLOW TRACE

```
SOURCE DOCUMENTS
  EXPERIMENT/sources/downloads/insurance_circulars/ (300+ PDFs)
  EXPERIMENT/sources/downloads/SOURCES/             (Legislation, Technical Standards)
  EXPERIMENT/sources/kb/                            (KB documents)
      ↓
INGESTION
  app/modules/documents/ingestion/corpus_builder.py     ← Scans source dirs, extracts text
  app/modules/documents/ingestion/pdf_extractor.py      ← pdfplumber PDF→text
  app/modules/documents/ingestion/feature_extractor.py  ← Category inference
      ↓ writes to ↓
  storage/datasets/app/circulars_corpus.json            (592 records, populated)
      ↓ [BROKEN: DEFAULT_SOURCES paths in training_orchestrator.py are stale]
PROCESSING
  app/modules/circulars/extractor.py                    ← Text cleaning
  app/modules/circulars/classifier.py                   ← Category classification
  app/modules/documents/classifier_service.py           ← Document type classification
  app/modules/documents/entity_extraction_service.py    ← NER (spaCy)
      ↓ stores to ↓
  DB: circular_analyses (0 rows — EMPTY)
  DB: extracted_entities (4 rows — near-empty)
      ↓
RAG
  app/ai/rag/indexing_pipeline.py   ← chunk_document → embed_and_store
      ↓ uses ↓
  ChromaDB (./chroma_db — DOES NOT EXIST on disk)
      ↓
  DB: document_chunks (0 rows — not indexed)
      ↓
  app/ai/rag/qa_engine.py           ← Falls back to offline keyword search
                                       (no ChromaDB, no extracted text)
      ↓
ANALYTICS (ALL BLOCKED by empty upstream tables)
  ├── CSP: app/modules/csp/service.py
  │     ← requires insurer_financials (0 rows) → returns None for all 72 insurers
  │
  ├── ML: app/modules/ml/trainer.py + predictor.py
  │     ← requires financial_snapshots (0 rows) + news_articles (0 rows)
  │     → raises ValueError on predict/train
  │
  ├── Intel: app/modules/intel/gdelt.py
  │     ← requires internet GDELT fetch (not yet triggered)
  │     → intel_articles (0 rows)
  │
  └── Deviation: app/modules/deviation/clause_scorer.py
        ← requires standard_clauses (0 rows) → returns _empty_score() for all
      ↓
UI
  app/ui/router.py, analytics_router.py, extra_router.py
  ← All analytics pages render empty charts/tables
  ← Settlement Power page: empty (no csp_scores)
  ← ML dashboard: shows last trained model metadata only
  ← Advisory: falls back to "no data" recommendations
```

---

## 4. ROOT CAUSES

### RC-1: Empty `insurer_financials` table (CRITICAL — blocks CSP + ML)
- 72 insurers exist, 0 have financial records
- `insurer_financials_full.csv` has 864 rows of synthetic data at `storage/datasets/app/insurer_financials_full.csv` — never imported into DB
- `scripts/import_insurers_csv.py` exists but imports insurer metadata only, not financials

### RC-2: Empty `financial_snapshots` table (CRITICAL — blocks ML training/prediction)
- `app/modules/financials/dev_seed.py` exists (can generate 6 months × 72 insurers = 432 snapshots) but has never been triggered
- ML `predictor.py:21` immediately raises `ValueError("No financial snapshots found")` for all 72 insurers

### RC-3: `standard_clauses` table empty (HIGH — deviation scoring broken)
- `KnowledgeBaseSeeder.seed_knowledge_base()` endpoint exists at `POST /api/deviation/seed-knowledge-base` but has never been called
- Result: all `POST /api/deviation/score-document/{id}` and `POST /api/deviation/clause` calls return `{"deviation_label": "unknown", "risk_implication": "Standard clause library is empty"}`
- `clause_deviation_scores` has 2559 rows in app.db from a previous session with a populated KB that was later wiped

### RC-4: ChromaDB directory does not exist (HIGH — RAG broken)
- `VectorStore` is configured to use `./chroma_db` which is absent on this machine
- `document_chunks` = 0 rows; no documents have been RAG-indexed
- Q&A falls back to offline keyword search on raw document text, which also fails because `circular_analyses` = 0 rows (no extracted text in DB)

### RC-5: `circular_analyses` table empty (HIGH — blocks RAG, Deviation, Comparison)
- None of the 300+ source PDFs have been through the analysis pipeline
- Downstream services (`indexing_pipeline._get_document_text()`, `clause_scorer.score_document()`, `comparison_service._extract_clauses()`) all fall back and return empty/null

### RC-6: Broken `DEFAULT_SOURCES` path in `training_orchestrator.py` (MEDIUM)
- Line 24: `r"C:\Users\lenovo\Desktop\Scrapper\kb\raw"` — this path does not exist
- `POST /ml/ingest-and-train` will partially succeed (circulars path exists) but silently skip the KB documents source

### RC-7: `corpus_state.json` contains paths from old sessions (MEDIUM)
- `storage/datasets/app/corpus_state.json` contains ~400 file paths pointing to:
  - `/sessions/wonderful-affectionate-einstein/mnt/PRIMARY/EXPERIMENT/` (Docker/cloud session — broken)
  - `C:\Users\lenovo\Desktop\CAPSTONE_ARCHIVE\PRIMARY\EXPERIMENT\` (old local path — broken)
- This state file is used to track which PDFs have already been processed, causing the ingestion pipeline to skip re-ingesting valid files that are now at a different path

### RC-8: Two active databases with diverged schemas (MEDIUM)
- `app.db` (active): 30 tables — missing `document_chunks`, `queued_jobs`, `refresh_tokens`, `dead_letter_jobs`, `document_job_steps`, `retrieval_audit_log`, `user_revocation_fence`
- `insuredb.sqlite3`: 37 tables — has the newer schema
- The `.env` / config defaults to `app.db`, so the async job queue (`queued_jobs`) and RAG chunk tracking (`document_chunks`) tables are inaccessible

### RC-9: `intel_articles` / `news_articles` tables empty (MEDIUM — blocks ML fusion, advisory)
- GDELT ingest (`POST /intel/ingest`) needs an internet connection and must be explicitly triggered
- `news_articles` are from a separate scraper (`news_router.py`) that has never run
- ML predictor's `NewsFeatureEngineer` returns zero-filled vectors, silently degrading model quality

### RC-10: ZSE module removed, advisory still references it (LOW)
- `app/modules/intel/advisory_service.py:297` always passes `zse=None`
- `app/main.py:7` comment: "zse module ... not needed for thesis demo"
- The advisory engine gracefully handles `zse=None` but the radar chart and data_points will always have a static "0.3" market risk score

---

## 5. DEPENDENCY MAP

```
insurers (72 rows)
    ↓ requires
insurer_financials (0 rows) ←──── BLOCKER for CSP + ML
    ↓ required by
    ├── CSPService.score_insurer()
    │       ↓ produces
    │   csp_scores (0 rows) ←──── all CSP endpoints return empty
    │
    └── MLTrainer._build_feature_row()
            ↓ also requires
        financial_snapshots (0 rows) ←──── BLOCKER for ML
            ↓ also requires
        news_articles (0 rows) ←────────── BLOCKER for ML fusion
            ↓ produces
        model.joblib ← EXISTS (trained on synthetic CSV, not live DB)
            ↓
        MLPredictor.predict() ← FAILS (no snapshots per insurer)

source PDFs (300+ files, local disk)
    ↓ via ingestion pipeline
circular_analyses (0 rows) ←──── BLOCKER for RAG + Deviation + Comparison
    ↓ required by
    ├── indexing_pipeline._get_document_text()
    │       ↓ embeds into
    │   ChromaDB (./chroma_db MISSING) ←── BLOCKER for vector RAG
    │       ↓ required by
    │   document_chunks (0 rows)
    │       ↓ required by
    │   QAEngine (falls back to keyword search on raw text)
    │
    ├── ClauseDeviationScorer.score_document()
    │       ↓ also requires
    │   standard_clauses (0 rows) ←──── BLOCKER for deviation
    │
    └── ComparisonService._extract_clauses()

standard_clauses (0 rows) ←──── seeder never called
    ↓ required by
ClauseDeviationScorer ← returns _empty_score() for all calls
```

---

## 6. BROKEN ENDPOINTS

| Endpoint | Method | Issue | Symptom |
|----------|--------|-------|---------|
| `/analytics/settlement-power/chart-data` | GET | `csp_scores` = 0 rows | Returns empty arrays |
| `/analytics/settlement-power/lookup` | GET | `csp_scores` = 0 rows | 404 for all insurers |
| `/analytics/settlement-power/` | GET | `csp_scores` = 0 rows | Page renders empty table |
| `/internal/csp/force-refresh` | POST | `insurer_financials` = 0 | Runs but scores 0 insurers |
| `/ml/predict/{insurer_id}` | GET | `financial_snapshots` = 0 | ValueError → 400 |
| `/ml/explain/{insurer_id}` | GET | Same | ValueError → 400 |
| `/ml/fused-risk/{insurer_id}` | GET | No financial/news data | ValueError → 400 |
| `/ml/train` | POST | No DB data for training | ValueError "Not enough training rows" |
| `/ml/forecast/{insurer_id}` | GET | `financial_snapshots` = 0 | Error/empty |
| `/ml/ingest-and-train` | POST | Broken KB source path | Partial — circulars only |
| `/api/deviation/score-document/{id}` | POST | `standard_clauses` = 0 | Returns `unknown` deviation for all |
| `/api/deviation/clause` | POST | `standard_clauses` = 0 | Returns `_empty_score` |
| `/intel/articles` | GET | `intel_articles` = 0 | `{"count": 0, "items": []}` |
| `/intel/stats` | GET | `intel_articles` = 0 | All-zero stats |
| `/intel/train` | POST | No articles | "No articles found" error |
| `/intel/predict` | GET | Classifier untrained | Fallback or error |
| `/api/qa/*` | ALL | No ChromaDB, no analyzed docs | Empty/fallback responses |
| `/api/embeddings/*` | ALL | ChromaDB missing | ChromaDB init error |

---

## 7. EMPTY DATASETS

| Table | Rows | Root Cause |
|-------|------|------------|
| `insurer_financials` | 0 | CSV never imported; no scraper triggered |
| `csp_scores` | 0 | Depends on insurer_financials |
| `financial_snapshots` | 0 | dev_seed.py never triggered |
| `circular_analyses` | 0 | Analysis pipeline never run |
| `standard_clauses` | 0 | Seeder never called |
| `intel_articles` | 0 | GDELT ingest never triggered |
| `news_articles` | 0 | News scraper never run |
| `document_chunks` | 0 | ChromaDB missing; no indexing |
| `extracted_entities` | 4 | Partial — only from 6 uploaded docs |
| `processing_batches` | 0 | Batch processor not triggered |
| `qa_sessions` | 0 | Follows from empty RAG |
| `compliance_results` | 1 | Near-empty |

---

## 8. FAKE / DEMO DATA

| Item | Location | Nature |
|------|----------|--------|
| `ml_training_dataset.csv` | `storage/datasets/app/` | 1572 synthetic rows (seeded random) |
| `insurer_financials_full.csv` | `storage/datasets/app/` | 864 synthetic rows |
| `news_articles_corpus.json` | `storage/datasets/app/` | 800 synthetic articles |
| `claims_training_dataset.csv` | `storage/datasets/app/` | 1000 synthetic claims |
| `demo_settlement_model.joblib` | `storage/models/demo/` | Trained on synthetic data |
| `model.joblib` (app profile) | `storage/models/app/` | Trained on `ml_training_dataset.csv` |
| `build_summary.json` | `storage/datasets/app/` | Confirms: "seed: 42, insurer_count: 72" |
| `financials/dev_seed.py` | `app/modules/financials/` | Random financial generator (never run) |

**Key note:** The app-profile model (`storage/models/app/model.joblib`) was trained against the synthetic CSV datasets, NOT against live DB financial snapshots. Predictions would be drawn from a synthetic distribution that does not match what `MLPredictor._vector()` computes from live DB data.

---

## 9. DEAD CODE / PLACEHOLDER IMPLEMENTATIONS

| Item | File | Issue |
|------|------|-------|
| `app/modules/intel/service.py` | Does not exist | Intel router bypasses a service layer; repo/classifier called directly |
| ZSE integration | `advisory_service.py:297` | Always `zse=None`; ZSE module deleted, placeholder remains in radar chart |
| Circulars router | `main.py:7` comment | Router exists on disk (`modules/circulars/router.py`) but is **not registered** in `create_app()` |
| `compat_router.py` | `app/modules/compat_router.py` | Compatibility shim — needs investigation for unused route aliases |
| `sandbox_report_service.py` | `app/modules/reports/` | Sandbox-mode report generation |
| `multilingual_pipeline.py` | `app/ai/multilingual/` | DB table `document_language_analysis` = 0 rows |
| Kaggle fetch | `knowledge_base_seeder.py:204` | Works only if `KAGGLE_USERNAME`/`KAGGLE_KEY` set; never called |
| `corpus_state.json` | `storage/datasets/app/` | ~400 broken paths from old sessions block re-ingestion |

---

## 10. RECOMMENDED FIX ORDER

Priority 1 items unblock all downstream modules. Each tier depends on the previous.

### TIER 1 — Data Seeding (fixes ~80% of broken endpoints)

| # | Fix | File(s) | Effort |
|---|-----|---------|--------|
| 1.1 | Reset `corpus_state.json` (delete or clear `processed_paths`) | `storage/datasets/app/corpus_state.json` | 5 min |
| 1.2 | Fix broken KB source path in training_orchestrator.py | `app/modules/ml/training_orchestrator.py:24` | 5 min |
| 1.3 | Import `insurer_financials_full.csv` into `insurer_financials` table | `scripts/` — new import script needed | 1 hr |
| 1.4 | Trigger `financials/dev_seed.py` to populate `financial_snapshots` | Admin endpoint or one-time script | 30 min |
| 1.5 | Call `POST /api/deviation/seed-knowledge-base` | Already implemented, just needs to be triggered | 5 min |

### TIER 2 — Ingestion Pipeline (fixes RAG + deviation accuracy)

| # | Fix | File(s) | Effort |
|---|-----|---------|--------|
| 2.1 | Run `POST /ml/ingest-and-train` with correct sources to populate `circulars_corpus.json` and train classifier | `training_orchestrator.py` | 2 hrs (CPU) |
| 2.2 | Process uploaded documents through analysis pipeline to populate `circular_analyses` | `app/modules/documents/service.py` → analysis trigger | 1 hr |
| 2.3 | Create ChromaDB directory and run `reindex_all_documents()` for analyzed documents | `app/ai/rag/indexing_pipeline.py` | 2 hrs (embedding time) |

### TIER 3 — CSP + ML Activation (fixes analytics pages)

| # | Fix | File(s) | Effort |
|---|-----|---------|--------|
| 3.1 | Trigger `POST /internal/csp/force-refresh` after Tier 1 financials seeded | `app/api/routes/csp_routes.py` | 30 min |
| 3.2 | Retrain ML models against live DB data: `POST /ml/train?profile=demo` | `app/modules/ml/trainer.py` | 1 hr |
| 3.3 | Trigger GDELT news ingest: `POST /intel/ingest` | `app/modules/intel/gdelt.py` | 30 min (internet) |
| 3.4 | Train intel classifier: `POST /intel/train` | `app/modules/intel/classifier.py` | 30 min |

### TIER 4 — Schema & Path Fixes

| # | Fix | File(s) | Effort |
|---|-----|---------|--------|
| 4.1 | Consolidate to single DB: run Alembic migrations on `app.db` to add missing 7 tables | `alembic/versions/` | 1 hr |
| 4.2 | Or: switch `DATABASE_URL` to `insuredb.sqlite3` and verify all table counts | `.env` | 30 min |
| 4.3 | Add circulars router back to `create_app()` if circular analytics UI is needed | `app/main.py` | 15 min |
| 4.4 | Remove/stub ZSE references in advisory_service.py to clean up placeholder radar score | `advisory_service.py:213–239` | 30 min |

### TIER 5 — Structural Improvements (optional, lower urgency)

| # | Fix | File(s) | Effort |
|---|-----|---------|--------|
| 5.1 | Add `service.py` to `app/modules/intel/` and move business logic out of router | `intel/` | 2 hrs |
| 5.2 | Add IPEC FSR-1 scraper trigger for real insurer financials | `infrastructure/scrapers/ipec_fsr1_scraper.py` | 4 hrs |
| 5.3 | Build admin dashboard endpoint to show seeding status for all modules | new endpoint | 3 hrs |

---

## 11. ESTIMATED EFFORT SUMMARY

| Tier | Description | Total Effort |
|------|-------------|-------------|
| 1 | Data seeding — unblocks 80% of endpoints | ~2 hrs |
| 2 | Ingestion pipeline — activates RAG and deviation | ~5 hrs (mostly CPU/IO wait) |
| 3 | CSP + ML activation — fills analytics | ~2 hrs |
| 4 | Schema + path fixes | ~2 hrs |
| 5 | Structural improvements | ~10 hrs |
| **Total to working state** | Tiers 1–3 | **~9 hrs** |
| **Total to production-clean** | Tiers 1–5 | **~19 hrs** |

---

## 12. WHAT IS ACTUALLY WORKING

Despite the empty data, the following infrastructure is fully functional:

- Auth system: JWT, refresh tokens, RBAC, rate limiting, lockout — operational (6 users in DB)
- Document upload/store: `POST /api/documents/upload` — functional (file dedup, MIME validation)
- Insurer list: 72 insurers in DB, `/insurers` endpoints return data
- Circular classifier model: `storage/models/app/circular_classifier.joblib` — trained, loads correctly
- Settlement risk models: `storage/models/app/model.joblib` + `demo/model.joblib` — trained, on disk
- Corpus JSON: `storage/datasets/app/circulars_corpus.json` — 592 records extracted from PDFs
- Audit logging: 709 entries in app.db, middleware active
- UI templates: all pages render (with empty data)
- ChromaDB library: installed, `VectorStore` code is correct — just needs the directory to be created

---

*End of audit. No code was modified during this review.*
