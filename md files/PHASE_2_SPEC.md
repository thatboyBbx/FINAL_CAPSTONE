# InsureIntel Zimbabwe — Phase 2 Implementation Spec
## Data Pipeline · ML Scaffolding · Scraper Fix · ChromaDB Seeding · Alembic Migrations

**Codebase:** `CAPSTONE_ARCHIVE/PRIMARY/EXPERIMENT/`
**Goal:** Make every AI/ML component in the platform capable of running on real data instead of synthetic placeholders. Fix the IPEC scraper bug so financial data flows in, seed ChromaDB so the chatbot and compliance checker have actual knowledge, wire the MarianMT model download so Shona translation works, and establish a proper Alembic migration history. The UI does not change in this phase — that is Phase 3.
**Derived from:** InsureIntel Project Audit Report (May 2026) — Audit Phase 3 tasks + BUG 4 + BUG 5 + BUG 7
**NOT ALLOWED:** Placeholders, stubs, TODOs, or synthetic-only data paths left untouched. Every component you touch must be fully functional after this phase.

---

## 0. GROUND RULES FOR CLAUDE CODE

- Work exclusively inside `CAPSTONE_ARCHIVE/PRIMARY/EXPERIMENT/`
- After every major step, verify `python -c "from app.main import app; print('OK')"` succeeds
- After every major step, run `python -m pytest tests/ -q --tb=short` — do not proceed if tests break
- Never modify a file without understanding what imports it first
- All new Python code must use Python 3.11+ type hints (`str | None` not `Optional[str]`)
- All new SQLAlchemy models use `Mapped[]` and `mapped_column()` syntax
- All new Pydantic schemas use `model_config = ConfigDict(...)` style
- Clear inline comments on every function and class you write or modify
- This phase is entirely backend and data — do NOT touch `app/ui/templates/` or `app/ui/static/`

---

## 1. FIX IPEC FSR-1 SCRAPER (BUG 4 — P0)

**File:** `app/infrastructure/scrapers/ipec_fsr1_scraper.py`

**The bug:** The recursive crawl has no depth limit and no URL pattern filter. It returns 374 directories instead of the ~12 quarterly FSR-1 PDF links that actually exist on the IPEC download centre. As a result, `run_ipec_fsr1_scraper()` never ingests any real financial data, so the financials table is empty and CSP scores run on synthetic values only.

**What you must do:**

### 1.1 Read the current scraper first
Open `app/infrastructure/scrapers/ipec_fsr1_scraper.py` and understand the full crawl logic before changing anything.

### 1.2 Apply these exact fixes

**Fix A — Add max_depth parameter to the recursive crawl function:**

The crawl function (whatever it is named — `_crawl`, `crawl_directory`, `_recurse`, etc.) must accept a `depth: int` parameter. Add a guard at the top:
```python
# Guard: stop recursing beyond max depth to prevent runaway crawls
if depth >= max_depth:
    return []
```
The default `max_depth` must be `2`. Pass it through all recursive calls as `depth + 1`.

**Fix B — Add PDF-only URL filtering:**

Before adding any URL to the results list, it must pass this filter:
```python
def _is_fsr1_pdf_url(url: str) -> bool:
    """
    Return True only if the URL points to an FSR-1 quarterly report PDF.
    IPEC FSR-1 files follow the pattern: FSR*.pdf or Financial*Soundness*.pdf
    We also accept any .pdf file found within a path containing 'fsr' or 'financial-soundness'.
    """
    url_lower = url.lower()
    # Must end in .pdf
    if not url_lower.endswith(".pdf"):
        return False
    # Must be in an FSR-related path OR have FSR in the filename
    fsr_signals = ["fsr", "financial-soundness", "financial_soundness", "quarterly-report"]
    return any(signal in url_lower for signal in fsr_signals)
```

**Fix C — Add retry logic with exponential backoff:**

The scraper must not crash the application if IPEC's server is slow or temporarily unavailable. Wrap the HTTP request in a retry loop:
```python
import time

def _fetch_with_retry(url: str, session: requests.Session, max_retries: int = 3) -> requests.Response | None:
    """Fetch a URL with exponential backoff. Returns None if all retries fail."""
    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=15)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            wait_seconds = 2 ** attempt  # 1s, 2s, 4s
            logger.warning(
                f"IPEC scraper fetch attempt {attempt + 1}/{max_retries} failed for {url}: {e}. "
                f"Retrying in {wait_seconds}s..."
            )
            time.sleep(wait_seconds)
    logger.error(f"IPEC scraper: all {max_retries} retries exhausted for {url}")
    return None
```

**Fix D — Add a dry-run mode for testing:**

Add a `dry_run: bool = False` parameter to the main scraper entry point function. When `dry_run=True`, the scraper logs what it would download but does not write to the database or disk. This lets you verify the fix worked without polluting the database.

### 1.3 Write a unit test for the scraper fix

In `tests/`, create `test_ipec_scraper.py`:

```python
"""
Tests for the IPEC FSR-1 scraper depth and URL filter fixes.
Uses mocked HTTP responses — no real network calls.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.infrastructure.scrapers.ipec_fsr1_scraper import _is_fsr1_pdf_url, IPECScraperConfig

class TestFSR1URLFilter:
    """Verify that only valid FSR-1 PDF URLs pass the filter."""

    def test_accepts_fsr_pdf(self) -> None:
        assert _is_fsr1_pdf_url("https://www.ipec.co.zw/download-centre/fsr/FSR-Q3-2024.pdf") is True

    def test_accepts_financial_soundness_pdf(self) -> None:
        assert _is_fsr1_pdf_url("https://www.ipec.co.zw/financial-soundness-report-2023.pdf") is True

    def test_rejects_non_pdf(self) -> None:
        assert _is_fsr1_pdf_url("https://www.ipec.co.zw/download-centre/fsr/") is False

    def test_rejects_unrelated_pdf(self) -> None:
        assert _is_fsr1_pdf_url("https://www.ipec.co.zw/circulars/circular-2024.pdf") is False

    def test_rejects_image(self) -> None:
        assert _is_fsr1_pdf_url("https://www.ipec.co.zw/images/logo.png") is False


class TestScraperMaxDepth:
    """Verify depth limiting prevents runaway crawls."""

    def test_scraper_config_has_max_depth(self) -> None:
        # IPECScraperConfig (or equivalent) must expose max_depth
        config = IPECScraperConfig()
        assert hasattr(config, "max_depth"), "IPECScraperConfig must have a max_depth attribute"
        assert config.max_depth == 2, "Default max_depth must be 2"
```

If `IPECScraperConfig` does not exist yet, create it as a simple dataclass in the scraper file:
```python
from dataclasses import dataclass, field

@dataclass
class IPECScraperConfig:
    """Configuration for the IPEC FSR-1 scraper."""
    base_url: str = "https://www.ipec.co.zw/download-centre"
    max_depth: int = 2        # Maximum directory recursion depth
    request_timeout: int = 15  # Seconds before a single request times out
    max_retries: int = 3       # Number of retry attempts per URL
    dry_run: bool = False       # If True, log actions but do not write to DB
```

---

## 2. SEED CHROMADB — KNOWLEDGE BASE (BUG 7 — P0)

**File:** `app/modules/deviation/knowledge_base_seeder.py` (moved here in Phase 1)
**ChromaDB collection:** used by `app/ai/rag/` — the chatbot and compliance checker

**The bug:** ChromaDB is empty. The seeder script exists but has never been run against real documents. The RAG chatbot returns empty or hallucinated answers. The compliance checker has no regulatory text to match against.

### 2.1 Audit the existing seeder

Read `app/modules/deviation/knowledge_base_seeder.py` fully. Understand:
- What input format does it expect? (PDF file paths, plain text, or pre-chunked strings?)
- What ChromaDB collection does it write to?
- What embedding model does it use? (should be `all-MiniLM-L6-v2` from SentenceTransformer)

Do NOT rewrite the seeder if it is already structurally correct. Only fix what is broken.

### 2.2 Create a seeder CLI script

Create `scripts/seed_knowledge_base.py` — a standalone runnable script (not a FastAPI route) that:

1. Accepts a `--source-dir` argument pointing to a directory of PDF files
2. Accepts a `--collection` argument (default: `"insurance_knowledge"`)
3. Accepts a `--dry-run` flag that prints what would be ingested without writing to ChromaDB
4. For each PDF in the source directory:
   - Extracts text using `pdfplumber` (already in requirements)
   - Chunks the text into ~500-token overlapping windows (overlap: 50 tokens)
   - Embeds each chunk using the SentenceTransformer model already used in the project
   - Upserts into ChromaDB with metadata: `{source_file, chunk_index, doc_type}`
5. Prints a completion summary: files processed, chunks embedded, errors

Full script signature:
```python
#!/usr/bin/env python3
"""
scripts/seed_knowledge_base.py

CLI tool to seed InsureIntel's ChromaDB knowledge base from a directory of PDF files.

Usage:
    python scripts/seed_knowledge_base.py --source-dir ./knowledge_pdfs/
    python scripts/seed_knowledge_base.py --source-dir ./knowledge_pdfs/ --dry-run
    python scripts/seed_knowledge_base.py --source-dir ./knowledge_pdfs/ --collection custom_collection

The source directory should contain:
    - Insurance Act Chapter 24:07 (PDF)
    - IPEC regulations and circulars (PDFs)
    - Standard insurance policy templates (PDFs)
    Any other PDF is also accepted and will be chunked and embedded.
"""
import argparse
import sys
from pathlib import Path
# ... full implementation below
```

Write the FULL implementation. No stubs. Every function must be complete with inline comments and type hints.

### 2.3 Create a seeder README

Create `knowledge_pdfs/README.md` (create the `knowledge_pdfs/` directory if it does not exist):

```markdown
# InsureIntel Zimbabwe — Knowledge Base Source Documents

Place PDF files here before running the knowledge base seeder.

## Required Documents

| Document | Source | Priority |
|----------|--------|----------|
| Insurance Act Chapter 24:07 | Government of Zimbabwe website / Zimbabwe Laws Online | P0 — Critical |
| IPEC Guidance Notes | ipec.co.zw/download-centre | P0 — Critical |
| IPEC Circulars (2020–present) | ipec.co.zw/download-centre | P1 |
| Standard Motor Policy Wording | Any licensed Zimbabwean insurer | P1 |
| Standard Fire Policy Wording | Any licensed Zimbabwean insurer | P1 |
| Reinsurance Treaty Template | Broker association / ICZ | P2 |

## Running the Seeder

After placing PDFs here, run:
    python scripts/seed_knowledge_base.py --source-dir ./knowledge_pdfs/

For a dry run (no writes, just verify):
    python scripts/seed_knowledge_base.py --source-dir ./knowledge_pdfs/ --dry-run

## File Naming Convention

Name files descriptively — the filename becomes part of the ChromaDB metadata:
    insurance_act_chapter_24_07.pdf
    ipec_guidance_note_life_2023.pdf
    standard_motor_policy_wording.pdf

## Notes

This directory is in .gitignore — PDF files are NOT committed to the repository.
Only this README is tracked.
```

Add `knowledge_pdfs/*.pdf` to `.gitignore` (keep the directory, ignore the PDFs).

### 2.4 Write a test for the seeder

In `tests/`, create `test_knowledge_base_seeder.py`:

```python
"""
Tests for the knowledge base seeder.
Uses a temporary ChromaDB in-memory client — no real ChromaDB connection needed.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

class TestSeederChunking:
    """Verify text chunking logic produces correct chunk sizes and overlaps."""

    def test_chunk_size_is_respected(self) -> None:
        """Chunks must not exceed ~500 tokens (approx 2000 chars)."""
        from scripts.seed_knowledge_base import chunk_text
        long_text = "word " * 2000  # 2000 words
        chunks = chunk_text(long_text, chunk_size=500, overlap=50)
        for chunk in chunks:
            word_count = len(chunk.split())
            assert word_count <= 550, f"Chunk exceeded size limit: {word_count} words"

    def test_overlap_produces_continuity(self) -> None:
        """Adjacent chunks must share overlapping tokens."""
        from scripts.seed_knowledge_base import chunk_text
        text = " ".join([f"word{i}" for i in range(200)])
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) >= 2, "Should produce multiple chunks"
        # The last 20 tokens of chunk 0 should appear at the start of chunk 1
        chunk0_tail = chunks[0].split()[-20:]
        chunk1_head = chunks[1].split()[:20]
        assert chunk0_tail == chunk1_head, "Overlap tokens must match between adjacent chunks"

    def test_empty_text_returns_empty_list(self) -> None:
        from scripts.seed_knowledge_base import chunk_text
        assert chunk_text("", chunk_size=500, overlap=50) == []

    def test_short_text_returns_single_chunk(self) -> None:
        from scripts.seed_knowledge_base import chunk_text
        text = "This is a short clause."
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) == 1
```

---

## 3. MARIANMT MODEL — DOWNLOAD + VERIFICATION (P2)

**File:** `app/ai/multilingual/multilingual_pipeline.py`

**The problem:** The multilingual pipeline file exists but the MarianMT model has never been downloaded and verified. When `POST /api/multilingual/translate` is called, it either crashes with a missing model error or returns an empty response.

### 3.1 Create a model download script

Create `scripts/download_ml_models.py` — a standalone script that downloads and caches all ML models the platform needs, run once during initial setup:

```python
#!/usr/bin/env python3
"""
scripts/download_ml_models.py

Downloads and caches all ML models required by InsureIntel Zimbabwe.
Run this script ONCE after initial setup, before starting the application.

Models downloaded:
    1. SentenceTransformer: all-MiniLM-L6-v2 (embeddings for RAG + ChromaDB)
    2. MarianMT: Helsinki-NLP/opus-mt-en-sn (English → Shona translation)
    3. spaCy: en_core_web_sm (base English NLP model for NER pipeline)

Usage:
    python scripts/download_ml_models.py
    python scripts/download_ml_models.py --skip-marian   # skip MarianMT if HF is slow
    python scripts/download_ml_models.py --verify-only   # check already-downloaded models
"""
import argparse
import sys
# ... full implementation
```

Full implementation must:

1. Download `sentence-transformers/all-MiniLM-L6-v2` via `SentenceTransformer("all-MiniLM-L6-v2")` — the library caches it automatically. Verify by running a test embedding.

2. Download MarianMT `Helsinki-NLP/opus-mt-en-sn` via:
   ```python
   from transformers import MarianMTModel, MarianTokenizer
   model_name = "Helsinki-NLP/opus-mt-en-sn"
   tokenizer = MarianTokenizer.from_pretrained(model_name)
   model = MarianMTModel.from_pretrained(model_name)
   ```
   Verify by translating the test phrase `"insurance policy"` → Shona. The output does not need to be perfect (the model is imperfect on low-resource languages), but the call must not raise an exception.

3. Download spaCy model via subprocess:
   ```python
   import subprocess
   result = subprocess.run(
       [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
       capture_output=True, text=True
   )
   ```

4. Print a clear pass/fail summary for each model at the end.

### 3.2 Fix the multilingual pipeline to handle model absence gracefully

Read `app/ai/multilingual/multilingual_pipeline.py`. The translate function must NOT raise an unhandled exception if the MarianMT model is not downloaded yet. It must return a structured error response:

```python
class TranslationResult:
    """Result of a translation attempt."""
    text: str                   # Translated text, or empty string if failed
    source_lang: str            # Input language code
    target_lang: str            # Output language code
    success: bool               # True if translation succeeded
    error: str | None           # Error message if success is False
    model_available: bool       # False if the model file is missing entirely
```

The router endpoint (`app/modules/multilingual/router.py`) must catch `TranslationResult.success == False` and return HTTP 503 with `{"detail": "Translation service unavailable — model not downloaded. Run scripts/download_ml_models.py"}` instead of a 500 crash.

### 3.3 Write a test for the translation pipeline

In `tests/`, create `test_multilingual_pipeline.py`:

```python
"""
Tests for the multilingual translation pipeline.
Uses a mocked MarianMT model — no real model download needed for tests.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.ai.multilingual.multilingual_pipeline import translate_text, TranslationResult

class TestTranslationPipeline:

    def test_returns_translation_result_type(self) -> None:
        """translate_text must always return a TranslationResult, never raise."""
        with patch("app.ai.multilingual.multilingual_pipeline.MarianMTModel") as mock_model:
            mock_model.from_pretrained.return_value = MagicMock()
            result = translate_text("test insurance clause", source_lang="en", target_lang="sn")
        assert isinstance(result, TranslationResult)

    def test_returns_graceful_error_when_model_missing(self) -> None:
        """If the model file is absent, success must be False and model_available False."""
        with patch(
            "app.ai.multilingual.multilingual_pipeline.MarianMTModel.from_pretrained",
            side_effect=OSError("model files not found")
        ):
            result = translate_text("test", source_lang="en", target_lang="sn")
        assert result.success is False
        assert result.model_available is False
        assert result.text == ""

    def test_empty_input_returns_empty_output(self) -> None:
        """Empty input string should return empty translation without crashing."""
        with patch("app.ai.multilingual.multilingual_pipeline.MarianMTModel") as mock_model:
            mock_instance = MagicMock()
            mock_instance.generate.return_value = [[]]
            mock_model.from_pretrained.return_value = mock_instance
            result = translate_text("", source_lang="en", target_lang="sn")
        assert result.text == "" or result.success is True
```

---

## 4. ALEMBIC — INCREMENTAL MIGRATIONS (BUG 5 — P1)

**The bug:** The entire database schema (27 tables) lives in a single Alembic baseline migration. You cannot roll back individual features. The migration history is not defensible in a dissertation context — a supervisor can rightfully ask "how did this schema evolve and why?"

### 4.1 Understand the current state

Run:
```bash
alembic history
alembic current
```
Document what exists. There should be exactly one revision covering all 27 tables.

### 4.2 Create feature-level migrations for Phase 1 additions

Phase 1 created three new modules: `clients`, `csp`, and `compliance`. Each needs its own Alembic migration file.

For each new module, run:
```bash
alembic revision --autogenerate -m "feat: add <module_name> module tables"
```

Then VERIFY the generated migration file is correct before applying it:
- Open the generated file in `alembic/versions/`
- Check that `upgrade()` contains `op.create_table(...)` for the new tables
- Check that `downgrade()` contains `op.drop_table(...)` in reverse order
- If autogenerate missed anything (it sometimes does with complex relationships), add the missing operations manually

Apply them:
```bash
alembic upgrade head
```

The three migrations to create are:

**Migration 1:** `feat: add clients module — client table`
- Table: `clients` (from `app/modules/clients/model.py`)

**Migration 2:** `feat: add csp module — csp_score table`
- Table: `csp_scores` (from `app/modules/csp/model.py`)

**Migration 3:** `feat: add compliance module — compliance_result table`
- Table: `compliance_results` (from `app/modules/compliance/model.py` — if this model does not exist yet, create it now, see below)

### 4.3 Create compliance model if missing

If `app/modules/compliance/model.py` does not have a proper SQLAlchemy model yet (it may only have a service), create it:

```python
"""
app/modules/compliance/model.py

SQLAlchemy model for storing compliance check results.
Each document gets one compliance_results row per check run.
"""
from datetime import datetime
from sqlalchemy import ForeignKey, Text, Float, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base  # use whatever Base import path is canonical in this project


class ComplianceResult(Base):
    """Stores the output of a compliance check run against a document."""
    __tablename__ = "compliance_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Overall compliance score 0.0–100.0
    compliance_score: Mapped[float] = mapped_column(Float, nullable=False)

    # JSON-serialised dict of individual clause checks: {"clause_name": true/false, ...}
    clause_results: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSON-serialised list of prohibited terms found: ["term1", "term2"]
    prohibited_terms_found: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSON-serialised list of missing mandatory clauses
    missing_mandatory_clauses: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Whether the document passes the minimum compliance threshold (score >= 70)
    passes_minimum: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Human-readable summary generated by the compliance checker
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Use whatever `Base` import is already canonical in the project (check other models to confirm the import path before writing it).

### 4.4 Verify migration history is clean

After all three migrations are applied:

```bash
# Must show at least 4 revisions: baseline + 3 feature migrations
alembic history --verbose

# Must show 'head' — no pending migrations
alembic current

# Must return no error
alembic check
```

### 4.5 Write a test for migrations

In `tests/`, create `test_alembic_migrations.py`:

```python
"""
Tests that Alembic migrations are in a consistent state.
These tests do not apply migrations — they verify the migration files exist and are valid.
"""
import pytest
from pathlib import Path

class TestAlembicMigrationState:

    def test_at_least_four_migration_files_exist(self) -> None:
        """There must be at least 4 migration files: baseline + 3 Phase 1 feature migrations."""
        versions_dir = Path("alembic/versions")
        migration_files = list(versions_dir.glob("*.py"))
        # Filter out __init__.py and README files
        real_migrations = [f for f in migration_files if not f.name.startswith("_")]
        assert len(real_migrations) >= 4, (
            f"Expected >= 4 migration files, found {len(real_migrations)}. "
            f"Create feature migrations for clients, csp, compliance modules."
        )

    def test_clients_migration_exists(self) -> None:
        """There must be a migration file mentioning the clients module."""
        versions_dir = Path("alembic/versions")
        content = " ".join(f.read_text() for f in versions_dir.glob("*.py"))
        assert "clients" in content.lower(), "No migration found for the clients module"

    def test_csp_migration_exists(self) -> None:
        """There must be a migration file mentioning the csp module."""
        versions_dir = Path("alembic/versions")
        content = " ".join(f.read_text() for f in versions_dir.glob("*.py"))
        assert "csp" in content.lower(), "No migration found for the csp module"

    def test_compliance_migration_exists(self) -> None:
        """There must be a migration file mentioning the compliance module."""
        versions_dir = Path("alembic/versions")
        content = " ".join(f.read_text() for f in versions_dir.glob("*.py"))
        assert "compliance" in content.lower(), "No migration found for the compliance module"
```

---

## 5. NER PIPELINE — WIRE ENTITY EXTRACTION TO DOCUMENTS MODULE (P1)

**The problem:** The audit notes that `app/ai/nlp/` should contain the NER pipeline but the target architecture diagram shows it as `NEEDED` (italic green in the audit). The NER entity extraction that the documents module calls must have a clear, tested path from document text → extracted entities → stored in the `extracted_entities` table.

### 5.1 Verify the current NER pipeline location

Run:
```bash
find app/ -name "ner_pipeline.py" -o -name "entity_extractor.py" | grep -v __pycache__
find app/ -name "entity_extraction*" | grep -v __pycache__
```

Document what you find. The file may be in `app/services/entity_extraction_service.py` (moved to a module in Phase 1) or in `app/modules/documents/`.

### 5.2 Create app/ai/nlp/ if it does not exist

If `app/ai/nlp/` does not exist:
```bash
mkdir -p app/ai/nlp/
touch app/ai/nlp/__init__.py
```

Create `app/ai/nlp/ner_pipeline.py` with a full NER pipeline that:
- Accepts a plain text string
- Uses the spaCy model (`en_core_web_sm` as base, extended with insurance-specific patterns)
- Returns a list of `ExtractedEntity` objects

```python
"""
app/ai/nlp/ner_pipeline.py

Named Entity Recognition pipeline for insurance documents.
Uses spaCy as the base NLP engine with custom EntityRuler patterns
for insurance-specific entities that the base model does not recognise.

Entity types extracted:
    INSURER         — name of an insurance company
    POLICY_NUMBER   — alphanumeric policy reference
    COVERAGE_LIMIT  — monetary coverage amounts (e.g. "USD 500,000")
    PREMIUM         — premium amounts and payment terms
    DEDUCTIBLE      — deductible amounts and conditions
    POLICY_PERIOD   — policy start/end dates
    EXCLUSION       — flagged exclusionary phrases
    CLAUSE_REF      — clause numbers (e.g. "Clause 4.1", "Section 7")
"""
from dataclasses import dataclass
from typing import NamedTuple
import spacy
from spacy.language import Language
# ... full implementation
```

The pipeline must handle the case where spaCy's `en_core_web_sm` is not installed — catch `OSError` and return an empty list with a logged warning, never crash.

### 5.3 Wire entity extraction to the documents service

In `app/modules/documents/service.py`, after a document is processed (text extracted), the NER pipeline must be called and results stored in the `extracted_entities` table. Verify this call exists. If it does not, add it.

The call pattern must be:
```python
from app.ai.nlp.ner_pipeline import run_ner_pipeline, ExtractedEntity

entities: list[ExtractedEntity] = run_ner_pipeline(document_text)
# Then persist each entity to the extracted_entities table via the repo
```

---

## 6. VERIFICATION CHECKLIST

After completing all steps, run these checks in order:

```bash
# 1. App imports cleanly
python -c "from app.main import app; print('✅ App imports OK')"

# 2. All tests pass (should be 72+ now, up from 68 — new tests added in this phase)
python -m pytest tests/ -q --tb=short

# 3. New test files exist
ls tests/test_ipec_scraper.py
ls tests/test_knowledge_base_seeder.py
ls tests/test_multilingual_pipeline.py
ls tests/test_alembic_migrations.py

# 4. Scripts directory has the new tools
ls scripts/seed_knowledge_base.py
ls scripts/download_ml_models.py

# 5. knowledge_pdfs directory exists with README
ls knowledge_pdfs/README.md

# 6. Alembic is at head with feature migrations
alembic history --verbose
alembic current

# 7. IPEC scraper has max_depth and URL filter
grep -n "max_depth\|_is_fsr1_pdf_url\|IPECScraperConfig" app/infrastructure/scrapers/ipec_fsr1_scraper.py

# 8. ChromaDB seeder script is runnable (dry run)
python scripts/seed_knowledge_base.py --source-dir ./knowledge_pdfs/ --dry-run

# 9. ML model download script is runnable (verify mode)
python scripts/download_ml_models.py --verify-only

# 10. No stale imports from deleted Phase 1 directories remain
grep -rn "from app\.ml\.\|from app\.rag\.\|from app\.multilingual\.\|from app\.scrapers\." app/ --include="*.py" | grep -v __pycache__
# Expected: zero results
```

---

## 7. GIT COMMIT

```bash
git add .
git commit -m "feat: Phase 2 — data pipeline + ML scaffolding + migrations

- Fixed IPEC FSR-1 scraper: max_depth=2, PDF-only URL filter, retry backoff
- Added IPECScraperConfig dataclass with dry_run support
- Created scripts/seed_knowledge_base.py — seeds ChromaDB from PDF directory
- Created knowledge_pdfs/README.md — documents required source PDFs
- Created scripts/download_ml_models.py — downloads all 3 ML models
- Fixed MarianMT pipeline: graceful TranslationResult on model-absent
- Multilingual router now returns HTTP 503 (not 500) when model missing
- Created ComplianceResult SQLAlchemy model in app/modules/compliance/
- Added 3 Alembic feature migrations: clients, csp, compliance modules
- Created app/ai/nlp/ner_pipeline.py with InsuranceEntityRuler patterns
- Wired NER pipeline to documents/service.py entity persistence
- Added 4 new test modules: scraper, seeder, multilingual, alembic
- All $(python -m pytest tests/ -q --tb=short | tail -1) tests passing"
```

---

## IMPORTANT NOTES

- **You cannot run the actual IPEC scraper in this phase** because the IPEC website requires a live internet connection that may not be available in the development environment. Fix the code; the human will run it manually to ingest real data.
- **The knowledge_pdfs/ directory will be empty** when you create it — you are creating the tooling and the instructions, not the PDFs themselves. The human must obtain the Insurance Act and IPEC documents separately and place them there before running the seeder.
- **MarianMT model download requires ~300MB** — the download script must print a clear size warning before attempting it so the human is not surprised.
- **Do NOT delete or modify the existing synthetic data generators** — they are still needed for tests and for running the platform before real data is available.
- **The NER pipeline section (Step 5) only applies if the wiring does not already exist** — verify before writing. If entity extraction is already called from the documents service, document that it is already wired and skip creating a duplicate.
- **`app/modules/compliance/model.py`** — check whether it already exists from Phase 1 before creating it in Step 4.3. If it exists, only add what is missing.
