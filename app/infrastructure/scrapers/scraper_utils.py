"""
Shared scraper utilities — HTTP client, PDF/HTML extractors, value parsers,
insurer fuzzy matcher.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# ── Exchange rates ────────────────────────────────────────────────────────────
_RATES_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "exchange_rates.json")

def _load_rates() -> dict[str, float]:
    try:
        with open(_RATES_PATH) as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {"ZWG": 0.00377, "ZWL": 0.00083, "ZAR": 0.0545, "GBP": 1.27, "EUR": 1.09, "USD": 1.0}


_EXCHANGE_RATES: dict[str, float] = _load_rates()

# ── User agents ───────────────────────────────────────────────────────────────
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
]
_ua_cycle = 0


def _next_user_agent() -> str:
    global _ua_cycle
    ua = _USER_AGENTS[_ua_cycle % len(_USER_AGENTS)]
    _ua_cycle += 1
    return ua


# ── HTTP client ───────────────────────────────────────────────────────────────

def get_http_client() -> requests.Session:
    """Return a requests.Session with retries, User-Agent rotation, and 15s timeout."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": _next_user_agent(), "Accept-Language": "en-US,en;q=0.9"})
    return session


# ── PDF extraction ────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract all text from a PDF byte string using pdfplumber."""
    try:
        import io
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            parts = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    parts.append(text)
        return "\n".join(parts)
    except Exception as exc:
        logger.warning("PDF text extraction failed: %s", exc)
        return ""


def extract_tables_from_pdf(pdf_bytes: bytes) -> list[list[list[str]]]:
    """Return list of tables (each table is list of rows, each row is list of cell strings)."""
    try:
        import io
        import pdfplumber
        all_tables: list[list[list[str]]] = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                for tbl in (page.extract_tables() or []):
                    cleaned = [
                        [str(cell).strip() if cell else "" for cell in row]
                        for row in tbl
                    ]
                    if cleaned:
                        all_tables.append(cleaned)
        return all_tables
    except Exception as exc:
        logger.warning("PDF table extraction failed: %s", exc)
        return []


# ── HTML extraction ───────────────────────────────────────────────────────────

def extract_text_from_html(html: str) -> str:
    """Strip HTML tags and return clean text."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except Exception as exc:
        logger.warning("HTML text extraction failed: %s", exc)
        return ""


# ── Text cleaning ─────────────────────────────────────────────────────────────

def clean_financial_text(text: str) -> str:
    """Normalize whitespace, strip page headers/footers, collapse blank lines."""
    # Remove page numbers like "Page 1 of 12" or "- 3 -"
    text = re.sub(r"(?i)(page\s+\d+\s+of\s+\d+|- \d+ -|\f)", " ", text)
    # Collapse multiple spaces/tabs
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse more than 2 consecutive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Value parsers ─────────────────────────────────────────────────────────────

_MULTIPLIERS = {
    "billion": 1_000_000_000,
    "bn":      1_000_000_000,
    "million": 1_000_000,
    "mn":      1_000_000,
    "m":       1_000_000,
    "thousand": 1_000,
    "k":        1_000,
}

# Matches: optional currency prefix, number with optional commas/decimals, optional suffix
_MONEY_RE = re.compile(
    r"(?i)"
    r"(?P<currency>US\$|USD|ZWG|ZWL|ZAR|GBP|EUR|\$)?\s*"
    r"(?P<number>[\d,]+(?:\.\d+)?)\s*"
    r"(?P<suffix>billion|bn|million|mn|m|thousand|k)?",
    re.IGNORECASE,
)


def parse_usd_value(text: str) -> float | None:
    """
    Parse a monetary value string to USD float.

    Handles:
    - "US$153.97 million" → 153_970_000.0
    - "USD 268.42m"       → 268_420_000.0
    - "ZWG4.84 billion"   → 4_840_000_000 × ZWG/USD
    - "$239.42M"          → 239_420_000.0
    - "153,970,000"       → 153_970_000.0
    - "12.5" (bare)       → 12.5
    """
    if not text:
        return None
    text = text.strip().replace(",", "")
    m = _MONEY_RE.search(text)
    if not m:
        return None
    try:
        number = float(m.group("number"))
    except (TypeError, ValueError):
        return None

    suffix = (m.group("suffix") or "").lower()
    number *= _MULTIPLIERS.get(suffix, 1)

    currency = (m.group("currency") or "USD").upper().replace("$", "USD").replace("US", "USD")
    if currency not in ("USD", "$"):
        rate = _EXCHANGE_RATES.get(currency, 1.0)
        number *= rate

    return round(number, 2)


_PCT_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*%")


def parse_percentage(text: str) -> float | None:
    """Return first percentage found in text as a float (e.g. '45.3%' → 45.3)."""
    if not text:
        return None
    m = _PCT_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


# ── Insurer fuzzy matcher ─────────────────────────────────────────────────────

def get_insurer_names(db) -> list[str]:
    """Return all insurer names from the DB."""
    from app.modules.insurers.model import Insurer
    return [row.name for row in db.query(Insurer.name).all()]


def resolve_insurer_id(db, name: str, fuzzy: bool = True) -> "int | None":
    """
    Resolve insurer name to DB id. Optionally falls back to rapidfuzz matching
    (threshold 80) when an exact match is not found.
    """
    if not name:
        return None
    from app.modules.insurers.model import Insurer
    row = db.query(Insurer).filter(Insurer.name == name).first()
    if row:
        return row.id
    if not fuzzy:
        return None
    all_names = get_insurer_names(db)
    matches = find_insurer_mentions(name, all_names, threshold=80)
    if matches:
        row = db.query(Insurer).filter(Insurer.name == matches[0][0]).first()
        return row.id if row else None
    return None


def find_insurer_mentions(text: str, insurer_names: list[str], threshold: int = 85) -> list[tuple[str, int]]:
    """
    Find insurer names mentioned in *text* using rapidfuzz.

    Returns list of (canonical_name, score) sorted by score desc, deduplicated.
    threshold: minimum score (0-100) to accept as a match.
    """
    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        logger.warning("rapidfuzz not installed — returning empty insurer mentions")
        return []

    if not text or not insurer_names:
        return []

    # Split text into chunks (sentences / lines) to avoid false positives on long text
    chunks = re.split(r"[\n.!?;]", text)
    seen: dict[str, int] = {}

    for chunk in chunks:
        chunk = chunk.strip()
        if len(chunk) < 4:
            continue
        results = process.extract(chunk, insurer_names, scorer=fuzz.partial_ratio, limit=3)
        for name, score, _ in results:
            if score >= threshold and name not in seen:
                seen[name] = score

    return sorted(seen.items(), key=lambda x: x[1], reverse=True)
