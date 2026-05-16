"""
app/modules/compliance/service.py
===================================
Regulatory Compliance Checker for Zimbabwe Insurance Documents.

Checks insurance policy documents against mandatory clause requirements and
prohibited term rules derived from the Zimbabwe Insurance Act [Chapter 24:07]
and IPEC regulations.

Knowledge base files are loaded from:
    C:\\Users\\lenovo\\Desktop\\Scrapper\\kb\\mandatory_clauses.json
    C:\\Users\\lenovo\\Desktop\\Scrapper\\kb\\prohibited_terms.json
"""
import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_KB_ROOT = Path(r"C:\Users\lenovo\Desktop\Scrapper\kb")

_instance: "ComplianceChecker | None" = None


def get_compliance_checker() -> "ComplianceChecker":
    """Return (or create) the shared ComplianceChecker singleton."""
    global _instance
    if _instance is None:
        _instance = ComplianceChecker()
    return _instance


class ComplianceChecker:
    """
    Checks an insurance document's text for regulatory compliance.

    Scoring formula
    ---------------
    Mandatory clauses contribute 70 % of the score.
    Absence of prohibited terms contributes 30 % of the score.

    Status thresholds
    -----------------
    compliant     : score >= 90
    needs_review  : 70 <= score < 90
    non_compliant : score < 70
    """

    def __init__(self) -> None:
        self.mandatory_clauses: list[dict] = []
        self.prohibited_terms: list[dict] = []
        self._clause_patterns: dict[str, list[re.Pattern]] = {}
        self._term_patterns: dict[str, list[re.Pattern]] = {}
        self._load_knowledge_base()

    def _load_knowledge_base(self) -> None:
        mandatory_path = _KB_ROOT / "mandatory_clauses.json"
        prohibited_path = _KB_ROOT / "prohibited_terms.json"

        if mandatory_path.exists():
            with open(mandatory_path, encoding="utf-8") as f:
                data = json.load(f)
            self.mandatory_clauses = data.get("clauses", [])
            self._clause_patterns = {
                c["id"]: [
                    re.compile(p, re.IGNORECASE)
                    for p in c.get("patterns", [])
                ]
                for c in self.mandatory_clauses
            }
            logger.info(
                "ComplianceChecker: loaded %d mandatory clauses from %s",
                len(self.mandatory_clauses), mandatory_path,
            )
        else:
            logger.warning("ComplianceChecker: mandatory_clauses.json not found at %s", mandatory_path)

        if prohibited_path.exists():
            with open(prohibited_path, encoding="utf-8") as f:
                data = json.load(f)
            self.prohibited_terms = data.get("prohibited_terms", [])
            self._term_patterns = {
                t["id"]: [
                    re.compile(p, re.IGNORECASE)
                    for p in t.get("patterns", [])
                ]
                for t in self.prohibited_terms
            }
            logger.info(
                "ComplianceChecker: loaded %d prohibited terms from %s",
                len(self.prohibited_terms), prohibited_path,
            )
        else:
            logger.warning("ComplianceChecker: prohibited_terms.json not found at %s", prohibited_path)

    def check_compliance(
        self,
        document_text: str,
        document_type: str = "all",
    ) -> dict[str, Any]:
        """
        Run a full compliance check on the supplied document text.

        Parameters
        ----------
        document_text : str
            Plain text extracted from the insurance document.
        document_type : str
            One of 'motor', 'life', 'property', 'health', or 'all'.

        Returns
        -------
        dict with keys: compliance_score, status, mandatory_clauses,
                        prohibited_terms, recommendations
        """
        text_lower = document_text.lower()

        mandatory_result = self._check_mandatory_clauses(text_lower, document_type)
        prohibited_result = self._check_prohibited_terms(text_lower, document_text)
        score = self._calculate_score(mandatory_result, prohibited_result)
        status = self._determine_status(score)
        recommendations = self._build_recommendations(mandatory_result, prohibited_result, score)

        return {
            "compliance_score": round(score, 2),
            "status": status,
            "mandatory_clauses": mandatory_result,
            "prohibited_terms": prohibited_result,
            "recommendations": recommendations,
        }

    def _check_mandatory_clauses(
        self, text_lower: str, document_type: str
    ) -> dict[str, Any]:
        applicable = [
            c for c in self.mandatory_clauses
            if "all" in c.get("document_types", ["all"])
            or document_type in c.get("document_types", ["all"])
            or document_type == "all"
        ]

        found: list[dict] = []
        missing: list[dict] = []

        for clause in applicable:
            if self._clause_present(text_lower, clause):
                found.append({
                    "id": clause["id"],
                    "requirement": clause["requirement"],
                    "section": clause["section"],
                })
            else:
                missing.append({
                    "id": clause["id"],
                    "requirement": clause["requirement"],
                    "section": clause["section"],
                    "description": clause["description"],
                })

        return {
            "total_required": len(applicable),
            "found": len(found),
            "missing": missing,
            "present": found,
        }

    def _clause_present(self, text_lower: str, clause: dict) -> bool:
        for keyword in clause.get("keywords", []):
            if keyword in text_lower:
                return True
        for pattern in self._clause_patterns.get(clause["id"], []):
            if pattern.search(text_lower):
                return True
        return False

    def _check_prohibited_terms(
        self, text_lower: str, original_text: str
    ) -> dict[str, Any]:
        violations: list[dict] = []

        for term in self.prohibited_terms:
            for pattern in self._term_patterns.get(term["id"], []):
                match = pattern.search(text_lower)
                if match:
                    start = max(0, match.start() - 30)
                    end = min(len(original_text), match.end() + 30)
                    snippet = original_text[start:end].strip()
                    violations.append({
                        "term": term["term"],
                        "severity": term["severity"],
                        "reason": term["reason"],
                        "legal_reference": term["legal_reference"],
                        "matched_text": snippet,
                    })
                    break

        return {
            "found": len(violations),
            "violations": violations,
        }

    def _calculate_score(
        self,
        mandatory_result: dict,
        prohibited_result: dict,
    ) -> float:
        total = mandatory_result["total_required"]
        mandatory_ratio = (mandatory_result["found"] / total) if total > 0 else 1.0

        violation_count = prohibited_result["found"]
        prohibited_ratio = max(0.0, 1.0 - violation_count * 0.15)

        critical_count = sum(
            1 for v in prohibited_result["violations"] if v.get("severity") == "critical"
        )
        if critical_count > 0:
            prohibited_ratio = max(0.0, prohibited_ratio - critical_count * 0.1)

        return (mandatory_ratio * 70.0) + (prohibited_ratio * 30.0)

    @staticmethod
    def _determine_status(score: float) -> str:
        if score >= 90.0:
            return "compliant"
        if score >= 70.0:
            return "needs_review"
        return "non_compliant"

    def _build_recommendations(
        self,
        mandatory_result: dict,
        prohibited_result: dict,
        score: float,
    ) -> list[str]:
        recs: list[str] = []

        for clause in mandatory_result["missing"]:
            recs.append(
                f"Add '{clause['requirement']}' clause as required by {clause['section']}."
            )

        for violation in prohibited_result["violations"]:
            severity_label = violation["severity"].upper()
            recs.append(
                f"[{severity_label}] Remove or revise prohibited term "
                f"'{violation['term']}': {violation['reason']}"
            )

        if score < 70:
            recs.append(
                "This document has significant compliance gaps. "
                "Review against the Zimbabwe Insurance Act [Chapter 24:07] before issuing."
            )
        elif score < 90:
            recs.append(
                "Minor compliance issues detected. Address the flagged items before final approval."
            )
        else:
            recs.append(
                "Document meets core regulatory requirements. "
                "Ensure ongoing compliance during the policy period."
            )

        return recs
