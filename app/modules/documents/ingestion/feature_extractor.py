"""
Convert a document (filename + extracted text) into structured features.
Used to build labelled training corpus from raw insurance circulars.
"""
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Category inference rules — ordered most-specific first
# ---------------------------------------------------------------------------
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("aml", [
        "aml", "aml-cft", "aml/cft", "anti-money laundering", "anti money laundering",
        "fiu", "financial intelligence unit", "financial sanctions",
        "targeted financial sanctions", "nra", "national risk assessment",
        "cft", "cpf", "counter proliferation",
    ]),
    ("settlement", [
        "settlement of claims", "settlement of claim", "claims settlement",
        "claim payment", "motor claims", "settlement days", "claims circular",
    ]),
    ("solvency", [
        "solvency capital", "capital requirement", "minimum capital", "own funds",
        "technical liabilities", "technical provisions", "ts 1", "ts 2", "ts 3",
        "ts 4", "ts 5", "ts 6", "risk based capital", "orsa",
        "overall risk", "eligible own funds", "underwriting risk",
        "market risk capital", "operational risk capital",
    ]),
    ("reinsurance", [
        "reinsurance", "reinsurers", "zicarp", "retrocession", "composite reinsurer",
        "non-life reinsurer",
    ]),
    ("microinsurance", [
        "microinsurance", "micro-insurance", "micro insurance", "micro insurance framework",
    ]),
    ("disclosure", [
        "market disclosure", "financial statements", "annual reporting",
        "annual publication", "ifrs 17", "quarterly return", "reporting requirements",
        "annual return", "industry feedback",
    ]),
    ("investment", [
        "offshore investment", "equities valuation", "properties valuation",
        "gold coin", "gold coin investment",
    ]),
    ("currency", [
        "currency changes", "currency of payment", "2024 currency", "zwg",
        "currency guideline", "payment of levies",
    ]),
    ("governance", [
        "corporate governance", "board charter", "risk management guideline",
        "governance guideline", "pension fund governance", "board of directors",
    ]),
    ("legislation", [
        "insurance act", "pensions and provident", "provident fund act",
        "statutory instrument", "s.i.", "chapter 24", "act [chapter",
    ]),
    ("compliance", [
        "compliance", "directive", "civil penalties", "administrative penalties",
        "self assessment", "compliance report", "section 64", "levy", "levies",
        "ipec levy",
    ]),
    ("risk_management", [
        "risk management", "supervisory intervention", "ladder of supervisory",
        "grs", "regulatory sandbox", "sandbox guidelines", "privacy statement",
    ]),
]

# Feature keyword sets
_SETTLEMENT_KW = ["settlement", "claim", "paid", "payment", "indemnity", "motor", "compensation"]
_AML_KW = ["aml", "money laundering", "terrorist financing", "sanctions", "fiu"]
_PENALTY_KW = ["penalty", "penalties", "fine", "civil penalty", "administrative penalty"]
_GOVERNANCE_KW = ["governance", "board", "director", "committee", "compliance officer"]
_RISK_KW = ["risk", "capital", "solvency", "reserve", "reinsurance", "actuarial"]


def _infer_category(filename: str, text: str) -> str:
    combined = (filename + " " + text[:3000]).lower()
    for category, keywords in CATEGORY_RULES:
        if any(kw in combined for kw in keywords):
            return category
    return "general"


def _infer_year(filepath: str, text: str) -> int | None:
    for year in range(2026, 2005, -1):
        if str(year) in filepath:
            return year
    m = re.search(r"\b(20\d{2})\b", text[:600])
    if m:
        return int(m.group(1))
    return None


def _infer_circular_number(filename: str) -> str | None:
    fn = filename.lower()
    m = re.search(r"circular\s*[#no.]*\s*(\d+)\s*of\s*(\d{4})", fn)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    m = re.search(r"circular[-_](\d+)[-_]of[-_](\d{4})", fn)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None


def _hits(text_lower: str, keywords: list[str]) -> int:
    return sum(1 for kw in keywords if kw in text_lower)


def extract_features(
    file_path: str | Path,
    text: str,
    source_label: str = "circulars",
) -> dict[str, Any]:
    """Return a flat feature dict for one document."""
    path = Path(file_path)
    filename = path.name
    text_lower = text.lower()
    word_count = len(text.split()) if text else 0

    return {
        "filename": filename,
        "filepath": str(path),
        "source": source_label,
        "category": _infer_category(filename, text),
        "year": _infer_year(str(path), text),
        "circular_number": _infer_circular_number(filename),
        "text": text[:8000],
        "text_length": len(text),
        "word_count": word_count,
        "extractable": word_count > 20,
        "has_settlement_mention": _hits(text_lower, _SETTLEMENT_KW) >= 2,
        "has_aml_mention": _hits(text_lower, _AML_KW) >= 1,
        "has_penalty_mention": _hits(text_lower, _PENALTY_KW) >= 1,
        "has_governance_mention": _hits(text_lower, _GOVERNANCE_KW) >= 2,
        "has_risk_mention": _hits(text_lower, _RISK_KW) >= 2,
    }
