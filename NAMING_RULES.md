# NAMING_RULES.md
## InsureIntel Zimbabwe — Naming Consistency Standards

---

## 1. File & Directory Names

| Artifact | Convention | Examples |
|---|---|---|
| Module directories | `snake_case` | `documents/`, `intel/`, `csp/` |
| Python source files | `snake_case.py` | `advisory_service.py`, `clause_aligner.py` |
| Router files | `router.py` (one per module) | `app/modules/documents/router.py` |
| Service files | `service.py` (one per module) | `app/modules/documents/service.py` |
| Repository files | `repo.py` (one per module) | `app/modules/insurers/repo.py` |
| ORM model files | `model.py` (one per module) | `app/modules/documents/model.py` |
| Pydantic schemas | `schemas.py` (one per module) | `app/modules/insurers/schemas.py` |

Specialised service files that exist alongside `service.py` are allowed and must be named
`<domain>_service.py` (e.g., `advisory_service.py`, `analytics_service.py`).

---

## 2. Class Names

| Class type | Convention | Examples |
|---|---|---|
| ORM model | `PascalCase`, noun | `Document`, `Insurer`, `CSPScore` |
| Pydantic schema (input) | `PascalCase` + `Create` / `Update` | `InsurerCreate`, `DocumentUpdate` |
| Pydantic schema (output) | `PascalCase` + `Out` or `Response` | `InsurerOut`, `DocumentResponse` |
| Service class | `PascalCase` + `Service` | `InsurerService`, `DocumentClassifierService` |
| Repository class | `PascalCase` + `Repo` | `InsurerRepo`, `CircularsRepo` |
| ML/AI engine class | `PascalCase` descriptive | `QAEngine`, `WCSScorer`, `MLPredictor` |
| FastAPI dependency | plain `PascalCase` noun or `get_*` function | `get_current_user`, `get_db` |

---

## 3. Function & Method Names

| Context | Convention | Examples |
|---|---|---|
| Public service method | `verb_noun` in `snake_case` | `create_insurer`, `process_document_full` |
| Public repo method | short CRUD verbs | `create`, `get`, `get_by_name`, `list`, `update`, `delete` |
| Private helper (module-level) | leading underscore + `snake_case` | `_classify_clause_type`, `_extract_keywords` |
| FastAPI route handler | `snake_case` verb | `upload_document`, `list_insurers`, `delete_insurer` |
| Background task function | `snake_case` with `_background` or `_job` suffix | `_process_document_background`, `run_scraper_job` |

---

## 4. Variable Names

- Use `db` for all `Session` parameters.
- Use `payload` for Pydantic input schema parameters in service/router functions.
- Use descriptive names for loop variables — not `i` or `x` (except trivial counter loops).
- Prefix module-level private constants with `_` and use `UPPER_SNAKE_CASE` for the remainder:
  `_STOP_WORDS`, `_CLAUSE_KEYWORDS`, `_COMPILED_KB`.

---

## 5. Router Prefix Conventions

All API routers must declare a prefix in the `APIRouter(prefix=...)` constructor. Prefixes follow:

| Module | Prefix |
|---|---|
| `documents` | `/api/documents` |
| `qa` | `/api/qa` |
| `chatbot` | `/api/chatbot` |
| `comparison` | `/api/comparison` |
| `feedback` | `/api/feedback` |
| `deviation` | `/api/deviation` |
| `batch` | `/api/batch` |
| `tracker` | `/api/tracker` |
| `audit` | `/api/audit` |
| `reports` | `/api/reports` |
| `multilingual` | `/api/multilingual` |
| `insurers` | `/insurers` |
| `financials` | `/financials` |
| `intel` | `/intel` |
| `auth` | `/auth` |
| `clients` | `/clients` |
| `ml` | `/ml` |

Routers registered under `/api/` must not also register routes without the `/api/` prefix.

---

## 6. Logging Names

Every module must obtain its logger using:

```python
logger = logging.getLogger(__name__)
```

Do not use a hard-coded string (e.g. `logging.getLogger("documents.service")`). This ensures
the logger name mirrors the module path and all log output can be filtered consistently.

---

## 7. Constant Naming for Shared NLP Utilities

Shared constants exported from `app/ai/nlp/text_utils.py` are named without a leading underscore
(they are public) and use `UPPER_SNAKE_CASE`:

```python
# app/ai/nlp/text_utils.py
STOP_WORDS: frozenset[str] = frozenset({...})
```

Module-private aliases may shadow the public name with a leading underscore if preferred:

```python
# inside a consuming module
from app.ai.nlp.text_utils import STOP_WORDS as _STOP_WORDS
```

---

## 8. Endpoint Parameter Names

- Path parameters: `snake_case` matching the model field (`document_id`, `insurer_id`).
- Query parameters: `snake_case` (`skip`, `limit`, `status`).
- Body fields (Pydantic): `snake_case`.
- Response fields (Pydantic): `snake_case`.

Do not mix camelCase and snake_case within the same schema.

---

## 9. Tag Names for OpenAPI

Each `APIRouter` must declare `tags=[...]`. Use the module's domain noun, singular or plural
as appropriate:

```python
router = APIRouter(prefix="/api/documents", tags=["documents"])
router = APIRouter(prefix="/insurers", tags=["insurers"])
```
