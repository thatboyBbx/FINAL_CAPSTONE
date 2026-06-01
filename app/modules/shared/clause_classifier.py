"""
app/modules/shared/clause_classifier.py
=========================================
Shared clause-type classification utility.

Previously duplicated in:
  - app/modules/comparison/service.py
  - app/modules/deviation/knowledge_base_seeder.py
"""


def classify_clause_type(text: str) -> str:
    """
    Classify a text block into a clause type based on keyword presence.

    Returns one of: "exclusion", "coverage", "cancellation",
    "claims_procedure", "condition", "general".
    """
    t = text.lower()
    if any(w in t for w in ("exclusion", "excluded", "not covered", "does not cover")):
        return "exclusion"
    if any(w in t for w in ("coverage", "covers", "insured amount", "limit of indemnity", "limit of")):
        return "coverage"
    if any(w in t for w in ("cancellation", "cancel", "termination", "terminate")):
        return "cancellation"
    if any(w in t for w in ("claims", "claim procedure", "claim", "notify", "notification", "report the loss")):
        return "claims_procedure"
    if any(w in t for w in ("condition", "shall", "must", "warranty", "warranted", "shall not")):
        return "condition"
    return "general"
