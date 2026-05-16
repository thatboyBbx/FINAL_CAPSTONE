"""
Abstract base scraper — defines ScraperResult dataclass, BaseScraper ABC,
and shared DB logging helpers.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class ScraperResult:
    """Returned by every scraper's run() method."""
    run_id: int | None = None
    status: str = "success"          # running / success / partial / failed
    records_inserted: int = 0
    records_updated: int = 0
    errors: list[str] = field(default_factory=list)


class BaseScraper(ABC):
    """
    Abstract base class for all IPEC / ZSE / News scrapers.

    Subclasses must implement:
        run(db) -> ScraperResult
        parse_financial_data(raw_text) -> list[dict]
    """

    scraper_name: str = "base"

    # ── Lifecycle helpers ─────────────────────────────────────────────────────

    def log_run_start(self, db: Session) -> int:
        """Insert a ScrapeRun row with status='running'; return its id."""
        from app.modules.insurers.scrape_model import ScrapeRun
        run = ScrapeRun(
            scraper_name=self.scraper_name,
            run_started_at=datetime.utcnow(),
            status="running",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        logger.info("[%s] run started — id=%d", self.scraper_name, run.id)
        return run.id

    def log_run_complete(
        self,
        db: Session,
        run_id: int,
        status: str,
        inserted: int,
        updated: int,
        error: str | None = None,
    ) -> None:
        """Update ScrapeRun row with final status and counts."""
        from app.modules.insurers.scrape_model import ScrapeRun
        run = db.query(ScrapeRun).filter(ScrapeRun.id == run_id).first()
        if run:
            run.status = status
            run.run_completed_at = datetime.utcnow()
            run.records_inserted = inserted
            run.records_updated = updated
            run.error_message = error
            db.commit()
        logger.info(
            "[%s] run %d completed — status=%s inserted=%d updated=%d",
            self.scraper_name, run_id, status, inserted, updated,
        )

    # ── HTTP helper ───────────────────────────────────────────────────────────

    def _fetch_with_retry(self, url: str, **kwargs) -> Any:
        """
        Fetch *url* with up to 3 attempts and exponential backoff (base 2s).
        Returns requests.Response or raises on final failure.
        """
        from app.infrastructure.scrapers.scraper_utils import get_http_client
        session = get_http_client()
        kwargs.setdefault("timeout", 15)

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = session.get(url, **kwargs)
                resp.raise_for_status()
                return resp
            except Exception as exc:
                last_exc = exc
                wait = 2 ** attempt
                logger.warning(
                    "[%s] fetch attempt %d failed for %s: %s — retrying in %ds",
                    self.scraper_name, attempt + 1, url, exc, wait,
                )
                time.sleep(wait)
        raise last_exc  # type: ignore[misc]

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def run(self, db: Session) -> ScraperResult:
        """Execute the full scrape pipeline. Must log start/complete via helpers."""

    @abstractmethod
    def parse_financial_data(self, raw_text: str) -> list[dict]:
        """Parse raw extracted text into a list of financial record dicts."""
