# SERVICE_RULES.md
## InsureIntel Zimbabwe — Service, Router & Repository Engineering Standards

---

## 1. Layer Definitions

The application is divided into four strict layers. Each layer may only depend on layers below it.

```
HTTP Layer       →  Router  (FastAPI APIRouter)
Business Logic   →  Service (domain service classes / functions)
Data Access      →  Repo    (SQLAlchemy query methods only)
Persistence      →  Model   (SQLAlchemy ORM models)
```

Cross-layer calls must always travel downward. No layer may import from a layer above it.

---

## 2. Router Responsibilities

Routers handle **only** the HTTP contract. They must not contain business logic.

**Allowed in a router:**
- Declare path, method, status codes, and response schema.
- Extract and validate request parameters, path variables, and body fields.
- Resolve FastAPI dependencies (`Depends(get_db)`, `Depends(get_current_user)`).
- Call one service function per endpoint and return its result.
- Raise `HTTPException` when the service raises a known domain error.

**Forbidden in a router:**
- SQLAlchemy queries, `db.add()`, `db.commit()`, or any direct ORM access.
- Importing or calling a `Repo` class directly.
- Importing or instantiating AI/ML pipeline objects (`QAEngine`, `WCSScorer`, etc.).
- Importing from `app.core.db.SessionLocal` (use `Depends(get_db)` only).
- Business logic: conditional data transformation, scoring, enrichment.
- Making HTTP requests back to the same application (`httpx.AsyncClient` to `settings.api_base`).

**Pattern — correct router endpoint:**
```python
@router.post("/", response_model=InsurerOut, status_code=201)
def create(payload: InsurerCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        return insurer_service.create_insurer(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
```

---

## 3. Service Responsibilities

Services own all **business logic**. They are plain Python classes or modules — no FastAPI imports.

**Allowed in a service:**
- Calling one or more `Repo` methods on the session passed to them.
- Calling AI/ML engines as collaborators (pass results in, pass results out).
- Raising `ValueError` or domain-specific exceptions for invalid states.
- Coordinating multi-step workflows (read → transform → write).

**Forbidden in a service:**
- Importing `APIRouter`, `HTTPException`, `Request`, or any FastAPI types.
- Opening or closing database sessions (accept `db: Session` as a parameter).
- Direct ORM operations (`db.add`, `db.commit`, `db.query`). Delegate to repo.
- Calling other services in a way that creates a circular import (use lazy imports only as a temporary, audited exception — see §6).

---

## 4. Repository Responsibilities

Repositories contain **all SQLAlchemy queries**. They must not contain business logic.

**Allowed in a repo:**
- `SELECT`, `INSERT`, `UPDATE`, `DELETE` operations via SQLAlchemy `select()` / `session.add()`.
- Returning ORM model instances or `None`.

**Forbidden in a repo:**
- Calling `db.commit()` or `db.rollback()`. Transaction boundaries belong to the service or request lifecycle.
- Raising domain errors (`ValueError`, `HTTPException`).
- Importing from other domain modules (repos may only import from `app.core` and their own `model.py`).

**Exception:** `InsurerRepo.create` currently calls `db.commit()` directly. This is a known deviation
tracked in `TRANSACTION_RULES.md §3`. Migration path: move commit responsibility to the service layer.

---

## 5. Service Boundary Rules

Each domain module (`app/modules/<domain>/`) exposes exactly one public service interface.

| Domain artifact | Owner module |
|---|---|
| Document ingestion, status updates | `app.modules.documents.service` |
| Insurer CRUD | `app.modules.insurers.service` |
| CSP scoring | `app.modules.csp.service` |
| Advisory generation | `app.modules.intel.advisory_service` |
| Compliance checking | `app.modules.compliance.service` |

If module A needs a result that belongs to module B, module A calls module B's **service**, never
module B's repo or model directly. The only exception is `app.core.*` which is a shared kernel.

---

## 6. Lazy Imports (Circular Dependency Mitigation)

Function-local lazy imports (`from x import y` inside a function body) are permitted **only** when a
genuine circular import exists that cannot be resolved by restructuring. Every such import must be
accompanied by an inline comment:

```python
# lazy import: circular dependency with app.modules.scoring.fusion
from app.modules.scoring.fusion import compute_fused_risk
```

Lazy imports must not be used to give a router direct access to a service it should not call
(e.g., `compat_router` calling `compliance.service` directly). These must be migrated to the correct
ownership module.

---

## 7. compat_router Policy

`app.modules.compat_router` wraps legacy REST paths for backwards compatibility only. It must not
contain business logic. Each `compat_router` endpoint must delegate to the canonical service for
that domain. The `compat_router` must not import AI engines, repos, or ML models directly.

---

## 8. UI Router Policy

`app.ui.router` and `app.ui.extra_router` render Jinja2 HTML templates. They follow the same rules
as API routers except:

- They may call service functions **or** call the `/api/` HTTP routes — not both for the same data.
- They must not make loopback HTTP calls to the same process (`httpx` to `settings.api_base`).
  Instead, call the service function directly.
- They must not import from `app.core.db.SessionLocal` directly; use `Depends(get_db)`.
- They must not import repos directly.
