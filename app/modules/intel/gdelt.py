"""
GDELT 2.1 DOC API ingestion — fetches Zimbabwe insurance news.
Adapted for PROJ_DEMO SQLAlchemy session pattern.
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

COUNTRY  = "Zimbabwe"
KEYWORDS = [
    "insurance", "insurer", "premium", "claim", "claims", "underwriting",
    "reinsurance", "microinsurance", "life insurance", "motor insurance",
    "health insurance", "funeral policy", "policyholder",
    "IPEC", "PRAZ", "Insurance Council of Zimbabwe",
    "Old Mutual", "First Mutual", "Zimre", "Fidelity Life",
    "Nyaradzo", "Zimnat", "CBZ Life", "Doves Life",
]

TOPIC_RULES: Dict[str, List[str]] = {
    "Regulation":    ["ipec", "praz", "statutory", "regulation", "compliance", "licence"],
    "Claims":        ["claim", "claims", "payout", "settlement", "complaint", "dispute"],
    "Premiums":      ["premium", "pricing", "rate", "tariff"],
    "Fraud":         ["fraud", "scam", "forgery"],
    "Health":        ["health insurance", "medical aid", "hospital"],
    "Motor":         ["motor insurance", "vehicle", "car insurance", "third party"],
    "Life":          ["life insurance", "funeral", "policyholder", "beneficiary"],
    "Innovation":    ["insurtech", "digital", "mobile", "automation"],
    "ZSE / Finance": ["stock exchange", "zse", "shares", "listed", "dividend", "earnings"],
}

# Insurer keyword detection (inline to avoid circular import)
_INSURER_KEYWORDS: Dict[str, List[str]] = {
    "Old Mutual Zimbabwe Ltd":       ["old mutual", "old mutual zimbabwe"],
    "First Mutual Holdings Ltd":     ["first mutual", "first mutual holdings", "fmhl"],
    "Zimre Holdings Ltd":            ["zimre", "zimre holdings"],
    "Fidelity Life Assurance Ltd":   ["fidelity life", "fidelity"],
    "Nyaradzo Life Assurance Co Ltd":["nyaradzo"],
    "Zimnat Life Assurance Co Ltd":  ["zimnat life", "zimnat"],
    "Zimnat Lion Insurance Co Ltd":  ["zimnat lion"],
    "CBZ Life Ltd":                  ["cbz life"],
    "Doves Life Assurance Co Ltd":   ["doves life", "doves"],
    "ZB Life Assurance Ltd":         ["zb life", "zb assurance"],
    "Nicoz Diamond Insurance Co Ltd":["nicoz diamond", "nicoz"],
    "Alliance Insurance Co Ltd":     ["alliance insurance"],
    "Cell Insurance Co Ltd":         ["cell insurance"],
    "Econet Life (Pvt) Ltd":         ["econet life"],
}

_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "Motor Vehicle (Comprehensive)": ["comprehensive", "motor comprehensive", "vehicle insurance"],
    "Motor Vehicle (3rd Party)":     ["third party", "3rd party", "tp insurance"],
    "Life":                          ["life insurance", "life assurance", "life policy"],
    "Health / Medical Aid":          ["medical aid", "health insurance", "hospital", "health cover"],
    "Funeral Policy":                ["funeral", "funeral policy", "burial society"],
    "Home / Buildings":              ["home insurance", "buildings insurance", "household"],
    "Property / Fire":               ["fire insurance", "property insurance", "commercial property"],
    "Agriculture / Crop":            ["agriculture", "crop insurance", "livestock"],
    "Marine":                        ["marine", "cargo insurance", "aviation"],
    "Public Liability":              ["public liability"],
    "Professional Indemnity":        ["professional indemnity", "pi insurance"],
    "Travel":                        ["travel insurance", "travel cover"],
}


def _detect_insurer(text: str):
    t = text.lower()
    for name, kws in _INSURER_KEYWORDS.items():
        if any(k in t for k in kws):
            return name
    return None


def _detect_type(text: str):
    t = text.lower()
    for itype, kws in _TYPE_KEYWORDS.items():
        if any(k in t for k in kws):
            return itype
    return None


def _normalize_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""


def _make_id(title: str, url: str) -> str:
    return hashlib.sha256(((title or "") + "|" + (url or "")).encode()).hexdigest()[:24]


def _classify_topics(text: str) -> List[str]:
    t = (text or "").lower()
    hits = [topic for topic, rules in TOPIC_RULES.items() if any(r in t for r in rules)]
    return hits or ["General Insurance"]


def _build_query() -> str:
    kw = " OR ".join([f'"{k}"' if " " in k else k for k in KEYWORDS[:14]])
    return f"({kw}) AND ({COUNTRY} OR Harare OR Bulawayo)"


def gdelt_search(query: str, start: datetime, end: datetime, max_records: int = 100) -> List[Dict[str, Any]]:
    """Query GDELT 2.1 DOC API. Returns list of article dicts."""
    try:
        import requests
        from dateutil import parser as dtparser  # noqa: F401
    except ImportError as e:
        logger.error("GDELT dependency missing: %s", e)
        return []

    params = {
        "query":          query,
        "mode":           "ArtList",
        "format":         "json",
        "maxrecords":     str(max_records),
        "startdatetime":  start.strftime("%Y%m%d%H%M%S"),
        "enddatetime":    end.strftime("%Y%m%d%H%M%S"),
        "formatdatetime": "true",
        "sort":           "HybridRel",
    }
    try:
        import requests as req
        r = req.get(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            params=params, timeout=30,
        )
        r.raise_for_status()
        return r.json().get("articles", []) or []
    except Exception as e:
        logger.warning("GDELT search error: %s", e)
        return []


def ingest(db, hours_back: int = 72, max_records: int = 100) -> Dict[str, Any]:
    """
    Fetch Zimbabwe insurance news from GDELT and store via SQLAlchemy session.
    Returns summary dict.
    """
    from app.modules.intel.repo import upsert_article

    try:
        from dateutil import parser as dtparser
    except ImportError:
        return {"error": "python-dateutil not installed", "inserted": 0, "skipped": 0}

    now   = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours_back)
    q     = _build_query()

    articles = gdelt_search(q, start, now, max_records)

    inserted = 0
    skipped  = 0

    for a in articles:
        title = a.get("title") or ""
        url   = a.get("url") or ""
        if not url:
            continue

        published_at = None
        if a.get("datetime"):
            try:
                published_at = dtparser.parse(a["datetime"]).astimezone(timezone.utc).isoformat()
            except Exception:
                pass

        text = f"{title} {a.get('snippet', '')}"

        row = {
            "id":           _make_id(title, url),
            "fetched_at":   now.isoformat(),
            "published_at": published_at,
            "title":        title,
            "url":          url,
            "domain":       _normalize_domain(url),
            "source_country": a.get("sourceCountry"),
            "snippet":      a.get("snippet") or "",
            "topics":       _classify_topics(text),
            "raw":          a,
            "insurer_name": _detect_insurer(text),
            "insurance_type": _detect_type(text),
        }

        if upsert_article(db, row):
            inserted += 1
        else:
            skipped += 1

    return {
        "query":    q,
        "fetched":  len(articles),
        "inserted": inserted,
        "skipped":  skipped,
        "window_hours": hours_back,
    }
