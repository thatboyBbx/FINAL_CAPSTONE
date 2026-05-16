"""
IPEC Scraper — downloads quarterly insurance industry reports from ipec.co.zw,
extracts financial and claims data, and upserts into FinancialSnapshot + ClaimsMetrics.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, date
from typing import Optional

from sqlalchemy.orm import Session

from app.infrastructure.scrapers.base_scraper import BaseScraper, ScraperResult
from app.infrastructure.scrapers.scraper_utils import (
    extract_text_from_pdf,
    extract_tables_from_pdf,
    clean_financial_text,
    parse_usd_value,
    parse_percentage,
    find_insurer_mentions,
)

logger = logging.getLogger(__name__)

IPEC_REPORTS_URL = "https://ipec.co.zw/short-term-insurance-reports/"
IPEC_LIFE_URL    = "https://ipec.co.zw/life-insurance-reports/"


class IPECScraper(BaseScraper):
    """
    Downloads IPEC quarterly PDF reports, parses insurer-level financial tables,
    and upserts FinancialSnapshot + ClaimsMetrics rows.
    """

    scraper_name = "ipec"

    def run(self, db: Session) -> ScraperResult:
        run_id = self.log_run_start(db)
        result = ScraperResult(run_id=run_id)

        try:
            insurer_names = self._get_insurer_names(db)
            pdf_links = self._discover_pdf_links()

            for url, period_label in pdf_links:
                if self._already_processed(db, url):
                    logger.info("[ipec] skipping already-processed PDF: %s", url)
                    continue
                try:
                    ins, upd = self._process_pdf(db, url, period_label, insurer_names, run_id)
                    result.records_inserted += ins
                    result.records_updated  += upd
                except Exception as exc:
                    msg = f"PDF {url}: {exc}"
                    logger.warning("[ipec] %s", msg)
                    result.errors.append(msg)

            status = "partial" if result.errors else "success"
            result.status = status
            self.log_run_complete(db, run_id, status, result.records_inserted, result.records_updated,
                                  "; ".join(result.errors) if result.errors else None)
        except Exception as exc:
            logger.error("[ipec] fatal error: %s", exc, exc_info=True)
            result.status = "failed"
            result.errors.append(str(exc))
            self.log_run_complete(db, run_id, "failed", 0, 0, str(exc))

        return result

    # ── Discovery ─────────────────────────────────────────────────────────────

    def _discover_pdf_links(self) -> list[tuple[str, str]]:
        """
        Fetch the IPEC reports page and return [(pdf_url, period_label)] for
        short-term and life PDFs found.
        """
        results: list[tuple[str, str]] = []
        for base_url in [IPEC_REPORTS_URL, IPEC_LIFE_URL]:
            try:
                resp = self._fetch_with_retry(base_url)
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if ".pdf" in href.lower():
                        full_url = href if href.startswith("http") else f"https://ipec.co.zw{href}"
                        label = self._infer_period_label(href)
                        results.append((full_url, label))
            except Exception as exc:
                logger.warning("[ipec] could not fetch report index %s: %s", base_url, exc)
        return results

    def _infer_period_label(self, url: str) -> str:
        """Try to extract a period label like 'Q3_2024' from the PDF filename."""
        url_lower = url.lower()
        # Match patterns like Q3-2024, Q3_2024, 2024Q3, third-quarter-2024
        m = re.search(r"q([1-4])[-_]?(\d{4})", url_lower)
        if m:
            return f"Q{m.group(1)}_{m.group(2)}"
        m = re.search(r"(\d{4})[-_]?q([1-4])", url_lower)
        if m:
            return f"Q{m.group(2)}_{m.group(1)}"
        # Annual
        m = re.search(r"annual[-_]?(\d{4})|(\d{4})[-_]?annual", url_lower)
        if m:
            year = m.group(1) or m.group(2)
            return f"Annual_{year}"
        # Fallback: extract any 4-digit year
        m = re.search(r"(\d{4})", url)
        if m:
            return f"Q?_{m.group(1)}"
        return "unknown"

    # ── Processing ────────────────────────────────────────────────────────────

    def _process_pdf(
        self,
        db: Session,
        pdf_url: str,
        period_label: str,
        insurer_names: list[str],
        run_id: int,
    ) -> tuple[int, int]:
        """Download, parse, and upsert one PDF. Returns (inserted, updated)."""
        logger.info("[ipec] processing %s (period=%s)", pdf_url, period_label)
        resp = self._fetch_with_retry(pdf_url)
        pdf_bytes = resp.content

        # Try table extraction first, fall back to raw text
        tables = extract_tables_from_pdf(pdf_bytes)
        raw_text = extract_text_from_pdf(pdf_bytes)
        raw_text = clean_financial_text(raw_text)

        records = self.parse_financial_data(raw_text)

        # Supplement with table-derived data
        for tbl in tables:
            records.extend(self._parse_table(tbl, insurer_names))

        # De-duplicate by insurer name (keep richest record)
        merged = self._merge_records(records)

        inserted = updated = 0
        for rec in merged:
            ins_id = self._resolve_insurer_id(db, rec.get("insurer_name", ""))
            if not ins_id:
                continue
            i, u = self._upsert_financial(db, ins_id, period_label, rec, run_id)
            inserted += i
            updated  += u
            if rec.get("complaints_count") is not None:
                i2, u2 = self._upsert_claims(db, ins_id, period_label, rec)
                inserted += i2
                updated  += u2

        db.commit()
        return inserted, updated

    # ── Parsing ───────────────────────────────────────────────────────────────

    def parse_financial_data(self, raw_text: str) -> list[dict]:
        """
        Extract financial rows from raw PDF text using regex heuristics.
        Looks for lines that contain an insurer name followed by numeric values.
        """
        records: list[dict] = []
        lines = raw_text.split("\n")
        for i, line in enumerate(lines):
            # Skip header/footer lines
            if len(line.strip()) < 5:
                continue
            # Look for lines with at least 2 numbers that could be financial data
            numbers = re.findall(r"[\d,]+(?:\.\d+)?", line)
            if len(numbers) < 2:
                continue
            # Try to find a known contextual keyword suggesting this is a data row
            context = " ".join(lines[max(0, i-5):i]).lower()
            if any(kw in context for kw in ["premium", "revenue", "capital", "asset", "claim"]):
                records.append({"_raw_line": line, "_numbers": numbers})

        return records

    def _parse_table(self, table: list[list[str]], insurer_names: list[str]) -> list[dict]:
        """
        Parse a pdfplumber table into financial record dicts.
        Identifies header row, then maps columns to known field names.
        """
        if not table or len(table) < 2:
            return []

        header = [str(c).lower().strip() for c in table[0]]
        records: list[dict] = []

        col_map = self._map_columns(header)
        if not col_map:
            return []

        for row in table[1:]:
            rec: dict = {}
            for field_name, col_idx in col_map.items():
                if col_idx < len(row):
                    val_str = str(row[col_idx]).strip()
                    if field_name in ("insurer_name",):
                        rec[field_name] = val_str
                    elif field_name == "market_share_pct":
                        rec[field_name] = parse_percentage(val_str)
                    else:
                        rec[field_name] = parse_usd_value(val_str)
            if rec.get("insurer_name"):
                # Fuzzy match to canonical name
                matches = find_insurer_mentions(rec["insurer_name"], insurer_names, threshold=80)
                if matches:
                    rec["insurer_name"] = matches[0][0]
                records.append(rec)
        return records

    def _map_columns(self, header: list[str]) -> dict[str, int]:
        """Map financial field names to column indices based on header keywords."""
        mapping: dict[str, int] = {}
        field_keywords = {
            "insurer_name":             ["insurer", "company", "name", "entity"],
            "total_revenue_usd":        ["gross premium", "total premium", "total revenue", "gwp"],
            "insurance_revenue_usd":    ["net premium", "insurance revenue"],
            "total_assets_usd":         ["total assets"],
            "capital_position_usd":     ["capital", "equity"],
            "minimum_capital_requirement_usd": ["mcr", "minimum capital"],
            "claims_paid":              ["claims paid", "net claims"],
            "profit_after_tax_usd":     ["profit", "pat", "net income"],
            "market_share_pct":         ["market share"],
            "complaints_count":         ["complaints received"],
            "complaints_resolved_count":["complaints resolved"],
        }
        for field, keywords in field_keywords.items():
            for idx, col in enumerate(header):
                if any(kw in col for kw in keywords):
                    if field not in mapping:
                        mapping[field] = idx
                    break
        return mapping

    # ── Merge & upsert helpers ────────────────────────────────────────────────

    def _merge_records(self, records: list[dict]) -> list[dict]:
        """Merge multiple partial records for the same insurer name."""
        merged: dict[str, dict] = {}
        for rec in records:
            name = rec.get("insurer_name", "_unknown")
            if name not in merged:
                merged[name] = rec.copy()
            else:
                for k, v in rec.items():
                    if v is not None and merged[name].get(k) is None:
                        merged[name][k] = v
        return list(merged.values())

    def _upsert_financial(
        self, db: Session, insurer_id: int, period_label: str, rec: dict, run_id: int
    ) -> tuple[int, int]:
        from app.modules.financials.model import FinancialSnapshot
        existing = (
            db.query(FinancialSnapshot)
            .filter_by(insurer_id=insurer_id, period_label=period_label)
            .first()
        )
        if existing:
            for field, val in rec.items():
                if field.startswith("_") or field == "insurer_name" or val is None:
                    continue
                if hasattr(existing, field):
                    setattr(existing, field, val)
            return 0, 1
        else:
            snap = FinancialSnapshot(
                insurer_id=insurer_id,
                period_label=period_label,
                period_type="quarterly",
                data_source="ipec_report",
                scrape_run_id=run_id,
                **{k: v for k, v in rec.items()
                   if not k.startswith("_") and k != "insurer_name"
                   and hasattr(FinancialSnapshot, k) and v is not None},
            )
            db.add(snap)
            return 1, 0

    def _upsert_claims(
        self, db: Session, insurer_id: int, period_label: str, rec: dict
    ) -> tuple[int, int]:
        from app.modules.insurers.claims_model import ClaimsMetrics
        existing = (
            db.query(ClaimsMetrics)
            .filter_by(insurer_id=insurer_id, period_label=period_label)
            .first()
        )
        if existing:
            for field in ("complaints_count", "complaints_resolved_count", "complaints_resolution_rate",
                          "total_policies_count"):
                if rec.get(field) is not None:
                    setattr(existing, field, rec[field])
            return 0, 1
        else:
            # Compute resolution rate if possible
            resolved = rec.get("complaints_resolved_count")
            total_comp = rec.get("complaints_count")
            rate = None
            if resolved is not None and total_comp and total_comp > 0:
                rate = round(resolved / total_comp * 100, 2)
            cm = ClaimsMetrics(
                insurer_id=insurer_id,
                period_label=period_label,
                complaints_count=total_comp,
                complaints_resolved_count=resolved,
                complaints_resolution_rate=rate,
                data_source="ipec_report",
            )
            db.add(cm)
            return 1, 0

    # ── DB helpers ────────────────────────────────────────────────────────────

    def _get_insurer_names(self, db: Session) -> list[str]:
        from app.infrastructure.scrapers.scraper_utils import get_insurer_names
        return get_insurer_names(db)

    def _resolve_insurer_id(self, db: Session, name: str) -> int | None:
        if not name or name == "_unknown":
            return None
        from app.infrastructure.scrapers.scraper_utils import resolve_insurer_id
        return resolve_insurer_id(db, name, fuzzy=True)

    def _already_processed(self, db: Session, pdf_url: str) -> bool:
        from app.modules.insurers.scrape_model import ScrapeRun
        # We store processed PDF URLs as scraper_name = "ipec:<url>"
        tag = f"ipec:{pdf_url[:90]}"
        existing = (
            db.query(ScrapeRun)
            .filter(ScrapeRun.scraper_name == tag, ScrapeRun.status == "success")
            .first()
        )
        return existing is not None
