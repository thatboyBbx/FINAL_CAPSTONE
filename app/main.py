"""
app/main.py
===========
FastAPI application factory for InsureIntel Zimbabwe.

Removed from live registration (kept on disk for training pipelines):
  - circulars module  (data used for classifier training only)
  - zse module        (ZSE scraping is fragile; not needed for thesis demo)
"""
import logging
import threading
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.db import Base, engine, validate_db_connection
from app.core.logging import setup_logging
from app.core.rate_limit import limiter

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
from app.modules.clients.router import router as client_router
from app.modules.reports.router import router as reports_router
from app.modules.intel.settlement_router import router as settlement_router
from app.modules.chatbot.router import router as chatbot_router
from app.modules.compat_router import router as compat_router
from app.modules.jobs.router import router as jobs_router
from app.modules.embeddings.router import router as embeddings_router
from app.modules.rag_governance.router import router as rag_governance_router

# ── UI routers ─────────────────────────────────────────────────────────────
from app.ui.router import router as ui_router
from app.ui.extra_router import router as extra_ui_router
from app.ui.analytics_router import router as analytics_ui_router

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
import app.modules.csp.model               # noqa: F401
import app.modules.clients.model           # noqa: F401
import app.modules.compliance.model        # noqa: F401
import app.modules.jobs.model              # noqa: F401
import app.modules.embeddings.model        # noqa: F401
import app.modules.rag_governance.model   # noqa: F401  — registers RetrievalAuditLog
import app.modules.auth.token_store        # noqa: F401  — registers RefreshToken, AccessTokenBlacklist, UserRevocationFence

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown logic using the modern lifespan context manager."""
    # ── Startup ──────────────────────────────────────────────────────────
    setup_logging()
    validate_db_connection()
    Base.metadata.create_all(bind=engine)

    try:
        from app.infrastructure.scrapers.scraper_scheduler import start_scheduler
        start_scheduler()
        logger.info("Scraper scheduler started.")
    except Exception as exc:
        logger.warning("Scraper scheduler could not start: %s", exc)

    # ── In-process ingestion worker ───────────────────────────────────────
    _worker_stop: threading.Event = threading.Event()
    _worker_thread: threading.Thread | None = None
    if settings.auto_start_workers and settings.queue_backend == "sqlite":
        try:
            from app.workers.sqlite_worker import run_worker_thread
            _worker_thread = threading.Thread(
                target=run_worker_thread,
                kwargs={
                    "queue": "ingestion_queue",
                    "stop_event": _worker_stop,
                    "poll_interval": settings.worker_poll_interval,
                },
                name="ingestion-worker",
                daemon=True,
            )
            _worker_thread.start()
            logger.info("In-process ingestion worker started (AUTO_START_WORKERS=true).")
        except Exception as exc:
            logger.warning("In-process worker could not start: %s", exc)

    logger.info("InsureIntel Zimbabwe started — env=%s", settings.env)
    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    if _worker_thread is not None and _worker_thread.is_alive():
        logger.info("Stopping in-process ingestion worker...")
        _worker_stop.set()
        _worker_thread.join(timeout=30)
        if _worker_thread.is_alive():
            logger.warning("Ingestion worker thread did not stop within 30 s.")
        else:
            logger.info("Ingestion worker stopped cleanly.")
    logger.info("InsureIntel Zimbabwe shutting down.")


_error_templates = Jinja2Templates(directory="app/ui/templates")


def _wants_html(request: Request) -> bool:
    """True when the client expects an HTML response (browser, not API call)."""
    if request.url.path.startswith("/api"):
        return False
    accept = request.headers.get("accept", "")
    return "text/html" in accept or "application/xhtml" in accept


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Static files (CSS, JS, images)
    app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")

    # UI routes (HTML pages — served first)
    app.include_router(ui_router)
    app.include_router(extra_ui_router)
    app.include_router(analytics_ui_router)

    # Auth (public — no JWT dependency on these)
    app.include_router(auth_router)

    # Protected API routes (JWT enforced via router-level dependencies)
    app.include_router(documents_router, prefix="/api")
    app.include_router(insurers_router)
    app.include_router(financials_router)
    app.include_router(news_router, prefix="/api")
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
    app.include_router(chatbot_router)
    app.include_router(compat_router)
    app.include_router(jobs_router)
    app.include_router(embeddings_router)
    app.include_router(rag_governance_router)

    # Audit trail middleware
    from app.modules.audit.audit_middleware import AuditMiddleware
    app.add_middleware(AuditMiddleware)

    @app.get("/health")
    def health():
        return {"status": "ok", "env": settings.env}

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        if not _wants_html(request):
            return JSONResponse(
                {"error": "Not found", "path": str(request.url.path)},
                status_code=404,
            )
        return _error_templates.TemplateResponse(
            "errors/404.html",
            {"request": request, "detail": None},
            status_code=404,
        )

    @app.exception_handler(403)
    async def forbidden_handler(request: Request, exc):
        if not _wants_html(request):
            return JSONResponse({"error": "Forbidden"}, status_code=403)
        detail = getattr(exc, "detail", None)
        required_role = getattr(exc, "required_role", None)
        return _error_templates.TemplateResponse(
            "errors/403.html",
            {"request": request, "detail": detail, "required_role": required_role},
            status_code=403,
        )

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc):
        logger.error("500 on %s: %s", request.url.path, exc)
        if not _wants_html(request):
            return JSONResponse(
                {"error": "Internal server error. Please try again."},
                status_code=500,
            )
        return _error_templates.TemplateResponse(
            "errors/500.html",
            {"request": request, "detail": None},
            status_code=500,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled on %s: %s", request.url.path, exc, exc_info=True)
        if not _wants_html(request):
            return JSONResponse({"error": "An unexpected error occurred."}, status_code=500)
        return _error_templates.TemplateResponse(
            "errors/500.html",
            {"request": request, "detail": None},
            status_code=500,
        )

    return app


app = create_app()
