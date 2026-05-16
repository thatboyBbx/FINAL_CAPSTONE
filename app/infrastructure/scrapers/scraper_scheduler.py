"""
Scraper scheduler — APScheduler BackgroundScheduler with cron jobs for
IPEC (monthly) and News (daily) scrapers.

Called from app/main.py startup event via start_scheduler().
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_scheduler = None


def start_scheduler() -> None:
    """Initialize and start the APScheduler BackgroundScheduler."""
    global _scheduler

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("apscheduler not installed — scraper scheduler disabled")
        return

    if _scheduler is not None and _scheduler.running:
        logger.info("Scheduler already running — skipping start")
        return

    _scheduler = BackgroundScheduler(timezone="Africa/Harare")

    # IPEC: 1st of month at 06:00 Africa/Harare
    _scheduler.add_job(
        _run_ipec,
        CronTrigger(day=1, hour=6, minute=0, timezone="Africa/Harare"),
        id="ipec_monthly",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # News: every day at 07:00 Africa/Harare
    _scheduler.add_job(
        _run_news,
        CronTrigger(hour=7, minute=0, timezone="Africa/Harare"),
        id="news_daily",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Retraining: 1st of month at 03:00 Africa/Harare (Advancement 3)
    _scheduler.add_job(
        _run_retraining,
        CronTrigger(day=1, hour=3, minute=0, timezone="Africa/Harare"),
        id="retraining_monthly",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Expiry alerts: every day at 08:00 Africa/Harare (Advancement 6)
    _scheduler.add_job(
        _run_expiry_alerts,
        CronTrigger(hour=8, minute=0, timezone="Africa/Harare"),
        id="expiry_alerts_daily",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.start()
    logger.info("Scraper scheduler started (IPEC monthly, News daily, retraining monthly, expiry alerts daily)")

    # Startup check: if no successful run in the last 7 days, trigger news once
    _trigger_startup_check()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scraper scheduler stopped")


def run_scraper_now(scraper_name: str) -> int:
    """
    Trigger a named scraper immediately (called from API endpoint).
    Returns the ScrapeRun id.
    """
    if scraper_name not in _SCRAPER_CLASSES:
        raise ValueError(f"Unknown scraper: {scraper_name!r}")
    import importlib
    from app.core.db import SessionLocal
    module_path, class_name = _SCRAPER_CLASSES[scraper_name].split(":")
    db = SessionLocal()
    try:
        module = importlib.import_module(module_path)
        result = getattr(module, class_name)().run(db)
        return result.run_id or 0
    finally:
        db.close()


_SCRAPER_CLASSES = {
    "ipec": "app.infrastructure.scrapers.ipec_scraper:IPECScraper",
    "news": "app.infrastructure.scrapers.news_scraper:NewsScraper",
}


# ── Job functions (run in background threads) ─────────────────────────────────

def _run_scraper(name: str) -> None:
    """Generic job runner — imports and runs the named scraper class."""
    module_path, class_name = _SCRAPER_CLASSES[name].split(":")
    logger.info("[scheduler] starting %s scraper job", name)
    from app.core.db import SessionLocal
    import importlib
    db = SessionLocal()
    try:
        module = importlib.import_module(module_path)
        scraper = getattr(module, class_name)()
        result = scraper.run(db)
        logger.info("[scheduler] %s done — inserted=%d updated=%d status=%s",
                    name, result.records_inserted, result.records_updated, result.status)
    except Exception as exc:
        logger.error("[scheduler] %s job error: %s", name, exc, exc_info=True)
    finally:
        db.close()


def _run_ipec() -> None:
    _run_scraper("ipec")


def _run_news() -> None:
    _run_scraper("news")


# ── Advancement 3: Monthly retraining job ─────────────────────────────────────

def _run_retraining() -> None:
    """Monthly job: retrain NER and risk models with accumulated feedback."""
    logger.info("[scheduler] starting monthly retraining job")
    from app.core.db import SessionLocal
    from app.modules.feedback.retraining_pipeline import RetrainingPipeline
    db = SessionLocal()
    try:
        result = RetrainingPipeline().run_full_retraining(db)
        logger.info("[scheduler] retraining complete: %s", result)
    except Exception as exc:
        logger.error("[scheduler] retraining job error: %s", exc, exc_info=True)
    finally:
        db.close()


# ── Advancement 6: Daily expiry alert job ────────────────────────────────────

def _run_expiry_alerts() -> None:
    """Daily job: send email notifications for policies expiring within 60 days."""
    logger.info("[scheduler] starting daily expiry alert job")
    from app.core.db import SessionLocal
    from app.modules.tracker.service import PolicyTrackerService
    db = SessionLocal()
    try:
        result = PolicyTrackerService().send_expiry_notifications(db)
        logger.info("[scheduler] expiry alerts sent: %s", result)
    except Exception as exc:
        logger.error("[scheduler] expiry alert job error: %s", exc, exc_info=True)
    finally:
        db.close()


def _trigger_startup_check() -> None:
    """If no successful scrape run in 7 days, trigger the news scraper once at startup."""
    try:
        from app.core.db import SessionLocal
        from app.modules.insurers.scrape_model import ScrapeRun
        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(days=7)
            recent = (
                db.query(ScrapeRun)
                .filter(ScrapeRun.status == "success", ScrapeRun.run_completed_at >= cutoff)
                .first()
            )
            if not recent:
                logger.info("[scheduler] no recent successful run — triggering startup news scrape")
                if _scheduler and _scheduler.running:
                    from datetime import timedelta as td
                    _scheduler.add_job(
                        _run_news,
                        "date",
                        run_date=datetime.now() + td(seconds=5),
                        id="news_startup",
                        replace_existing=True,
                    )
        finally:
            db.close()
    except Exception as exc:
        logger.warning("[scheduler] startup check failed: %s", exc)
