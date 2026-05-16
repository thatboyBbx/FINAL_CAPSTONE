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
from pathlib import Path
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

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
        download_dir: Directory where PDFs are saved.  Defaults to a temp dir.
        request_delay: Seconds to wait between HTTP requests (polite scraping).
    """

    DOWNLOAD_CENTRE_URL = "https://www.ipec.co.zw/download-centre/"

    def __init__(
        self,
        download_dir: str | None = None,
        request_delay: float = 1.0,
    ) -> None:
        self._download_dir = Path(download_dir) if download_dir else Path(tempfile.gettempdir()) / "ipec_fsr1"
        self._download_dir.mkdir(parents=True, exist_ok=True)
        self._delay = request_delay

    def scrape_download_centre(self) -> list[str]:
        """
        Fetch the IPEC download centre page and return all relevant PDF URLs.

        Returns:
            List of absolute PDF URLs whose link text or filename matches FSR keywords.
            Returns empty list on network/parsing failure.
        """
        try:
            import httpx
            from bs4 import BeautifulSoup

            logger.info("Fetching IPEC download centre: %s", self.DOWNLOAD_CENTRE_URL)
            response = httpx.get(self.DOWNLOAD_CENTRE_URL, timeout=30.0, follow_redirects=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            pdf_urls: list[str] = []

            for a_tag in soup.find_all("a", href=True):
                href: str = a_tag["href"]
                link_text: str = a_tag.get_text(strip=True).lower()
                filename = Path(urlparse(href).path).name.lower()

                is_pdf = href.lower().endswith(".pdf") or "pdf" in href.lower()
                is_relevant = any(kw in link_text or kw in filename for kw in _RELEVANT_KEYWORDS)

                if is_pdf and is_relevant:
                    abs_url = urljoin(self.DOWNLOAD_CENTRE_URL, href)
                    pdf_urls.append(abs_url)
                    logger.debug("Found FSR PDF: %s", abs_url)

            logger.info("Found %d relevant PDF links on IPEC download centre", len(pdf_urls))
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
