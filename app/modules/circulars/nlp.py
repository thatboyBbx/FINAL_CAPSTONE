"""
NLP analysis pipeline for regulatory circulars.

Extracts:
- Named entities (insurer names, dates, monetary amounts, regulatory references)
- Risk signals and compliance keywords
- Circular category classification features
- Structured risk indicators for ML integration

No external NLP libraries required — pure regex + rule-based extraction.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Entity patterns (Zimbabwe / IPEC insurance regulatory context)
# ---------------------------------------------------------------------------

_DATE_PATTERNS = [
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    r"\b(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},?\s+\d{4}\b",
    r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b",
]

_MONEY_PATTERNS = [
    r"USD?\s*[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand))?\b",
    r"ZWL?\s*[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand))?\b",
    r"\$\s*[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand))?\b",
    r"ZW\$\s*[\d,]+(?:\.\d+)?",
]

_CIRCULAR_REF_PATTERNS = [
    r"\bIPEC[/\s-]*\d+[/\s-]*\d+\b",
    r"\bCircular\s+No\.?\s*\d+\b",
    r"\bDirective\s+No\.?\s*\d+\b",
    r"\bSection\s+\d+\s+of\s+the\b",
    r"\bActuarial\s+Circular\b",
    r"\bSolvency\s+(?:Margin|Directive|Framework)\b",
]

_INSURER_INDICATORS = [
    r"\b[\w\s]+(?:Insurance|Assurance|Life|Reinsurance)\s+(?:Company|Corporation|Ltd|Limited|Group)\b",
    r"\b[\w\s]+(?:Mutual|Cooperative)\s+(?:Insurance|Assurance)\b",
]

# ---------------------------------------------------------------------------
# Risk keyword lexicons
# ---------------------------------------------------------------------------

RISK_KEYWORDS: dict[str, list[str]] = {
    "compliance": [
        "comply", "compliance", "non-compliance", "deadline", "mandatory",
        "required", "must", "shall", "directive", "obligation", "penalty",
        "sanction", "licence revocation", "suspension",
    ],
    "financial_stress": [
        "solvency", "insolvency", "capital adequacy", "reserve deficiency",
        "liquidity", "shortfall", "undercapitalized", "winding up",
        "receivership", "statutory fund", "reinsurance cession",
    ],
    "claims": [
        "claims", "settlement", "payout", "outstanding claims",
        "claims ratio", "loss ratio", "incurred", "claims reserve",
        "claims backlog", "claimant", "compensation",
    ],
    "regulatory": [
        "IPEC", "regulation", "regulatory", "statutory", "commissioner",
        "insurance act", "pension act", "microinsurance", "supervision",
        "examination", "inspection", "directive", "circular",
    ],
    "market_conduct": [
        "mis-selling", "unfair treatment", "consumer protection",
        "policyholder", "disclosure", "transparency", "intermediary",
        "broker", "agent commission",
    ],
}

CATEGORY_SIGNATURES: dict[str, list[str]] = {
    "solvency_directive":    ["solvency", "capital", "minimum capital requirement", "mcr", "scr"],
    "claims_circular":       ["claims", "settlement", "payout", "loss ratio", "claims ratio"],
    "compliance_notice":     ["comply", "compliance", "deadline", "mandatory", "non-compliance"],
    "financial_reporting":   ["reporting", "return", "quarterly", "annual", "financial statement"],
    "market_conduct":        ["mis-selling", "consumer", "policyholder", "disclosure", "broker"],
    "general_notice":        [],   # fallback
}

RISK_WEIGHT: dict[str, float] = {
    "compliance":      3.0,
    "financial_stress": 4.0,
    "claims":          2.5,
    "regulatory":      2.0,
    "market_conduct":  1.5,
}


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class CircularNLPResult:
    # Entities
    dates: list[str] = field(default_factory=list)
    monetary_values: list[str] = field(default_factory=list)
    regulatory_refs: list[str] = field(default_factory=list)
    insurer_mentions: list[str] = field(default_factory=list)

    # Risk keyword counts per category
    keyword_counts: dict[str, int] = field(default_factory=dict)

    # Overall risk signals
    circular_risk_score: float = 0.0
    predicted_category: str = "general_notice"
    category_confidence: float = 0.0

    # Summary counts (for ML feature vector)
    compliance_signal: int = 0
    financial_stress_signal: int = 0
    claims_signal: int = 0
    regulatory_signal: int = 0
    market_conduct_signal: int = 0
    total_risk_signals: int = 0

    def to_feature_dict(self) -> dict[str, Any]:
        return {
            "circular_risk_score":       round(self.circular_risk_score, 4),
            "compliance_signal":         self.compliance_signal,
            "financial_stress_signal":   self.financial_stress_signal,
            "claims_signal":             self.claims_signal,
            "regulatory_signal":         self.regulatory_signal,
            "market_conduct_signal":     self.market_conduct_signal,
            "total_risk_signals":        self.total_risk_signals,
            "monetary_mentions":         len(self.monetary_values),
            "date_mentions":             len(self.dates),
            "regulatory_ref_count":      len(self.regulatory_refs),
        }


# ---------------------------------------------------------------------------
# Main analyser class
# ---------------------------------------------------------------------------

class CircularNLPAnalyser:
    """
    Rule-based NLP analysis of insurance regulatory circulars.
    Extracts entities, classifies category, and computes risk signals.
    """

    def analyse(self, text: str) -> CircularNLPResult:
        lower = text.lower()
        result = CircularNLPResult()

        # --- Entity extraction ---
        result.dates = self._extract_patterns(text, _DATE_PATTERNS)
        result.monetary_values = self._extract_patterns(text, _MONEY_PATTERNS)
        result.regulatory_refs = self._extract_patterns(text, _CIRCULAR_REF_PATTERNS)
        result.insurer_mentions = self._extract_patterns(text, _INSURER_INDICATORS)

        # --- Keyword counting ---
        for category, keywords in RISK_KEYWORDS.items():
            count = sum(
                len(re.findall(rf"\b{re.escape(kw)}\b", lower))
                for kw in keywords
            )
            result.keyword_counts[category] = count

        result.compliance_signal      = result.keyword_counts.get("compliance", 0)
        result.financial_stress_signal = result.keyword_counts.get("financial_stress", 0)
        result.claims_signal          = result.keyword_counts.get("claims", 0)
        result.regulatory_signal      = result.keyword_counts.get("regulatory", 0)
        result.market_conduct_signal  = result.keyword_counts.get("market_conduct", 0)
        result.total_risk_signals     = sum(result.keyword_counts.values())

        # --- Risk score ---
        score = 0.0
        for cat, count in result.keyword_counts.items():
            score += RISK_WEIGHT.get(cat, 1.0) * count
        # Normalise to 0-10 scale
        result.circular_risk_score = min(round(score / max(len(text.split()) / 100, 1), 4), 10.0)

        # --- Category classification ---
        result.predicted_category, result.category_confidence = self._classify_category(lower)

        return result

    # ------------------------------------------------------------------
    def _extract_patterns(self, text: str, patterns: list[str]) -> list[str]:
        found = []
        for p in patterns:
            matches = re.findall(p, text, flags=re.IGNORECASE)
            found.extend(matches)
        # Deduplicate, preserve order
        seen: set[str] = set()
        unique = []
        for m in found:
            norm = m.strip()
            if norm.lower() not in seen:
                seen.add(norm.lower())
                unique.append(norm)
        return unique

    def _classify_category(self, lower_text: str) -> tuple[str, float]:
        scores: dict[str, int] = {}
        for cat, sigs in CATEGORY_SIGNATURES.items():
            if not sigs:
                scores[cat] = 0
                continue
            scores[cat] = sum(
                len(re.findall(rf"\b{re.escape(s)}\b", lower_text))
                for s in sigs
            )

        best_cat = max(scores, key=lambda c: scores[c])
        total = sum(scores.values()) or 1
        confidence = round(scores[best_cat] / total, 4) if scores[best_cat] > 0 else 0.0

        if scores[best_cat] == 0:
            best_cat = "general_notice"
            confidence = 0.0

        return best_cat, confidence
