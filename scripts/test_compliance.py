"""
Test suite for the regulatory compliance engine.

Tests
-----
1. Knowledge base files exist and are valid JSON.
2. ComplianceChecker initialises and loads KB data.
3. Sample insurance document is checked and scores reasonably.

Run from the project root:
    python scripts/test_compliance.py
"""
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

KB_ROOT = Path(r"C:\Users\lenovo\Desktop\Scrapper\kb")


# ---------------------------------------------------------------------------
# Test 1 — Knowledge base loading
# ---------------------------------------------------------------------------

def test_knowledge_base_loading() -> bool:
    print("\n" + "=" * 60)
    print("TEST 1: Knowledge Base Loading")
    print("=" * 60)

    required = ["mandatory_clauses.json", "prohibited_terms.json"]
    all_ok = True

    for filename in required:
        path = KB_ROOT / filename
        if not path.exists():
            print(f"  FAIL  {filename}: file not found at {path}")
            all_ok = False
            continue

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            if filename == "mandatory_clauses.json":
                count = len(data.get("clauses", []))
                key = "clauses"
            else:
                count = len(data.get("prohibited_terms", []))
                key = "prohibited_terms"

            print(f"  PASS  {filename}: valid JSON — {count} {key} loaded")
        except json.JSONDecodeError as exc:
            print(f"  FAIL  {filename}: invalid JSON — {exc}")
            all_ok = False

    return all_ok


# ---------------------------------------------------------------------------
# Test 2 — ComplianceChecker initialisation
# ---------------------------------------------------------------------------

def test_compliance_checker_init():
    print("\n" + "=" * 60)
    print("TEST 2: ComplianceChecker Initialisation")
    print("=" * 60)

    # Ensure project root is on sys.path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    try:
        from app.services.compliance_checker import ComplianceChecker
        checker = ComplianceChecker()

        mandatory_count = len(checker.mandatory_clauses)
        prohibited_count = len(checker.prohibited_terms)

        if mandatory_count == 0:
            print("  FAIL  No mandatory clauses loaded")
            return None

        if prohibited_count == 0:
            print("  FAIL  No prohibited terms loaded")
            return None

        print(f"  PASS  ComplianceChecker initialised")
        print(f"        Mandatory clauses : {mandatory_count}")
        print(f"        Prohibited terms  : {prohibited_count}")
        return checker

    except Exception as exc:
        print(f"  FAIL  Initialisation error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Test 3 — Sample document compliance check
# ---------------------------------------------------------------------------

SAMPLE_TEXT = """
INSURANCE POLICY DOCUMENT

Policy Number: POL-2024-001234

INSURER: First Mutual Zimbabwe Limited
Registration Number: 1234/2020
Registered Office: 123 Harare Street, Harare

INSURED: John Doe

POLICY PERIOD:
Effective Date: 01 January 2024
Expiry Date: 31 December 2024

COVERAGE DESCRIPTION:
Sum Insured: $50,000
This policy covers comprehensive motor insurance against accidental damage,
theft, and third-party liability.

PREMIUM:
Annual Premium: $2,500
Payment Terms: Annually in advance

DEDUCTIBLE / EXCESS:
Excess: $500 per claim

CLAIMS PROCEDURE:
Claims must be notified within 30 days of incident. Supporting documents
required include: police report, repair estimates, and driver's licence.

CANCELLATION:
Either party may cancel this policy with 30 days written notice.

EXCLUSIONS:
This policy does not cover:
- War and terrorism
- Wear and tear
- Driving under the influence of alcohol or drugs

DUTY OF DISCLOSURE:
The insured must disclose all material facts to the insurer at inception
and throughout the policy period.

GOVERNING LAW:
This policy is governed by the laws of Zimbabwe.

DISPUTE RESOLUTION:
Any disputes arising from this policy shall be referred to arbitration
in accordance with the Arbitration Act [Chapter 7:15].
"""


def test_sample_document(checker) -> bool:
    print("\n" + "=" * 60)
    print("TEST 3: Sample Document Compliance Check")
    print("=" * 60)

    try:
        result = checker.check_compliance(SAMPLE_TEXT, document_type="motor")

        score = result["compliance_score"]
        status = result["status"]
        mc = result["mandatory_clauses"]
        pt = result["prohibited_terms"]

        print(f"  Compliance Score   : {score}%")
        print(f"  Status             : {status}")
        print(f"  Mandatory Clauses  : {mc['found']}/{mc['total_required']} found")
        print(f"  Prohibited Terms   : {pt['found']} violation(s)")

        if mc["missing"]:
            print(f"\n  Missing clauses ({len(mc['missing'])}):")
            for clause in mc["missing"]:
                print(f"    - [{clause['id']}] {clause['requirement']} ({clause['section']})")

        if pt["violations"]:
            print(f"\n  Violations ({len(pt['violations'])}):")
            for v in pt["violations"]:
                print(f"    - [{v['severity'].upper()}] {v['term']}")

        print(f"\n  Top Recommendations:")
        for rec in result["recommendations"][:3]:
            print(f"    • {rec}")

        passed = score >= 50  # A well-formed sample should always score above 50
        if passed:
            print(f"\n  PASS  Score {score}% is above minimum threshold (50%)")
        else:
            print(f"\n  FAIL  Score {score}% is below minimum threshold (50%)")
        return passed

    except Exception as exc:
        print(f"  FAIL  Compliance check error: {exc}")
        import traceback
        traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n" + "=" * 60)
    print("COMPLIANCE ENGINE TEST SUITE")
    print("=" * 60)

    passed = 0
    total = 3

    if not test_knowledge_base_loading():
        print("\nCannot continue without knowledge base files.")
        sys.exit(1)
    passed += 1

    checker = test_compliance_checker_init()
    if not checker:
        print("\nCannot continue without ComplianceChecker.")
        sys.exit(1)
    passed += 1

    if test_sample_document(checker):
        passed += 1

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("\nALL TESTS PASSED — Compliance Engine is ready.\n")
        sys.exit(0)
    else:
        print(f"\n{total - passed} test(s) failed.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
