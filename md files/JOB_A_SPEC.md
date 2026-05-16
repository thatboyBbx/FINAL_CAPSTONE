# JOB A SPECIFICATION — Backend Security Hardening
**Consumed by:** JOB_A_PROMPT.txt agent team  
**Touches:** config.py · auth/dependencies.py · 18 router files · main.py · requirements.txt · .env.example

---

## BACKGROUND — WHY THIS JOB EXISTS

The codebase has three critical security failures that must be fixed before anything else:

1. **SECRET_KEY regenerates on every server restart** — `secrets.token_urlsafe(32)` is called as a default value inside the Settings class. Python evaluates this once per module load, meaning every restart produces a new key and invalidates every JWT in existence. Every user gets silently logged out on deploy.

2. **Zero route protection** — `grep -rn "get_current_user" app/modules/` returns 0 results. Every single API endpoint — documents, insurers, ML models, CSP scores — is completely public. No login required.

3. **Dead modules still registered** — `circulars_router` and `chatbot_router` are imported and registered in `main.py`. The chatbot crashes immediately (requires paid Anthropic key). The circulars module was supposed to be removed from the live app.

There are also two housekeeping issues: `pydantic[email]` is missing from requirements.txt (causes startup crash when email validation triggers), and `@app.on_event("startup")` is deprecated since FastAPI 0.93.

---

## TASK 1 — Fix `app/core/config.py`

**Problem:** Line 22 reads:
```python
secret_key: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
```

**Fix:** Replace the entire file with this exact content:

```python
"""
app/core/config.py
==================
Centralised application settings, loaded once from the .env file.

SECRET_KEY note:
  Development uses a fixed fallback so JWTs survive server restarts.
  Production MUST set SECRET_KEY in .env to a real random value.
  The app refuses to start in production with the dev fallback.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, model_validator

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

# Fixed dev-only fallback — stable across restarts, never used in production
_DEV_FALLBACK_KEY = (
    "insure-intel-dev-only-secret-key-do-not-use-in-production-minimum64chars!!"
)


class Settings(BaseModel):
    model_config = ConfigDict(extra="allow")

    app_name: str = os.getenv("APP_NAME", "Insurance Documents Intelligence Platform")
    env: str = os.getenv("ENV", "dev")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    api_base: str = os.getenv("API_BASE", "http://127.0.0.1:8000")
    model_storage_dir: str = os.getenv("MODEL_STORAGE_DIR", "app/storage/models")

    # JWT
    secret_key: str = os.getenv("SECRET_KEY", _DEV_FALLBACK_KEY)
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )

    # Storage paths
    demo_dataset_dir: str = os.getenv("DEMO_DATASET_DIR", "storage/datasets/demo")
    app_dataset_dir: str = os.getenv("APP_DATASET_DIR", "storage/datasets/app")
    demo_model_dir: str = os.getenv("DEMO_MODEL_DIR", "storage/models/demo")
    app_model_dir: str = os.getenv("APP_MODEL_DIR", "storage/models/app")

    # LLM — intentionally empty; chatbot uses offline engine (see Job C)
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    @model_validator(mode="after")
    def _block_dev_key_in_production(self) -> "Settings":
        """Refuse to start in production with the insecure dev fallback key."""
        if self.env == "production" and self.secret_key == _DEV_FALLBACK_KEY:
            raise ValueError(
                "SECRET_KEY must be set to a secure random value in production. "
                "Generate one with: openssl rand -hex 32"
            )
        return self


settings = Settings()
```

**Security reviewer checks:**
- No `secrets.token_urlsafe()` call anywhere in this file
- `_DEV_FALLBACK_KEY` is a long fixed string (≥64 chars)
- `model_validator` is from `pydantic` (not `pydantic.v1`)
- `model_validator(mode="after")` syntax — correct for Pydantic v2

---

## TASK 2 — Create `app/modules/auth/dependencies.py` (new file)

This file does not exist yet. Create it:

```python
"""
app/modules/auth/dependencies.py
==================================
JWT authentication dependency for FastAPI API routes.

This is for JSON API endpoints — it returns HTTP 401 on failure.
For HTML page routes (browser redirects), see ui_dependencies.py (Job B).

Usage:
    from app.modules.auth.dependencies import get_current_user, require_role

    # Protect an entire router:
    router = APIRouter(dependencies=[Depends(get_current_user)])

    # Protect a single endpoint:
    @router.get("/me")
    def get_me(user: User = Depends(get_current_user)):
        return user

    # Role-based access:
    @router.delete("/admin-action")
    def admin_action(user: User = Depends(require_role("admin"))):
        ...
"""
from __future__ import annotations

import logging
from typing import Callable

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.service import decode_access_token
from app.modules.users.model import User

logger = logging.getLogger(__name__)

# auto_error=False so we can fall back to cookie when header is absent
_bearer = HTTPBearer(auto_error=False)


def _extract_token(
    credentials: HTTPAuthorizationCredentials | None,
    access_token: str | None,
) -> str | None:
    """
    Extract token from Authorization header first, cookie second.
    Returns the raw token string or None if neither source has one.
    """
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    if access_token:
        return access_token
    return None


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """
    Validate the JWT and return the authenticated User.
    Sources checked in order: Authorization header, then access_token cookie.

    Raises:
        HTTP 401 — missing token, expired token, invalid token, user not found
        HTTP 403 — user account is deactivated
    """
    token = _extract_token(credentials, access_token)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: int | None = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token.",
        )

    user: User | None = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Contact your administrator.",
        )

    return user


def require_role(*allowed_roles: str) -> Callable[..., User]:
    """
    Return a dependency that enforces role membership.

    Example:
        @router.post("/approve")
        def approve(user: User = Depends(require_role("admin", "manager"))):
            ...
    """
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access denied. Required: {', '.join(allowed_roles)}. "
                    f"Your role: {current_user.role}."
                ),
            )
        return current_user

    return _check
```

**Security reviewer checks:**
- `HTTPBearer(auto_error=False)` — correct; allows cookie fallback
- Cookie import is `from fastapi import Cookie` — correct
- `decode_access_token` returns `None` on failure — handled
- `db.get(User, user_id)` — correct SQLAlchemy 2.0 syntax
- `require_role` uses `Depends(get_current_user)` inside the inner function — correct

---

## TASK 3 — Add `dependencies=[Depends(get_current_user)]` to 18 router files

For each file listed below, make exactly this change:

**Find** the existing `router = APIRouter(...)` line.  
**Replace** it with the version that includes `dependencies=[Depends(get_current_user)]`.

The import to add at the top of each file:
```python
from fastapi import Depends
from app.modules.auth.dependencies import get_current_user
```

The router line change pattern:
```python
# BEFORE (example):
router = APIRouter(prefix="/documents", tags=["documents"])

# AFTER:
router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    dependencies=[Depends(get_current_user)],
)
```

**Apply to these 18 files:**

| File | Current prefix |
|------|---------------|
| `app/modules/documents/router.py` | `/documents` |
| `app/modules/insurers/router.py` | `/insurers` |
| `app/modules/financials/router.py` | `/financials` |
| `app/modules/news/router.py` | `/news` |
| `app/modules/ml/router.py` | `/ml` |
| `app/api/routes/csp_routes.py` | (check file for prefix) |
| `app/modules/intel/router.py` | `/intel` |
| `app/modules/intel/settlement_router.py` | (check file for prefix) |
| `app/modules/qa/router.py` | `/api/qa` |
| `app/modules/comparison/router.py` | `/api/comparison` |
| `app/modules/feedback/router.py` | `/api/feedback` |
| `app/modules/deviation/router.py` | `/api/deviation` |
| `app/modules/batch/router.py` | `/api/batch` |
| `app/modules/tracker/router.py` | `/api/tracker` |
| `app/modules/audit/router.py` | `/api/audit` |
| `app/modules/multilingual/router.py` | `/api/multilingual` |
| `app/modules/users/client_router.py` | (check file for prefix) |
| `app/modules/reports/router.py` | `/api/reports` |

**DO NOT touch:**
- `app/modules/auth/router.py` — login and register must stay public
- `app/ui/router.py` — UI routes handled separately in Job B
- `app/ui/extra_router.py` — UI routes handled separately in Job B

**Security reviewer checks (run for all 18 files):**
```bash
# Must return 18 (one match per file)
grep -rl "dependencies=\[Depends(get_current_user)\]" app/modules app/api | wc -l

# Must return 0 (auth router must NOT have this)  
grep -n "get_current_user" app/modules/auth/router.py
```

---

## TASK 4 — Rewrite `app/main.py`

Replace the entire file. Key changes from original:
- Remove `circulars_router` import and registration
- Remove `chatbot_router` import and registration  
- Remove `zse` module imports if any exist
- Replace `@app.on_event("startup")` with `lifespan` context manager
- Add `StaticFiles` mount (it may already exist — confirm it does)
- Keep all other 19 routers

```python
"""
app/main.py
===========
FastAPI application factory for InsureIntel Zimbabwe.

Removed from live registration (kept on disk for training pipelines):
  - circulars module  (data used for classifier training only)
  - zse module        (ZSE scraping is fragile; not needed for thesis demo)
  - chatbot module    (replaced with offline engine — see Job C)
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.db import Base, engine
from app.core.logging import setup_logging

# ── API routers ────────────────────────────────────────────────────────────
from app.modules.auth.router import router as auth_router
from app.modules.documents.router import router as documents_router
from app.modules.financials.router import router as financials_router
from app.modules.insurers.router import router as insurers_router
from app.modules.intel.router import router as intel_router
from app.modules.ml.router import router as ml_router
from app.modules.news.router import router as news_router
from app.api.routes.csp_routes import router as csp_router
from app.modules.qa.router import router as qa_router
from app.modules.comparison.router import router as comparison_router
from app.modules.feedback.router import router as feedback_router
from app.modules.deviation.router import router as deviation_router
from app.modules.batch.router import router as batch_router
from app.modules.tracker.router import router as tracker_router
from app.modules.audit.router import router as audit_router
from app.modules.multilingual.router import router as multilingual_router
from app.modules.users.client_router import router as client_router
from app.modules.reports.router import router as reports_router
from app.modules.intel.settlement_router import router as settlement_router

# ── UI routers ─────────────────────────────────────────────────────────────
from app.ui.router import router as ui_router
from app.ui.extra_router import router as extra_ui_router

# ── Model imports — required for Base.metadata.create_all() ───────────────
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
import app.models.insurer                  # noqa: F401
import app.models.insurer_financials       # noqa: F401
import app.models.csp_score                # noqa: F401
import app.models.client                   # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Startup and shutdown logic.
    Replaces the deprecated @app.on_event("startup") pattern.
    """
    # ── Startup ──────────────────────────────────────────────────────────
    setup_logging()
    Base.metadata.create_all(bind=engine)

    try:
        from app.scrapers.scraper_scheduler import start_scheduler
        start_scheduler()
        logger.info("Scraper scheduler started.")
    except Exception as exc:
        logger.warning("Scraper scheduler could not start: %s", exc)

    logger.info("InsureIntel Zimbabwe started — env=%s", settings.env)
    yield
    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("InsureIntel Zimbabwe shutting down.")


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )

    # Static files (CSS, JS, images)
    app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")

    # UI routes (HTML pages — served first)
    app.include_router(ui_router)
    app.include_router(extra_ui_router)

    # Auth (public — no JWT dependency on these)
    app.include_router(auth_router)

    # Protected API routes (JWT enforced via router-level dependencies)
    app.include_router(documents_router)
    app.include_router(insurers_router)
    app.include_router(financials_router)
    app.include_router(news_router)
    app.include_router(ml_router)
    app.include_router(csp_router)
    app.include_router(intel_router)
    app.include_router(settlement_router)
    app.include_router(qa_router)
    app.include_router(comparison_router)
    app.include_router(feedback_router)
    app.include_router(deviation_router)
    app.include_router(batch_router)
    app.include_router(tracker_router)
    app.include_router(audit_router)
    app.include_router(multilingual_router)
    app.include_router(client_router)
    app.include_router(reports_router)

    # Audit trail middleware
    from app.audit.audit_middleware import AuditMiddleware
    app.add_middleware(AuditMiddleware)

    @app.get("/health")
    def health():
        return {"status": "ok", "env": settings.env}

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        if (
            request.url.path.startswith("/api")
            or request.url.path.startswith("/intel")
            or request.url.path.startswith("/analytics")
            or request.url.path.startswith("/ml")
        ):
            return JSONResponse(
                {"error": "Not found", "path": str(request.url.path)},
                status_code=404,
            )
        return JSONResponse(
            {"error": "Page not found", "path": str(request.url.path)},
            status_code=404,
        )

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc):
        logger.error("500 on %s: %s", request.url.path, exc)
        return JSONResponse(
            {"error": "Internal server error. Please try again."},
            status_code=500,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled on %s: %s", request.url.path, exc, exc_info=True)
        return JSONResponse({"error": "An unexpected error occurred."}, status_code=500)

    return app


app = create_app()
```

---

## TASK 5 — Fix `requirements.txt` and `.env.example`

### requirements.txt changes:
1. Change `pydantic` → `pydantic[email]`
2. Add `email-validator>=2.0.0` on the line directly below it
3. Delete the line `anthropic>=0.25.0` entirely

### Replace `.env.example` entirely:
```
# InsureIntel Zimbabwe — Environment Configuration
# Copy this file to .env and fill in values before running the app.

APP_NAME=Insurance Documents Intelligence Platform
ENV=dev

# Database — SQLite for development
DATABASE_URL=sqlite:///./app.db

LOG_LEVEL=INFO
API_BASE=http://127.0.0.1:8000

# JWT Security
# For production, generate with: openssl rand -hex 32
SECRET_KEY=insure-intel-dev-only-secret-key-do-not-use-in-production-minimum64chars!!
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Storage paths (relative to project root)
MODEL_STORAGE_DIR=app/storage/models
DEMO_DATASET_DIR=storage/datasets/demo
APP_DATASET_DIR=storage/datasets/app
DEMO_MODEL_DIR=storage/models/demo
APP_MODEL_DIR=storage/models/app
```

---

## VERIFICATION STEPS
**All of these must pass before this job is considered complete.**

```bash
# V1 — App imports cleanly
python3 -c "from app.main import app; print('PASS: import OK')"

# V2 — App starts without deprecation warnings
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
sleep 4

# V3 — SECRET_KEY is stable across two loads
python3 -c "
import importlib
from app.core import config as cfg
k1 = cfg.settings.secret_key
importlib.reload(cfg)
k2 = cfg.settings.secret_key
print('PASS: key stable' if k1 == k2 else 'FAIL: key changed')
"

# V4 — Unauthenticated API call returns 401
CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/documents/)
[ "$CODE" = "401" ] && echo "PASS: /documents/ returns 401" || echo "FAIL: got $CODE"

# V5 — Auth routes remain public (login returns 422 with empty body, not 401)
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8000/auth/login)
[ "$CODE" = "422" ] && echo "PASS: /auth/login is public" || echo "FAIL: got $CODE"

# V6 — Health check works (always public)
curl -s http://127.0.0.1:8000/health | python3 -m json.tool

# V7 — circulars route is gone
CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/circulars/analyses)
[ "$CODE" = "404" ] && echo "PASS: circulars route removed" || echo "FAIL: got $CODE"

# V8 — on_event is gone from main.py
grep -n "on_event" app/main.py && echo "FAIL: on_event still present" || echo "PASS: on_event removed"

# V9 — email-validator installed
python3 -c "import email_validator; print('PASS: email_validator available')"

# V10 — 18 routers have get_current_user dependency
COUNT=$(grep -rl "get_current_user" app/modules app/api | grep "router.py\|routes.py" | wc -l)
echo "Routers with auth: $COUNT (expected 18)"

pkill -f "uvicorn app.main" 2>/dev/null || true
```

**Expected output for all steps:**
- V1: `PASS: import OK`
- V2: No `DeprecationWarning: on_event` in startup output
- V3: `PASS: key stable`
- V4: `PASS: /documents/ returns 401`
- V5: `PASS: /auth/login is public`
- V6: `{"status": "ok", "env": "dev"}`
- V7: `PASS: circulars route removed`
- V8: `PASS: on_event removed`
- V9: `PASS: email_validator available`
- V10: `18`
