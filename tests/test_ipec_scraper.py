"""
Tests for the IPEC FSR-1 scraper depth and URL filter fixes.
Uses mocked HTTP responses — no real network calls.
"""
from unittest.mock import patch
from app.infrastructure.scrapers.ipec_fsr1_scraper import _is_fsr1_pdf_url, IPECScraperConfig


class TestFSR1URLFilter:
    """Verify that only valid FSR-1 PDF URLs pass the filter."""

    def test_accepts_fsr_pdf(self) -> None:
        assert _is_fsr1_pdf_url("https://www.ipec.co.zw/download-centre/fsr/FSR-Q3-2024.pdf") is True

    def test_accepts_financial_soundness_pdf(self) -> None:
        assert _is_fsr1_pdf_url("https://www.ipec.co.zw/financial-soundness-report-2023.pdf") is True

    def test_accepts_fsr1_in_path(self) -> None:
        assert _is_fsr1_pdf_url("https://www.ipec.co.zw/reports/fsr/annual-2022.pdf") is True

    def test_accepts_quarterly_report_pdf(self) -> None:
        assert _is_fsr1_pdf_url("https://www.ipec.co.zw/quarterly-report-q1-2024.pdf") is True

    def test_rejects_non_pdf(self) -> None:
        assert _is_fsr1_pdf_url("https://www.ipec.co.zw/download-centre/fsr/") is False

    def test_rejects_unrelated_pdf(self) -> None:
        assert _is_fsr1_pdf_url("https://www.ipec.co.zw/circulars/circular-2024.pdf") is False

    def test_rejects_image(self) -> None:
        assert _is_fsr1_pdf_url("https://www.ipec.co.zw/images/logo.png") is False

    def test_rejects_html_page(self) -> None:
        assert _is_fsr1_pdf_url("https://www.ipec.co.zw/download-centre/index.html") is False

    def test_rejects_empty_string(self) -> None:
        assert _is_fsr1_pdf_url("") is False


class TestScraperMaxDepth:
    """Verify depth limiting prevents runaway crawls."""

    def test_scraper_config_has_max_depth(self) -> None:
        # IPECScraperConfig must expose max_depth
        config = IPECScraperConfig()
        assert hasattr(config, "max_depth"), "IPECScraperConfig must have a max_depth attribute"
        assert config.max_depth == 2, "Default max_depth must be 2"

    def test_scraper_config_has_dry_run(self) -> None:
        config = IPECScraperConfig()
        assert hasattr(config, "dry_run"), "IPECScraperConfig must have a dry_run attribute"
        assert config.dry_run is False, "Default dry_run must be False"

    def test_scraper_config_dry_run_can_be_set(self) -> None:
        config = IPECScraperConfig(dry_run=True)
        assert config.dry_run is True

    def test_scraper_config_max_depth_can_be_overridden(self) -> None:
        config = IPECScraperConfig(max_depth=5)
        assert config.max_depth == 5

    def test_crawl_stops_at_max_depth(self) -> None:
        """_crawl called at depth >= max_depth must return empty list immediately."""
        from app.infrastructure.scrapers.ipec_fsr1_scraper import IPECFinancialScraper

        scraper = IPECFinancialScraper()
        # Call at depth == max_depth — should not make any HTTP calls
        with patch("httpx.get") as mock_get:
            result = scraper._crawl("https://www.ipec.co.zw/fsr/", depth=2, max_depth=2)
        assert result == [], "Should return empty list when depth >= max_depth"
        mock_get.assert_not_called()
