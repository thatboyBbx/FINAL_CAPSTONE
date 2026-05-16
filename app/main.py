"""
app/main.py
===========
FastAPI application factory for InsureIntel Zimbabwe.

Removed from live registration (kept on disk for training pipelines):
  - circulars module  (data used for classifier training only)
  - zse module        (ZSE scraping is fragile; not needed for thesis demo)
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
from app.modules.clients.router import router as client_router
from app.modules.reports.router import router as reports_router
from app.modules.intel.settlement_router import router as settlement_router
from app.modules.chatbot.router import router as chatbot_router
from app.modules.compat_router import router as compat_router

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
import app.modules.csp.model               # noqa: F401
import app.modules.clients.model           # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown logic using the modern lifespan context manager."""
    # ── Startup ──────────────────────────────────────────────────────────
    setup_logging()
    Base.metadata.create_all(bind=engine)

    try:
        from app.infrastructure.scrapers.scraper_scheduler import start_scheduler
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

    # Audit trail middleware
    from app.modules.audit.audit_middleware import AuditMiddleware
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
