"""
app/ai/nlp/entity_registry.py

Single source of truth for all NER entity labels in InsureIntel Zimbabwe.

Exports:
    ALL_ENTITY_LABELS       — complete list (insurance core + sandbox + compliance)
    ENTITY_GROUPS           — labels grouped by category
    ENTITY_DISPLAY_NAMES    — human-readable names for UI rendering
    ENTITY_COLORS           — hex colour per entity group for UI span highlighting
    ENTITY_DESCRIPTIONS     — one-line descriptions for reports and tooltips
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Insurance core entities  (pre-existing, defined by the insurance document
# ontology used across the InsureIntel platform)
# ---------------------------------------------------------------------------

_INSURANCE_CORE: list[str] = [
    "COVERAGE_LIMIT",
    "POLICY_PERIOD",
    "PREMIUM",
    "DEDUCTIBLE",
    "PARTY",
    "GEOGRAPHIC_COVERAGE",
    "EXCLUSION",
    # Legacy labels still accepted by the NER pipeline
    "POLICY_NUMBER",
    "INSURER",
    "INSURED",
    "CLAUSE_REF",
]

# ---------------------------------------------------------------------------
# Regulatory sandbox entities  (new — IPEC Regulatory Sandbox Guidelines 2025)
# ---------------------------------------------------------------------------

_REGULATORY_SANDBOX: list[str] = [
    "TESTING_PERIOD",
    "BOUNDARY_CONDITION",
    "REGULATORY_WAIVER",
    "KPI_TARGET",
    "EXIT_CONDITION",
    "COMPLIANCE_STATUS",
]

# ---------------------------------------------------------------------------
# Compliance safeguard entities  (new — drawn from IPEC Safeguards section)
# ---------------------------------------------------------------------------

_COMPLIANCE_SAFEGUARDS: list[str] = [
    "TCF_CLAUSE",
    "KYC_AML_CLAUSE",
]

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

# The 8 new sandbox labels (used by register_sandbox_entities)
NEW_SANDBOX_LABELS: list[str] = _REGULATORY_SANDBOX + _COMPLIANCE_SAFEGUARDS

# Complete ordered label list — insurance core first, then extensions
ALL_ENTITY_LABELS: list[str] = (
    _INSURANCE_CORE + _REGULATORY_SANDBOX + _COMPLIANCE_SAFEGUARDS
)

# Grouped by category for the UI and the entity registry
ENTITY_GROUPS: dict[str, list[str]] = {
    "insurance_core": _INSURANCE_CORE,
    "regulatory_sandbox": _REGULATORY_SANDBOX,
    "compliance_safeguards": _COMPLIANCE_SAFEGUARDS,
}

# Human-readable display names for UI components and PDF reports
ENTITY_DISPLAY_NAMES: dict[str, str] = {
    # Insurance core
    "COVERAGE_LIMIT":    "Coverage Limit",
    "POLICY_PERIOD":     "Policy Period",
    "PREMIUM":           "Premium",
    "DEDUCTIBLE":        "Deductible / Excess",
    "PARTY":             "Party",
    "GEOGRAPHIC_COVERAGE": "Geographic Coverage",
    "EXCLUSION":         "Exclusion Clause",
    "POLICY_NUMBER":     "Policy Number",
    "INSURER":           "Insurer",
    "INSURED":           "Insured",
    "CLAUSE_REF":        "Clause Reference",
    # Regulatory sandbox
    "TESTING_PERIOD":    "Testing Period",
    "BOUNDARY_CONDITION": "Boundary Condition",
    "REGULATORY_WAIVER": "Regulatory Waiver",
    "KPI_TARGET":        "KPI Target",
    "EXIT_CONDITION":    "Exit Condition",
    "COMPLIANCE_STATUS": "Compliance Status",
    # Compliance safeguards
    "TCF_CLAUSE":        "Treating Customers Fairly Clause",
    "KYC_AML_CLAUSE":    "KYC / AML Clause",
}

# Hex highlight colours — one colour per group, applied to all labels in that group
# These are chosen to be visible on both dark and light backgrounds
ENTITY_COLORS: dict[str, str] = {
    # Insurance core — gold amber (matches brand colour --cp)
    "COVERAGE_LIMIT":    "#d4af37",
    "POLICY_PERIOD":     "#d4af37",
    "PREMIUM":           "#d4af37",
    "DEDUCTIBLE":        "#d4af37",
    "PARTY":             "#d4af37",
    "GEOGRAPHIC_COVERAGE": "#d4af37",
    "EXCLUSION":         "#d4af37",
    "POLICY_NUMBER":     "#d4af37",
    "INSURER":           "#d4af37",
    "INSURED":           "#d4af37",
    "CLAUSE_REF":        "#d4af37",
    # Regulatory sandbox — steel blue
    "TESTING_PERIOD":    "#4a90d9",
    "BOUNDARY_CONDITION": "#4a90d9",
    "REGULATORY_WAIVER": "#4a90d9",
    "KPI_TARGET":        "#4a90d9",
    "EXIT_CONDITION":    "#4a90d9",
    "COMPLIANCE_STATUS": "#4a90d9",
    # Compliance safeguards — jade green
    "TCF_CLAUSE":        "#3dba78",
    "KYC_AML_CLAUSE":    "#3dba78",
}

# One-line descriptions (used in reports and API responses)
ENTITY_DESCRIPTIONS: dict[str, str] = {
    "COVERAGE_LIMIT":    "Maximum monetary coverage amount stated in the policy",
    "POLICY_PERIOD":     "Start and end dates of insurance cover",
    "PREMIUM":           "Amount payable by the insured for cover",
    "DEDUCTIBLE":        "Excess amount borne by the insured per claim",
    "PARTY":             "Named party to the contract",
    "GEOGRAPHIC_COVERAGE": "Territorial scope of the policy",
    "EXCLUSION":         "Risk or event excluded from coverage",
    "POLICY_NUMBER":     "Unique alphanumeric policy reference",
    "INSURER":           "Insurance company providing the cover",
    "INSURED":           "Person or entity covered by the policy",
    "CLAUSE_REF":        "Reference to a specific policy clause or section",
    "TESTING_PERIOD":    "Duration of the regulatory sandbox test window",
    "BOUNDARY_CONDITION": "Defined limits of the sandbox (customers, geography, transactions)",
    "REGULATORY_WAIVER": "Temporary relaxation of a regulatory requirement",
    "KPI_TARGET":        "Key performance indicator and success criterion for the sandbox",
    "EXIT_CONDITION":    "Conditions for exit, graduation, or orderly wind-down",
    "COMPLIANCE_STATUS": "Outcome communication — approval, revocation, or pass/fail",
    "TCF_CLAUSE":        "Treating Customers Fairly obligation under IPEC mandate",
    "KYC_AML_CLAUSE":    "Know Your Customer / Anti-Money Laundering requirement",
}
