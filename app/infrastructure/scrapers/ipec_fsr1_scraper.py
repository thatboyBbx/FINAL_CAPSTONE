"""
IPEC FSR-1 Scraper — fetches Financial Soundness Return PDFs from the IPEC download centre.

Strategy:
  1. Fetch the IPEC download centre page
  2. Extract all PDF links whose text or filename contains FSR / Financial Soundness /
     Quarterly Return
  3. Download each PDF to a local temp directory
  4. Deduplicates against existing InsurerFinancials rows (source_url match)

All exceptions are caught and logged — a failed scrape does not crash the refresh pipeline.
"""
from __future__ import annotations

import logging
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)


@dataclass
class IPECScraperConfig:
    """Configuration for the IPEC FSR-1 scraper."""
    base_url: str = "https://www.ipec.co.zw/download-centre"
    max_depth: int = 2          # Maximum directory recursion depth — prevents 374-dir runaway
    request_timeout: int = 15   # Seconds before a single request times out
    max_retries: int = 3        # Number of retry attempts per URL
    dry_run: bool = False        # If True, log actions but do not write to DB


def _is_fsr1_pdf_url(url: str) -> bool:
    """
    Return True only if the URL points to an FSR-1 quarterly report PDF.
    IPEC FSR-1 files follow the pattern: FSR*.pdf or Financial*Soundness*.pdf.
    Also accepts any .pdf in a path containing 'fsr' or 'financial-soundness'.
    """
    url_lower = url.lower()
    # Must end in .pdf
    if not url_lower.endswith(".pdf"):
        return False
    # Must be in an FSR-related path OR have FSR in the filename
    fsr_signals = ["fsr", "financial-soundness", "financial_soundness", "quarterly-report"]
    return any(signal in url_lower for signal in fsr_signals)


def _fetch_with_retry(
    url: str,
    session: object,
    max_retries: int = 3,
) -> object | None:
    """
    Fetch a URL with exponential backoff. Returns the Response or None if all retries fail.
    Works with both requests.Session and httpx.Client objects.
    """
    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=15)
            response.raise_for_status()
            return response
        except Exception as e:
            wait_seconds = 2 ** attempt  # 1s, 2s, 4s
            logger.warning(
                "IPEC scraper fetch attempt %d/%d failed for %s: %s. Retrying in %ds...",
                attempt + 1, max_retries, url, e, wait_seconds,
            )
            if attempt < max_retries - 1:
                time.sleep(wait_seconds)
    logger.error("IPEC scraper: all %d retries exhausted for %s", max_retries, url)
    return None

# Keywords that identify relevant PDF links on the IPEC download centre page
_RELEVANT_KEYWORDS = frozenset([
    "fsr", "financial soundness", "quarterly return", "fsr-1", "fsr1"
])

# Column alias map — handles FSR-1 format variations across different reporting periods
COLUMN_ALIAS_MAP: dict[str, str] = {
    # Solvency
    "total assets": "total_assets_usd",
    "assets (usd)": "total_assets_usd",
    "total liabilities": "total_liabilities_usd",
    "liabilities (usd)": "total_liabilities_usd",
    "solvency margin": "solvency_margin_usd",
    "free assets": "solvency_margin_usd",
    "solvency ratio": "solvency_ratio_pct",
    "solvency ratio (%)": "solvency_ratio_pct",
    # Claims
    "gross claims paid": "gross_claims_paid_usd",
    "claims paid": "gross_claims_paid_usd",
    "outstanding claims": "outstanding_claims_reserve",
    "outstanding claims reserve": "outstanding_claims_reserve",
    "ibnr": "ibnr_reserve_usd",
    "ibnr provisions": "ibnr_reserve_usd",
    "claims reserves": "total_claims_reserves_usd",
    "total claims reserves": "total_claims_reserves_usd",
    "claims ratio": "claims_ratio_pct",
    "claims ratio (%)": "claims_ratio_pct",
    # Liquidity
    "current assets": "current_assets_usd",
    "current liabilities": "current_liabilities_usd",
    "liquidity ratio": "liquidity_ratio",
    "liquid assets": "liquid_assets_usd",
    "cash and equivalents": "liquid_assets_usd",
    # Premiums
    "gross premiums written": "gross_premiums_written_usd",
    "gross written premium": "gross_premiums_written_usd",
    "gwp": "gross_premiums_written_usd",
    "net premiums earned": "net_premiums_earned_usd",
    "net earned premium": "net_premiums_earned_usd",
}


class IPECFinancialScraper:
    """
    Scrapes IPEC download centre and downloads FSR-1 PDFs for parsing.

    Args:
        download_dir:  Directory where PDFs are saved.  Defaults to a temp dir.
        request_delay: Seconds to wait between HTTP requests (polite scraping).
        config:        Optional IPECScraperConfig. Defaults to IPECScraperConfig().
    """

    DOWNLOAD_CENTRE_URL = "https://www.ipec.co.zw/download-centre/"

    def __init__(
        self,
        download_dir: str | None = None,
        request_delay: float = 1.0,
        config: IPECScraperConfig | None = None,
        dry_run: bool = False,
    ) -> None:
        self._download_dir = Path(download_dir) if download_dir else Path(tempfile.gettempdir()) / "ipec_fsr1"
        self._download_dir.mkdir(parents=True, exist_ok=True)
        self._delay = request_delay
        self.config = config or IPECScraperConfig(dry_run=dry_run)

    def _crawl(
        self,
        url: str,
        depth: int = 0,
        max_depth: int | None = None,
    ) -> list[str]:
        """
        Recursively crawl a directory page and collect FSR-1 PDF URLs.
        The max_depth guard prevents the 374-directory runaway observed in production.

        Args:
            url:       The page to crawl.
            depth:     Current recursion depth (0 = root page).
            max_depth: Maximum depth to recurse; defaults to config.max_depth.

        Returns:
            List of absolute FSR-1 PDF URLs found at this depth and below.
        """
        effective_max = max_depth if max_depth is not None else self.config.max_depth

        # Guard: stop recursing beyond max depth to prevent runaway crawls
        if depth >= effective_max:
            logger.debug("_crawl: max_depth=%d reached at %s, stopping", effective_max, url)
            return []

        try:
            import httpx
            from bs4 import BeautifulSoup

            response = httpx.get(url, timeout=float(self.config.request_timeout), follow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            pdf_urls: list[str] = []
            subdir_urls: list[str] = []

            for a_tag in soup.find_all("a", href=True):
                href: str = a_tag["href"]
                abs_url = urljoin(url, href)

                if _is_fsr1_pdf_url(abs_url):
                    # Apply FSR-1 URL filter before adding
                    pdf_urls.append(abs_url)
                    logger.debug("_crawl depth=%d: accepted FSR-1 PDF: %s", depth, abs_url)
                elif abs_url.startswith(self.DOWNLOAD_CENTRE_URL) and not abs_url.lower().endswith(".pdf"):
                    # Potential subdirectory — recurse (depth check at next level)
                    subdir_urls.append(abs_url)

            # Recurse into subdirectories (depth incremented)
            for subdir_url in subdir_urls:
                pdf_urls.extend(self._crawl(subdir_url, depth=depth + 1, max_depth=effective_max))

            return pdf_urls

        except Exception as exc:
            logger.error("_crawl failed at depth=%d for %s: %s", depth, url, exc)
            return []

    def scrape_download_centre(self, dry_run: bool | None = None) -> list[str]:
        """
        Fetch the IPEC download centre page and return all FSR-1 PDF URLs.
        Applies max_depth crawling and _is_fsr1_pdf_url filter on every URL.

        Args:
            dry_run: If True (or if config.dry_run is True), log actions but return results
                     without triggering any downloads. Defaults to config.dry_run.

        Returns:
            List of absolute FSR-1 PDF URLs. Returns empty list on failure.
        """
        effective_dry_run = dry_run if dry_run is not None else self.config.dry_run

        try:
            import httpx
            from bs4 import BeautifulSoup

            logger.info("Fetching IPEC download centre: %s", self.DOWNLOAD_CENTRE_URL)
            response = httpx.get(
                self.DOWNLOAD_CENTRE_URL,
                timeout=float(self.config.request_timeout),
                follow_redirects=True,
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            pdf_urls: list[str] = []

            for a_tag in soup.find_all("a", href=True):
                href: str = a_tag["href"]
                abs_url = urljoin(self.DOWNLOAD_CENTRE_URL, href)

                # Apply FSR-1 PDF filter — rejects non-PDF and unrelated PDFs
                if _is_fsr1_pdf_url(abs_url):
                    pdf_urls.append(abs_url)
                    logger.debug("Found FSR-1 PDF: %s", abs_url)

            if effective_dry_run:
                logger.info("[dry_run] Would process %d FSR-1 PDFs: %s", len(pdf_urls), pdf_urls)
            else:
                logger.info("Found %d FSR-1 PDF links on IPEC download centre", len(pdf_urls))

            return pdf_urls

        except ImportError as exc:
            logger.error("Missing dependency for scraping: %s. Install httpx + beautifulsoup4", exc)
            return []
        except Exception as exc:
            logger.error("scrape_download_centre failed: %s", exc, exc_info=True)
            return []

    def download_pdf(self, url: str, dest_dir: str | None = None) -> str | None:
        """
        Download a PDF to the local destination directory.

        Args:
            url:      Full URL of the PDF to download.
            dest_dir: Override download directory (defaults to self._download_dir).

        Returns:
            Local file path string on success, None on failure.
        """
        target_dir = Path(dest_dir) if dest_dir else self._download_dir
        filename = Path(urlparse(url).path).name or "ipec_document.pdf"
        dest_path = target_dir / filename

        if dest_path.exists():
            logger.info("PDF already downloaded: %s", dest_path)
            return str(dest_path)

        try:
            import httpx

            time.sleep(self._delay)
            logger.info("Downloading: %s → %s", url, dest_path)
            with httpx.stream("GET", url, timeout=60.0, follow_redirects=True) as resp:
                resp.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=8192):
                        f.write(chunk)
            logger.info("Download complete: %s (%d bytes)", dest_path, dest_path.stat().st_size)
            return str(dest_path)

        except Exception as exc:
            logger.error("download_pdf failed for %s: %s", url, exc, exc_info=True)
            return None

    def is_already_processed(self, source_url: str, db: object) -> bool:
        """
        Check whether a PDF has already been parsed into InsurerFinancials.

        Args:
            source_url: The URL of the PDF to check.
            db:         SQLAlchemy Session.

        Returns:
            True if a row with matching source_url already exists.
        """
        try:
            from app.modules.financials.model import InsurerFinancials

            exists = (
                db.query(InsurerFinancials)
                .filter(InsurerFinancials.source_url == source_url)
                .first()
            ) is not None
            return exists
        except Exception as exc:
            logger.error("is_already_processed check failed: %s", exc, exc_info=True)
            return False

    def infer_period(self, filename: str) -> tuple[int, int | None]:
        """
        Parse year and optional quarter from a PDF filename.

        Handles patterns such as:
          FSR1_Q3_2024.pdf         → (2024, 3)
          Annual_Returns_2023.pdf  → (2023, None)
          FSR_2024_Q2.pdf          → (2024, 2)
          20230930_FSR1.pdf        → (2023, None)

        Args:
            filename: Basename of the PDF file.

        Returns:
            (year, quarter) tuple.  Quarter is None for annual reports.
            Returns (0, None) if parsing fails.
        """
        name_lower = filename.lower()

        # Extract year (4-digit number between 2010 and 2030)
        year_match = re.search(r"\b(20[1-3]\d)\b", filename)
        year = int(year_match.group(1)) if year_match else 0

        # Extract quarter
        quarter: int | None = None
        q_match = re.search(r"[qQ]([1-4])", filename)
        if q_match:
            quarter = int(q_match.group(1))
        elif "annual" in name_lower or "year" in name_lower:
            quarter = None

        return year, quarter
