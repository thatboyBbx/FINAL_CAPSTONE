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

# ---------------------------------------------------------------------------
# Deliverable 4 — IPEC Sandbox Eligibility Rules (Annexure 1)
# ---------------------------------------------------------------------------

# Six eligibility criteria from Annexure 1 of the IPEC Regulatory Sandbox
# Guidelines (2025).  Each rule maps directly to a numbered criterion.
SANDBOX_ELIGIBILITY_RULES: dict = {
    "rule_group": "sandbox_eligibility",
    "display_name": "IPEC Regulatory Sandbox Eligibility Pre-Check",
    "source": "IPEC Regulatory Sandbox Guidelines (2025), Annexure 1",
    "rules": [
        {
            "id": "SE_001",
            "criterion": "Scope and mandate",
            "check": "Document describes an innovation within IPEC supervisory mandate "
                     "(insurance or pensions)",
            "keywords_required": ["insurance", "pensions", "ipec", "commission"],
            "severity": "critical",
            "pass_message": "Innovation appears within IPEC mandate scope",
            "fail_message": "Document does not clearly establish activity within IPEC "
                            "mandate — see Annexure 1, Criterion 1",
        },
        {
            "id": "SE_002",
            "criterion": "Governance structure",
            "check": "Document includes or references organisational structure, "
                     "shareholders, or directors",
            "keywords_required": [
                "organogram", "governance", "directors", "shareholders", "beneficial owner",
            ],
            "severity": "high",
            "pass_message": "Governance structure information present",
            "fail_message": "No governance structure information found — Annexure 1, "
                            "Criterion 2 requires organogram and shareholder details",
        },
        {
            "id": "SE_003",
            "criterion": "Regulatory approval requirement",
            "check": "Document acknowledges whether regulatory approval is required "
                     "to operate",
            "keywords_required": [
                "regulatory approval", "licence", "license", "commission approval",
            ],
            "severity": "high",
            "pass_message": "Regulatory approval status addressed",
            "fail_message": "Regulatory approval requirement not addressed — "
                            "Annexure 1, Criterion 3",
        },
        {
            "id": "SE_004",
            "criterion": "Capacity to participate",
            "check": "Document demonstrates business model readiness, testing plan, "
                     "and resource mobilisation",
            "keywords_required": [
                "business model", "testing plan", "milestones", "resources", "kpi",
            ],
            "severity": "high",
            "pass_message": "Capacity indicators present",
            "fail_message": "Insufficient evidence of capacity — missing testing plan, "
                            "milestones, or KPIs (Annexure 1, Criterion 4)",
        },
        {
            "id": "SE_005",
            "criterion": "Regulatory gap (cannot operate under existing framework)",
            "check": "Document explains why existing regulatory framework is insufficient",
            "keywords_required": [
                "existing framework", "not covered", "no existing licence",
                "regulatory gap", "cannot operate",
            ],
            "severity": "medium",
            "pass_message": "Regulatory gap justification present",
            "fail_message": "No justification for why existing framework is insufficient "
                            "— Annexure 1, Criterion 5",
        },
        {
            "id": "SE_006",
            "criterion": "Fit and proper requirements",
            "check": "Document references police clearance, tax clearance, or fit "
                     "and proper status",
            "keywords_required": [
                "police clearance", "tax clearance", "fit and proper",
                "insolvent", "money laundering",
            ],
            "severity": "medium",
            "pass_message": "Fit and proper references present",
            "fail_message": "No fit and proper documentation referenced — Annexure 1, "
                            "Criterion 6 requires police and tax clearance",
        },
    ],
}

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


# ---------------------------------------------------------------------------
# Deliverable 4 — Standalone sandbox eligibility checker function
# ---------------------------------------------------------------------------

def check_sandbox_eligibility(document_text: str) -> dict:
    """
    Run all 6 Annexure 1 eligibility checks against a document.

    Checks each of the six IPEC Regulatory Sandbox eligibility criteria
    using keyword matching against the document text (case-insensitive).
    Returns a structured result with pass/fail per criterion, an overall
    eligibility score (0-6 criteria passed), and a plain-English summary
    suitable for display to a non-technical user (e.g. an insurance broker).

    Status thresholds:
        ELIGIBLE        : 5-6 criteria passed
        LIKELY_ELIGIBLE : 3-4 criteria passed
        NOT_ELIGIBLE    : 0-2 criteria passed

    Dissertation Methodology Note (Chapter 3):
    This function implements a rule-based eligibility pre-checker whose
    rules are fully specified in IPEC (2025) Annexure 1.  A rule-based
    approach is chosen over a learned classifier because (a) the criterion
    set is closed and authoritatively defined by the regulator, (b) outputs
    must be explainable for regulatory purposes, and (c) deterministic
    results avoid probabilistic ambiguity in a compliance context.

    References:
        IPEC (2025). Regulatory Sandbox Guidelines for the Insurance and
        Pensions Industry. Insurance and Pensions Commission of Zimbabwe.
        Effective Q4 2025. Retrieved from ipec.co.zw.
    """
    if not document_text:
        document_text = ""

    # Normalise to lower-case once for efficient substring matching
    text_lower = document_text.lower()

    results: list[dict] = []
    criteria_passed = 0

    for rule in SANDBOX_ELIGIBILITY_RULES["rules"]:
        # A rule passes if ANY of its required keywords is found in the text
        matched = any(kw in text_lower for kw in rule["keywords_required"])

        if matched:
            criteria_passed += 1
            results.append({
                "id": rule["id"],
                "criterion": rule["criterion"],
                "passed": True,
                "message": rule["pass_message"],
                "severity": rule["severity"],
            })
        else:
            results.append({
                "id": rule["id"],
                "criterion": rule["criterion"],
                "passed": False,
                "message": rule["fail_message"],
                "severity": rule["severity"],
            })

    total_criteria = len(SANDBOX_ELIGIBILITY_RULES["rules"])
    criteria_failed = total_criteria - criteria_passed
    eligibility_score_pct = round(criteria_passed / total_criteria * 100, 1)

    # Determine overall eligibility band
    if criteria_passed >= 5:
        overall_status = "ELIGIBLE"
    elif criteria_passed >= 3:
        overall_status = "LIKELY_ELIGIBLE"
    else:
        overall_status = "NOT_ELIGIBLE"

    # Build a plain-English summary for non-technical users
    failed_criteria = [r["criterion"] for r in results if not r["passed"]]
    if overall_status == "ELIGIBLE":
        summary = (
            f"This document meets {criteria_passed} of {total_criteria} IPEC sandbox "
            f"eligibility criteria and is likely eligible to apply for the Regulatory "
            f"Sandbox. "
        )
        if failed_criteria:
            summary += (
                f"To strengthen the application, address the following: "
                f"{', '.join(failed_criteria)}."
            )
        else:
            summary += "All criteria are satisfied."
    elif overall_status == "LIKELY_ELIGIBLE":
        summary = (
            f"This document meets {criteria_passed} of {total_criteria} criteria. "
            f"It may be eligible for the sandbox but requires the following improvements "
            f"before submission: {', '.join(failed_criteria)}."
        )
    else:
        summary = (
            f"This document only meets {criteria_passed} of {total_criteria} eligibility "
            f"criteria and is unlikely to qualify for the IPEC Regulatory Sandbox in its "
            f"current form. Please address: {', '.join(failed_criteria)}."
        )

    return {
        "rule_group": SANDBOX_ELIGIBILITY_RULES["rule_group"],
        "source": SANDBOX_ELIGIBILITY_RULES["source"],
        "total_criteria": total_criteria,
        "criteria_passed": criteria_passed,
        "criteria_failed": criteria_failed,
        "eligibility_score_pct": eligibility_score_pct,
        "overall_status": overall_status,
        "results": results,
        "plain_english_summary": summary,
    }
