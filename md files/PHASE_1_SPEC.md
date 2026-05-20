# InsureIntel Zimbabwe — Phase 1 Implementation Spec
## Structural Cleanup · Modular Monolith · Security Fixes · GitHub Init

**Codebase:** `CAPSTONE_ARCHIVE/PRIMARY/EXPERIMENT/`
**Goal:** Transform the current messy-but-functional codebase into a clean modular monolith
**Derived from:** InsureIntel Project Audit Report (May 2026)
**NOT ALLOWED:** Placeholders, stubs, or TODOs — every change must be complete and the app must still start after each step

---

## 0. GROUND RULES FOR CLAUDE CODE

- Work exclusively inside `CAPSTONE_ARCHIVE/PRIMARY/EXPERIMENT/`
- After every major step, verify `python -m pytest tests/ -q` still passes (68 tests)
- After structural changes, verify `python -c "from app.main import app; print('OK')"` succeeds
- Never delete a file without first checking what imports it — update those imports first
- Never rename a module path without a global find-and-replace of all `from app.X` imports pointing to it
- Preserve all existing business logic — this is a structural migration, not a rewrite
- The `.env` file already exists — do NOT overwrite it
- `__pycache__` directories can be deleted freely — they regenerate automatically

---

## 1. SECURITY FIXES (Phase 1 from Audit Report)

### 1.1 Fix SECRET_KEY in .env
**File:** `.env`

The current `.env` has:
```
SECRET_KEY=your-very-long-random-secret-key
```
This is a placeholder string. Replace it with a real 64-character hex key:
```
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
```
Run that Python command, capture the output, and write it into `.env` as `SECRET_KEY=<output>`.

**`app/core/config.py` is already correct** — it reads `SECRET_KEY` from `.env` and blocks startup in production if the dev fallback is used. No changes needed there.

### 1.2 Verify RBAC is enforced on all routers
From live grep of the codebase, ALL active routers already have `dependencies=[Depends(get_current_user)]`:
- `modules/audit/router.py` ✅
- `modules/batch/router.py` ✅
- `modules/chatbot/router.py` ✅
- `modules/comparison/router.py` ✅
- `modules/deviation/router.py` ✅
- `modules/documents/router.py` ✅
- `modules/feedback/router.py` ✅
- `modules/financials/router.py` ✅
- `modules/insurers/router.py` ✅
- `modules/intel/router.py` ✅
- `modules/intel/settlement_router.py` ✅
- `modules/ml/router.py` ✅
- `modules/multilingual/router.py` ✅
- `modules/news/router.py` ✅
- `modules/qa/router.py` ✅
- `modules/reports/router.py` ✅
- `modules/tracker/router.py` ✅
- `modules/users/client_router.py` ✅
- `api/routes/csp_routes.py` ✅
- `modules/compat_router.py` ✅

**Action required:** Add `dependencies=[Depends(get_current_user)]` to any router in `modules/` that is missing it. Verify by running:
```
grep -rn "APIRouter(" app/modules/ app/api/ --include="*.py" | grep -v "get_current_user\|auth\|__pycache__"
```
If any result shows a router definition without the dependency, add it.

---

## 2. IMMEDIATE JUNK REMOVAL (5 minutes of work)

Delete the following files/directories — no imports reference them:

```bash
# Temp scratch files from old Claude Code sessions
rm CAPSTONE_ARCHIVE/PRIMARY/EXPERIMENT/zip_dash.txt
rm CAPSTONE_ARCHIVE/PRIMARY/EXPERIMENT/zip_router.txt
rm CAPSTONE_ARCHIVE/PRIMARY/EXPERIMENT/zip_svc.txt

# Duplicate stitch mockup folder (stitch/ is the canonical copy)
rm -rf CAPSTONE_ARCHIVE/PRIMARY/EXPERIMENT/stitch_extracted/

# Test image accidentally uploaded — not an insurance document
# Check first: find storage/documents/ -name "Monaco*"
# If found, delete it
find CAPSTONE_ARCHIVE/PRIMARY/EXPERIMENT/storage/ -name "Monaco*" -delete

# Empty domain stubs — only contain __init__.py, nothing imports them
rm -rf CAPSTONE_ARCHIVE/PRIMARY/EXPERIMENT/app/domains/
```

---

## 3. DUPLICATE DIRECTORY REMOVAL (High Priority — Import Risk)

These are the 4 directories that are **full duplicates** of canonical locations in `app/ai/` and `app/infrastructure/`. Imports from these must be migrated to their canonical paths before deletion.

### Step-by-step for each:

---

### 3.1 Delete `app/ml/` → canonical is `app/ai/inference/` + `app/ai/training/`

**Files in `app/ml/`:**
- `csp_nlg.py` → canonical: `app/ai/inference/csp_nlg.py`
- `csp_normalizer.py` → canonical: `app/ai/inference/csp_normalizer.py`  
- `csp_training_pipeline.py` → canonical: `app/ai/training/csp_training_pipeline.py`
- `csp_wcs_scorer.py` → canonical: `app/ai/inference/csp_wcs_scorer.py`
- `csp_xgboost_model.py` → canonical: `app/ai/inference/csp_xgboost_model.py`

**Action:**
1. Find all files importing from `app.ml.*`:
   ```
   grep -rn "from app\.ml\." app/ --include="*.py" | grep -v __pycache__
   ```
2. For each found import, update it to the canonical `app.ai.inference.*` or `app.ai.training.*` path
3. Delete `app/ml/` entirely

---

### 3.2 Delete `app/rag/` → canonical is `app/ai/rag/`

**Files in `app/rag/`:**
- `indexing_pipeline.py` → canonical: `app/ai/rag/indexing_pipeline.py`
- `qa_engine.py` → canonical: `app/ai/rag/qa_engine.py`
- `vector_store.py` → canonical: `app/ai/rag/vector_store.py`

**Action:**
1. Find all imports from `app.rag.*`:
   ```
   grep -rn "from app\.rag\." app/ --include="*.py" | grep -v __pycache__
   ```
   Known import: `app/modules/compat_router.py` imports `from app.rag.qa_engine import QAEngine`
2. Update all found imports to `app.ai.rag.*`
3. Delete `app/rag/`

---

### 3.3 Delete `app/multilingual/` → canonical is `app/ai/multilingual/`

**Files in `app/multilingual/`:**
- `language_detector.py` → canonical: `app/ai/multilingual/language_detector.py`
- `multilingual_pipeline.py` → canonical: `app/ai/multilingual/multilingual_pipeline.py`

**Action:**
1. Find all imports from `app.multilingual.*`:
   ```
   grep -rn "from app\.multilingual\." app/ --include="*.py" | grep -v __pycache__
   ```
2. Update all found imports to `app.ai.multilingual.*`
3. Delete `app/multilingual/`

---

### 3.4 Delete `app/scrapers/` → canonical is `app/infrastructure/scrapers/`

**Files in `app/scrapers/`:**
- `base_scraper.py`, `ipec_fsr1_scraper.py`, `ipec_scraper.py`, `news_scraper.py`, `scraper_scheduler.py`, `scraper_utils.py`
- All have canonical equivalents in `app/infrastructure/scrapers/`

**Action:**
1. Find all imports from `app.scrapers.*`:
   ```
   grep -rn "from app\.scrapers\." app/ --include="*.py" | grep -v __pycache__
   ```
2. Update all found imports to `app.infrastructure.scrapers.*`
3. Delete `app/scrapers/`

---

## 4. MERGE SPLIT-IDENTITY MODULES

These 5 modules have their service logic in a top-level directory but their model/router in `app/modules/`. Move the service files INTO the module.

### 4.1 Merge `app/comparison/` → `app/modules/comparison/`

**Files to move:**
- `app/comparison/clause_aligner.py` → `app/modules/comparison/clause_aligner.py`
- `app/comparison/comparison_service.py` → `app/modules/comparison/service.py`
- `app/comparison/delta_reporter.py` → `app/modules/comparison/delta_reporter.py`

**Action:**
1. Move the 3 files (rename `comparison_service.py` to `service.py`)
2. Find all imports from `app.comparison.*` and update to `app.modules.comparison.*`
   - Known: `app/modules/compat_router.py` imports `from app.comparison.comparison_service import ComparisonService`
   - Update to: `from app.modules.comparison.service import ComparisonService`
3. Update any internal imports within the moved files themselves
4. Delete `app/comparison/`

---

### 4.2 Merge `app/deviation/` → `app/modules/deviation/`

**Files to move:**
- `app/deviation/clause_scorer.py` → `app/modules/deviation/clause_scorer.py`
- `app/deviation/knowledge_base_seeder.py` → `app/modules/deviation/knowledge_base_seeder.py`

**Action:**
1. Move both files
2. Find all imports from `app.deviation.*` and update to `app.modules.deviation.*`
   - Known: `app/modules/compat_router.py` imports `from app.deviation.clause_scorer import get_clause_scorer`
   - Update to: `from app.modules.deviation.clause_scorer import get_clause_scorer`
3. Delete `app/deviation/`

---

### 4.3 Merge `app/feedback/` → `app/modules/feedback/`

**Files to move:**
- `app/feedback/feedback_store.py` → `app/modules/feedback/feedback_store.py`
- `app/feedback/retraining_pipeline.py` → `app/modules/feedback/retraining_pipeline.py`

**Action:**
1. Move both files
2. Find all imports from `app.feedback.*` and update to `app.modules.feedback.*`
3. Delete `app/feedback/`

---

### 4.4 Merge `app/tracker/` → `app/modules/tracker/`

**Files to move:**
- `app/tracker/policy_tracker_service.py` → `app/modules/tracker/service.py`

**Action:**
1. Move file (rename to `service.py`)
2. Find all imports from `app.tracker.*` and update to `app.modules.tracker.*`
3. Delete `app/tracker/`

---

### 4.5 Merge `app/audit/` → `app/modules/audit/`

**Files to move:**
- `app/audit/audit_logger.py` → `app/modules/audit/audit_logger.py`
- `app/audit/audit_middleware.py` → `app/modules/audit/audit_middleware.py`

**Action:**
1. Move both files
2. Find all imports from `app.audit.*` and update to `app.modules.audit.*`
   - Known: `app/main.py` imports `from app.audit.audit_middleware import AuditMiddleware`
   - Update to: `from app.modules.audit.audit_middleware import AuditMiddleware`
3. Delete `app/audit/`

---

## 5. FLOATING MODELS — Migrate `app/models/` into Modules

The `app/models/` directory has 4 floating models with no module home.

### 5.1 Migrate `app/models/client.py` → `app/modules/clients/`

The `client.py` model belongs to the clients module but the entire `app/modules/clients/` directory doesn't exist yet. Create the full module:

**Create `app/modules/clients/` with these files:**

**`app/modules/clients/__init__.py`** — empty

**`app/modules/clients/model.py`** — Move the content of `app/models/client.py` here. Update the module docstring to reflect its new home. Ensure all SQLAlchemy imports use `app.core.db.Base`.

**`app/modules/clients/schemas.py`** — Create Pydantic v2 schemas matching the Client model fields:
- `ClientBase`, `ClientCreate`, `ClientUpdate`, `ClientRead` using `model_config = ConfigDict(from_attributes=True)`

**`app/modules/clients/repo.py`** — Move content from `app/modules/users/client_service.py` that contains DB query logic (CRUD operations). Standard repo pattern with `get_by_id`, `get_all`, `create`, `update`, `delete`.

**`app/modules/clients/service.py`** — Business logic layer, thin wrapper over repo. Move business logic from `app/modules/users/client_service.py` here.

**`app/modules/clients/router.py`** — Move content from `app/modules/users/client_router.py` here. Update all internal imports. Keep the same route paths so existing UI calls don't break.

**After creating the module:**
1. Update `app/main.py`:
   - Remove: `from app.modules.users.client_router import router as client_router`
   - Add: `from app.modules.clients.router import router as client_router`
   - Remove: `import app.models.client  # noqa: F401`
   - Add: `import app.modules.clients.model  # noqa: F401`
2. Delete `app/modules/users/client_router.py`
3. Delete `app/modules/users/client_service.py`
4. Delete `app/models/client.py`

---

### 5.2 Migrate `app/models/csp_score.py` → `app/modules/csp/`

The CSP module has a route file at `app/api/routes/csp_routes.py` but no `app/modules/csp/` directory. Create the module:

**Create `app/modules/csp/` with these files:**

**`app/modules/csp/__init__.py`** — empty

**`app/modules/csp/model.py`** — Move content of `app/models/csp_score.py` here. Update imports.

**`app/modules/csp/schemas.py`** — Pydantic v2 schemas for CSP score read/response.

**`app/modules/csp/service.py`** — Move content of `app/services/csp_service.py` here. This is the business logic for CSP scoring. Update all internal imports.

After moving:
1. Update `app/main.py`:
   - Remove: `import app.models.csp_score  # noqa: F401`
   - Add: `import app.modules.csp.model  # noqa: F401`
2. Update `app/api/routes/csp_routes.py`: change `from app.services.csp_service import CSPService` → `from app.modules.csp.service import CSPService`
3. Update `app/modules/intel/settlement_router.py`: same import update
4. Delete `app/models/csp_score.py`
5. Delete `app/services/csp_service.py`

---

### 5.3 Migrate `app/models/insurer_financials.py` → Delete (duplicate)

`app/models/insurer_financials.py` is an identical duplicate of `app/modules/financials/model.py`.

**Action:**
1. Verify they are identical: `diff app/models/insurer_financials.py app/modules/financials/model.py`
2. Find any imports of `app.models.insurer_financials`:
   ```
   grep -rn "from app\.models\.insurer_financials\|app\.models\.insurer_financials" app/ --include="*.py" | grep -v __pycache__
   ```
3. Update any found imports to `app.modules.financials.model`
4. Remove from `main.py`: `import app.models.insurer_financials  # noqa: F401`
5. Delete `app/models/insurer_financials.py`

---

### 5.4 Migrate `app/models/insurer.py` → Delete (stub)

`app/models/insurer.py` is a 10-line stub. The full model (92 lines) lives at `app/modules/insurers/model.py`.

**Action:**
1. Find all imports of `app.models.insurer`:
   ```
   grep -rn "from app\.models\.insurer\b\|app\.models\.insurer\b" app/ --include="*.py" | grep -v __pycache__
   ```
2. Update any found imports to `app.modules.insurers.model`
3. Remove from `main.py`: `import app.models.insurer  # noqa: F401`
4. Delete `app/models/insurer.py`
5. **After deleting all 4 models files:** delete `app/models/` directory entirely

---

## 6. CREATE `app/modules/compliance/` MODULE

The compliance checker lives at `app/services/compliance_checker.py` with no module home. Create the proper module:

**Create `app/modules/compliance/` with these files:**

**`app/modules/compliance/__init__.py`** — empty

**`app/modules/compliance/service.py`** — Move `app/services/compliance_checker.py` content here. Keep the `get_compliance_checker()` factory function. Update module docstring.

**`app/modules/compliance/schemas.py`** — Pydantic v2 schemas:
```python
class ComplianceCheckResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    compliance_score: float
    status: str  # "compliant" | "non_compliant" | "partial"
    mandatory_clauses: dict
    prohibited_terms: dict
    recommendations: list[str]
```

**After creating:**
1. Update all callers of `app.services.compliance_checker`:
   - `app/modules/documents/router.py` → `from app.modules.compliance.service import get_compliance_checker`
   - `app/modules/documents/service.py` → same
   - `app/modules/compat_router.py` → same
2. Delete `app/services/compliance_checker.py`

---

## 7. DISTRIBUTE REMAINING `app/services/` FILES

After the above migrations, `app/services/` will still contain files. Distribute them:

| File | Move To | Reason |
|------|---------|--------|
| `advisory_service.py` | `app/modules/intel/advisory_service.py` | Intel/insurer advisory logic |
| `circular_classifier.py` | `app/modules/ml/circular_classifier.py` | ML classification — lives in ml module |
| `dataset_registry.py` | `app/infrastructure/storage/dataset_registry.py` | Infrastructure data management |
| `document_classifier_service.py` | `app/modules/documents/classifier_service.py` | Documents module service |
| `entity_extraction_service.py` | `app/modules/documents/entity_extraction_service.py` | Documents module service |
| `insurer_analytics.py` | `app/modules/insurers/analytics_service.py` | Insurers module service |
| `model_training_service.py` | `app/modules/ml/training_service.py` | ML module |
| `prediction_service.py` | `app/modules/ml/prediction_service.py` | ML module |
| `training_orchestrator.py` | `app/modules/ml/training_orchestrator.py` | ML module |
| `visualization_service.py` | `app/modules/ml/visualization_service.py` | ML/reporting |
| `document_ingestion/` (whole dir) | `app/modules/documents/ingestion/` | Documents module |
| `demo_dashboard_service.py` | **DELETE** — demo mode only, not wired to production |
| `mode_registry.py` | **DELETE** — depends on demo_dashboard_service, demo mode only |
| `zse_service.py` | **DELETE** — ZSE module removed from product scope |

**For each file being moved:**
1. Move the file to its new location
2. Update its internal imports if they reference `app.services.*`
3. Run `grep -rn "from app.services.<filename>" app/ --include="*.py"` to find callers
4. Update all callers to the new import path
5. After all moves, verify `app/services/` is empty except `__init__.py`, then delete it

**Special handling for `app/ui/router.py`** — it imports from `demo_dashboard_service`, `mode_registry`, `visualization_service`, and `circular_classifier`. Since `demo_dashboard_service` and `mode_registry` are being deleted:
- Find all uses of `get_demo_dashboard_summary` and `get_mode_summary` in `ui/router.py`
- Replace `get_demo_dashboard_summary()` calls with a direct DB query for document/insurer counts (simple inline query, no service needed)
- Replace `get_mode_summary()` calls with a hardcoded `{"mode": "production"}` dict
- Update `visualization_service` and `circular_classifier` imports to their new paths

---

## 8. DEAD CODE REMOVAL

Remove modules that are permanently out of scope:

### 8.1 Remove ZSE module
```bash
rm -rf app/modules/zse/
# zse_service.py already deleted in step 7
```

### 8.2 Remove `app/portfolio/`
```bash
rm -rf app/portfolio/
# portfolio_analytics.py has no router, no model, not imported anywhere
```

### 8.3 Clean up `app/modules/circulars/`
The circulars module is training-data only and its router is not registered in `main.py`.
- Keep `app/modules/circulars/` on disk (needed for classifier training pipeline in `app/modules/ml/`)
- Add a clear `README.md` inside: "This module is training-data only. The router is intentionally not registered in main.py. Do not register it."
- Do NOT delete it — the ML classifier uses the circulars data

### 8.4 Update `main.py` model imports
After all the above, the `import app.models.*` block in `main.py` should be empty (all models now live in their modules). Remove that entire block. The models are already imported via `import app.modules.*.model` imports.

Final `main.py` model import block should look like:
```python
import app.modules.insurers.model          # noqa: F401
import app.modules.insurers.claims_model   # noqa: F401
import app.modules.insurers.scrape_model   # noqa: F401
import app.modules.financials.model        # noqa: F401
import app.modules.news.model              # noqa: F401
import app.modules.qa.model                # noqa: F401
import app.modules.comparison.model        # noqa: F401
import app.modules.feedback.model          # noqa: F401
import app.modules.deviation.model         # noqa: F401
import app.modules.batch.model             # noqa: F401
import app.modules.tracker.model           # noqa: F401
import app.modules.audit.model             # noqa: F401
import app.modules.multilingual.model      # noqa: F401
import app.modules.documents.model         # noqa: F401
import app.modules.clients.model           # noqa: F401  ← NEW
import app.modules.csp.model               # noqa: F401  ← NEW
```

---

## 9. GITIGNORE UPDATE + GITHUB REPO INIT

### 9.1 Update `.gitignore`

Add these additional entries to the existing `.gitignore`:
```gitignore
# ── Scratch / temp files ────────────────────────────────────────────────────
zip_*.txt
*.txt.bak

# ── Stitch design exports (keep only stitch/, not extracted copies) ──────────
stitch_extracted/

# ── App database (SQLite dev only) ──────────────────────────────────────────
app.db

# ── Seed / generated data files ─────────────────────────────────────────────
seed_financials.csv
generate_seed_financials.py

# ── UV/pip lock files (optional — add if using uv) ──────────────────────────
uv.lock

# ── Claude Code session files ────────────────────────────────────────────────
.claude/
```

### 9.2 Create GitHub repo and push

Run these commands from inside `CAPSTONE_ARCHIVE/PRIMARY/EXPERIMENT/`:

```bash
# Verify git is not already initialised
ls -la .git 2>/dev/null && echo "Git already initialised" || echo "No git repo yet"

# If no git repo:
git init
git branch -m main

# Stage everything (respects .gitignore)
git add .

# Verify nothing sensitive is staged
git status

# Initial commit
git commit -m "feat: initial modular monolith — Phase 1 structural cleanup complete

- Removed duplicate directories: app/ml/, app/rag/, app/multilingual/, app/scrapers/
- Merged split modules: comparison, deviation, feedback, tracker, audit into app/modules/
- Created new modules: app/modules/clients/, app/modules/csp/, app/modules/compliance/
- Migrated floating models from app/models/ into respective modules
- Distributed app/services/ files to owning modules
- Deleted dead code: app/modules/zse/, app/portfolio/, app/domains/
- Deleted stitch_extracted/ duplicate, zip_*.txt scratch files
- Secured SECRET_KEY — now loaded from .env, never random
- All 68 tests passing after restructure"

# Create the GitHub repo (requires GitHub CLI — gh)
# If gh is not installed, skip this and provide manual instructions
gh repo create insure-intel-zimbabwe \
  --private \
  --description "AI-Powered Insurance Document Intelligence Platform — BSc Honours Capstone, University of Zimbabwe" \
  --source=. \
  --remote=origin \
  --push

# If gh CLI is not available, print manual instructions:
echo ""
echo "============================================"
echo "GitHub CLI not available. To push manually:"
echo "1. Create repo at https://github.com/new"
echo "   Name: insure-intel-zimbabwe"
echo "   Visibility: Private"
echo "   Do NOT initialise with README (we already have one)"
echo "2. Then run:"
echo "   git remote add origin https://github.com/<your-username>/insure-intel-zimbabwe.git"
echo "   git push -u origin main"
echo "============================================"
```

---

## 10. VERIFICATION CHECKLIST

After completing all steps, run these checks:

```bash
# 1. App imports cleanly
python -c "from app.main import app; print('✅ App imports OK')"

# 2. All tests pass
python -m pytest tests/ -q --tb=short

# 3. No imports left pointing to deleted directories
grep -rn "from app\.ml\.\|from app\.rag\.\|from app\.multilingual\.\|from app\.scrapers\.\|from app\.audit\.\|from app\.comparison\.\|from app\.deviation\.\|from app\.feedback\.\|from app\.tracker\.\|from app\.models\.\|from app\.services\.\|from app\.portfolio\." app/ --include="*.py" | grep -v __pycache__ | grep -v ".pyc"

# Expected: zero results

# 4. Deleted directories are gone
for d in app/ml app/rag app/multilingual app/scrapers app/audit app/comparison app/deviation app/feedback app/tracker app/models app/services app/portfolio app/domains stitch_extracted; do
  [ -d "$d" ] && echo "❌ $d still exists!" || echo "✅ $d gone"
done

# 5. New modules exist
for d in app/modules/clients app/modules/csp app/modules/compliance; do
  [ -d "$d" ] && echo "✅ $d exists" || echo "❌ $d MISSING!"
done

# 6. Git is clean after commit
git status
```

---

## IMPORTANT NOTES

- **`app/modules/zse/`** — delete entirely, it's dead code
- **`app/modules/circulars/`** — keep on disk, it feeds the classifier training pipeline; add README note
- **`app/modules/ml/`** — this is the ML module inside `modules/`, NOT the duplicate `app/ml/`. Keep it.
- **`app/ai/`** — this is the canonical AI/inference layer. Keep everything in it.
- **`app/infrastructure/`** — canonical I/O layer. Keep everything in it.
- **`stitch/`** — canonical design mockups folder. Keep it.
- The `.env` file is in `.gitignore` — it will NOT be committed. Only `.env.example` goes to GitHub.
- After the commit, `app.db` (SQLite dev database) should also not be committed — it's in `.gitignore`.
