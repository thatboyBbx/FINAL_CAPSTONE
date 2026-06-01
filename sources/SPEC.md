# SPEC — Sandbox Regulatory Expansion Job
## InsureIntel Zimbabwe | R228131Q | Job: SANDBOX_EXP_v1

---

## 0. Context

The IPEC Regulatory Sandbox Guidelines (effective Q4 2025) have been reviewed and analysed.
This job implements all ML, NLP, compliance, and UI additions that flow directly from that document.

**Source document path (on Windows dev machine):**
```
C:\Users\lenovo\Desktop\CAPSTONE_ARCHIVE\PRIMARY\EXPERIMENT\sources\REGULATORY-SANDBOX-GUIDELINES-FOR-THE-INSURANCE-AND-PENSIONS-INDUSTRY-.pdf
```

**Active codebase root:**
```
C:\Users\lenovo\Desktop\CAPSTONE_ARCHIVE\PRIMARY\EXPERIMENT\
```

All paths in this spec are relative to that root unless stated otherwise.

---

## 1. Scope — What This Job Builds

This job has **6 deliverables**, executed in strict order:

| # | Deliverable | Layer |
|---|------------|-------|
| 1 | PDF text extraction + BIO annotation pipeline for sandbox document | ML / Data |
| 2 | 8 new NER entity types added to spaCy training schema | ML / NER |
| 3 | 3 new document classification labels + training examples | ML / Classification |
| 4 | 6 new compliance rule group (Annexure 1 eligibility checker) | Backend / Compliance |
| 5 | 3 new clause types in clause classifier | ML / Clause |
| 6 | Sandbox Quarterly Report Jinja2 template + PDF export route | UI / Reports |

**Out of scope for this job:**
- Retraining the NER model end-to-end (data generation only — training run is a separate job)
- Modifying existing entity types
- Any change to auth, RBAC, or database migrations
- CSP model changes

---

## 2. Deliverable 1 — PDF Extraction + BIO Annotation Pipeline

### File to create:
```
app/infrastructure/scrapers/sandbox_annotator.py
```

### What it does:
1. Reads the sandbox PDF using `pdfplumber`
2. Extracts all text, preserving sentence boundaries
3. Runs each sentence through a rule-based pre-annotator that tags spans matching the 8 new entity types using keyword patterns
4. Outputs a `.jsonl` file in spaCy training format (list of `{"text": ..., "entities": [[start, end, label], ...]}`)
5. Outputs a plain `.txt` file of all extracted sentences for manual review
6. Prints a summary: total sentences, total annotations per entity type

### Output files:
```
app/infrastructure/storage/training_data/sandbox_ner_annotations.jsonl
app/infrastructure/storage/training_data/sandbox_sentences_raw.txt
```

### Entity pattern rules (regex + keyword matching):

```
TESTING_PERIOD    → patterns: "X months", "testing period", "X-month", "duration of"
BOUNDARY_CONDITION → patterns: "start and end date", "transaction limit", "number of customers",
                               "geographical location", "target customer", "consent to participate"
REGULATORY_WAIVER  → patterns: "relaxation", "regulatory relief", "waiver", "exemption sought",
                               "cannot operate within"
KPI_TARGET         → patterns: "key performance indicator", "KPI", "success criteria",
                               "target.*metric", "performance indicator"
EXIT_CONDITION     → patterns: "exit plan", "graduation", "exit report", "orderly exit",
                               "transition.*deployment", "post-exit"
COMPLIANCE_STATUS  → patterns: "successful", "failure", "communicate.*writing", "approved",
                               "revoked", "pass", "fail"
TCF_CLAUSE         → patterns: "Treating Customers Fairly", "TCF", "dispute resolution",
                               "fair treatment", "customer complaint"
KYC_AML_CLAUSE     → patterns: "Know Your Customer", "KYC", "Anti Money Laundering", "AML",
                               "Countering Financing of Terrorism", "CFT", "money laundering"
```

### Rules:
- Use `pdfplumber` only (already in requirements.txt)
- Split text into sentences using simple period+space heuristic (no NLTK dependency)
- Each sentence becomes one training example
- If no entities found in a sentence, still include it as a negative example
- Annotate overlapping spans conservatively — skip the sentence if two patterns overlap
- Write full inline comments explaining each step
- Handle PDF extraction errors gracefully with try/except, log warnings, continue

---

## 3. Deliverable 2 — NER Entity Schema Extension

### File to modify:
```
app/ai/nlp/ner_pipeline.py
```

### What to add:

Add the 8 new entity labels to the existing spaCy NER pipeline's label set. The model is not retrained here — labels are registered so the pipeline accepts them and passes them through without crashing when encountered in training data.

```python
NEW_ENTITY_LABELS = [
    "TESTING_PERIOD",
    "BOUNDARY_CONDITION",
    "REGULATORY_WAIVER",
    "KPI_TARGET",
    "EXIT_CONDITION",
    "COMPLIANCE_STATUS",
    "TCF_CLAUSE",
    "KYC_AML_CLAUSE",
]
```

Add a function `register_sandbox_entities(nlp_model)` that:
1. Gets the NER pipe from the model
2. For each label in `NEW_ENTITY_LABELS`, calls `ner.add_label(label)` if not already present
3. Logs each addition
4. Returns the updated model

Add a constant `ENTITY_DESCRIPTIONS` dict mapping each label to a plain-English description — this is used by the UI and the Reports module to display human-readable entity names.

### File to create:
```
app/ai/nlp/entity_registry.py
```

This file is the single source of truth for ALL entity labels in the system — both existing and new. It exports:
- `ALL_ENTITY_LABELS` — complete list
- `ENTITY_GROUPS` — dict grouping labels by category: `"insurance_core"`, `"regulatory_sandbox"`, `"compliance_safeguards"`
- `ENTITY_DISPLAY_NAMES` — human readable names for UI rendering
- `ENTITY_COLORS` — hex color per entity group for UI highlighting

---

## 4. Deliverable 3 — Document Classifier New Labels

### File to modify:
```
app/infrastructure/storage/training_data/document_classification_training_20260411.json
```

Add 3 new document type labels with synthetic training examples generated from the Annexure 2 and Annexure 3 templates:

**New labels:**
- `SANDBOX_APPLICATION` — 25 synthetic examples
- `SANDBOX_QUARTERLY_REPORT` — 20 synthetic examples  
- `SANDBOX_EXIT_REPORT` — 20 synthetic examples

### File to create:
```
app/infrastructure/storage/training_data/sandbox_document_examples.json
```

Structure:
```json
{
  "label": "SANDBOX_APPLICATION",
  "examples": [
    {
      "text": "...",
      "source": "synthetic_annexure2",
      "sections_present": ["problem_statement", "business_model", "testing_plan", "boundary_conditions"]
    }
  ]
}
```

Each synthetic example must:
- Be 150-400 words (realistic document excerpt length)
- Contain at least 3 structural markers specific to that document type
- Use Zimbabwean insurance context (IPEC, Insurance Act, Zimbabwe, USD amounts)
- NOT copy verbatim from the sandbox PDF

### File to modify:
```
app/modules/documents/service.py
```

Update `DOCUMENT_TYPE_LABELS` constant to include the 3 new types.
Update any switch/match statements or if-chains that enumerate document types.

---

## 5. Deliverable 4 — Annexure 1 Compliance Rule Group

### File to modify:
```
app/services/compliance_checker.py
```

Add a new rule group called `"sandbox_eligibility"` with 6 rule sets mapping directly to Annexure 1 criteria:

```python
SANDBOX_ELIGIBILITY_RULES = {
    "rule_group": "sandbox_eligibility",
    "display_name": "IPEC Regulatory Sandbox Eligibility Pre-Check",
    "source": "IPEC Regulatory Sandbox Guidelines (2025), Annexure 1",
    "rules": [
        {
            "id": "SE_001",
            "criterion": "Scope and mandate",
            "check": "Document describes an innovation within IPEC supervisory mandate (insurance or pensions)",
            "keywords_required": ["insurance", "pensions", "IPEC", "Commission"],
            "severity": "critical",
            "pass_message": "Innovation appears within IPEC mandate scope",
            "fail_message": "Document does not clearly establish activity within IPEC mandate — see Annexure 1, Criterion 1"
        },
        {
            "id": "SE_002",
            "criterion": "Governance structure",
            "check": "Document includes or references organisational structure, shareholders, or directors",
            "keywords_required": ["organogram", "governance", "directors", "shareholders", "beneficial owner"],
            "severity": "high",
            "pass_message": "Governance structure information present",
            "fail_message": "No governance structure information found — Annexure 1, Criterion 2 requires organogram and shareholder details"
        },
        {
            "id": "SE_003",
            "criterion": "Regulatory approval requirement",
            "check": "Document acknowledges whether regulatory approval is required to operate",
            "keywords_required": ["regulatory approval", "licence", "license", "Commission approval"],
            "severity": "high",
            "pass_message": "Regulatory approval status addressed",
            "fail_message": "Regulatory approval requirement not addressed — Annexure 1, Criterion 3"
        },
        {
            "id": "SE_004",
            "criterion": "Capacity to participate",
            "check": "Document demonstrates business model readiness, testing plan, and resource mobilisation",
            "keywords_required": ["business model", "testing plan", "milestones", "resources", "KPI"],
            "severity": "high",
            "pass_message": "Capacity indicators present",
            "fail_message": "Insufficient evidence of capacity — missing testing plan, milestones, or KPIs (Annexure 1, Criterion 4)"
        },
        {
            "id": "SE_005",
            "criterion": "Regulatory gap (cannot operate under existing framework)",
            "check": "Document explains why existing regulatory framework is insufficient",
            "keywords_required": ["existing framework", "not covered", "no existing licence", "regulatory gap", "cannot operate"],
            "severity": "medium",
            "pass_message": "Regulatory gap justification present",
            "fail_message": "No justification for why existing framework is insufficient — Annexure 1, Criterion 5"
        },
        {
            "id": "SE_006",
            "criterion": "Fit and proper requirements",
            "check": "Document references police clearance, tax clearance, or fit and proper status",
            "keywords_required": ["police clearance", "tax clearance", "fit and proper", "insolvent", "money laundering"],
            "severity": "medium",
            "pass_message": "Fit and proper references present",
            "fail_message": "No fit and proper documentation referenced — Annexure 1, Criterion 6 requires police and tax clearance"
        }
    ]
}
```

The compliance checker's main `check_document(text, rule_groups)` function must accept `"sandbox_eligibility"` as a valid group name.

Add a new top-level function:
```python
def check_sandbox_eligibility(document_text: str) -> dict:
    """
    Runs all 6 Annexure 1 eligibility checks against a document.
    Returns structured result with pass/fail per criterion,
    overall eligibility score (0-6 criteria passed),
    and a plain-English summary.
    """
```

### File to modify:
```
app/modules/documents/router.py  (or wherever analysis routes live)
```

Add endpoint:
```
POST /api/documents/{document_id}/sandbox-eligibility
```
Returns the structured eligibility check result.

---

## 6. Deliverable 5 — Clause Classifier New Types

### File to modify:
```
app/ai/nlp/ner_pipeline.py  (or wherever clause classification lives)
```

Add 3 new clause type labels:

```python
NEW_CLAUSE_TYPES = [
    {
        "label": "TCF_CLAUSE",
        "description": "Treating Customers Fairly clause — covers dispute resolution, fair treatment, complaints handling",
        "trigger_phrases": [
            "dispute resolution", "treating customers fairly", "fair treatment",
            "customer complaint", "complaints procedure", "ombudsman",
            "right to complain", "redress mechanism"
        ]
    },
    {
        "label": "KYC_AML_CLAUSE",
        "description": "Know Your Customer / Anti-Money Laundering clause — identity verification, suspicious transaction reporting",
        "trigger_phrases": [
            "know your customer", "identity verification", "suspicious transaction",
            "anti-money laundering", "beneficial owner", "politically exposed person",
            "PEP", "FATF", "financial intelligence", "counter terrorism financing"
        ]
    },
    {
        "label": "REGULATORY_WAIVER_CLAUSE",
        "description": "Temporary regulatory relief or exemption — time-limited permission to operate outside standard framework",
        "trigger_phrases": [
            "regulatory relief", "temporary exemption", "waiver", "relaxation of",
            "notwithstanding", "without prejudice to", "derogation", "pilot basis",
            "subject to Commission approval", "conditional approval"
        ]
    }
]
```

Add a function `classify_clause_type(clause_text: str) -> str` that:
1. Checks trigger phrases for all clause types (existing + new)
2. Returns the matching label or `"UNKNOWN_CLAUSE"` if no match
3. Is deterministic (rule-based, no model call) — fast enough for bulk processing

---

## 7. Deliverable 6 — Sandbox Quarterly Report Template

### File to create:
```
app/ui/templates/reports/sandbox_quarterly_report.html
```

This is a Jinja2 template that generates an IPEC-compliant Sandbox Quarterly Progress Report.

**Template variables (passed from route):**
```python
{
    "participant_name": str,
    "report_quarter": str,          # e.g. "Q2 2026"
    "report_date": str,
    "kpis": list[dict],             # [{"name": str, "target": str, "actual": str, "status": "met"|"partial"|"missed"}]
    "customer_count": int,
    "transaction_volume": int,
    "transaction_value": str,
    "risk_register": list[dict],    # [{"risk": str, "trigger": str, "treatment": str, "likelihood": str}]
    "operational_challenges": list[str],
    "cybersecurity_incidents": list[str],
    "audit_details": str,
    "customer_complaints": list[dict],  # [{"complaint": str, "resolution": str, "status": str}]
    "generated_by": str,            # "InsureIntel Zimbabwe Platform"
    "document_ids_analysed": list[str]
}
```

Template structure follows Annexure 3 exactly:
1. Header — participant name, quarter, date, IPEC reference
2. Section A — KPI Progress (table: KPI name | target | actual | status badge)
3. Section B — Customer Statistics (count, volume, value)
4. Section C — Risk Register (table: risk | trigger | treatment | likelihood)
5. Section E — Operational Challenges (bullet list)
6. Section F — Audit Details
7. Section G — Customer Complaints (table)
8. Footer — "Generated by InsureIntel Zimbabwe Platform | Compliant with IPEC Regulatory Sandbox Guidelines (2025) Annexure 3"

Design: use existing glassmorphism CSS variables from base.html. Dark/light mode toggle must work.

### File to create:
```
app/modules/reports/sandbox_report_service.py
```

Service that:
1. Queries the database for all analysis results linked to a given broker/client over the quarter
2. Aggregates KPI metrics from those results (avg risk score, compliance rate, entity extraction counts)
3. Pulls risk register entries from the database
4. Returns a populated template context dict
5. Renders the template to HTML
6. Exports to PDF using WeasyPrint (same pattern as existing report generation)

### File to modify:
```
app/modules/reports/router.py
```

Add endpoint:
```
GET /api/reports/sandbox-quarterly/{broker_id}?quarter=Q2-2026
```

Returns either JSON (if `Accept: application/json`) or PDF download (if `Accept: application/pdf`).

---

## 8. Required New Files Summary

```
app/infrastructure/scrapers/sandbox_annotator.py          ← Deliverable 1
app/infrastructure/storage/training_data/
    sandbox_ner_annotations.jsonl                         ← Deliverable 1 output
    sandbox_sentences_raw.txt                             ← Deliverable 1 output
    sandbox_document_examples.json                        ← Deliverable 3
app/ai/nlp/entity_registry.py                             ← Deliverable 2
app/modules/reports/sandbox_report_service.py             ← Deliverable 6
app/ui/templates/reports/sandbox_quarterly_report.html    ← Deliverable 6
```

## 9. Files to Modify Summary

```
app/ai/nlp/ner_pipeline.py                    ← add 8 labels + register function
app/services/compliance_checker.py            ← add sandbox_eligibility rule group
app/modules/documents/service.py              ← add 3 new document type labels
app/infrastructure/storage/training_data/
    document_classification_training_20260411.json ← add new labels
app/modules/documents/router.py               ← add sandbox eligibility endpoint
app/modules/reports/router.py                 ← add sandbox quarterly report endpoint
```

---

## 10. Dissertation Documentation Requirements

Every new function must include a docstring in this format:

```python
def function_name(...):
    """
    [Plain English description of what this does]

    Dissertation Methodology Note (Chapter 3):
    This function implements [approach] as justified by [citation].
    The rule-based approach was chosen over a learned classifier because
    [reason — e.g. the rule set is fully defined by IPEC (2025) and
    requires no training data; deterministic outputs are preferable for
    regulatory compliance checking where explainability is mandatory].

    References:
        IPEC (2025). Regulatory Sandbox Guidelines for the Insurance and
        Pensions Industry. Insurance and Pensions Commission, Zimbabwe.
        Effective Q4 2025.
    """
```

---

## 11. Testing Requirements

For each deliverable, add at minimum:

- **Deliverable 1:** Test that `sandbox_annotator.py` runs on the PDF without crashing and produces non-empty `.jsonl` output. Test that at least `TESTING_PERIOD` and `KYC_AML_CLAUSE` are annotated.
- **Deliverable 2:** Test that `register_sandbox_entities()` adds all 8 labels without duplicating existing ones. Test that `entity_registry.py` exports complete and consistent dicts.
- **Deliverable 3:** Test that classifier training JSON is valid and all 3 new labels have at least 15 examples each.
- **Deliverable 4:** Test `check_sandbox_eligibility()` with a dummy document that passes all 6 criteria. Test with a document that fails 3 criteria. Assert correct pass/fail counts.
- **Deliverable 5:** Test `classify_clause_type()` with known TCF and KYC phrases returns correct labels.
- **Deliverable 6:** Test that the report route returns 200 with valid HTML. Test PDF export returns bytes with PDF mime type.

---

## 12. Constraints

- Python 3.11 only
- No new pip packages — use only what is already in requirements.txt
- No changes to SQLAlchemy models (no Alembic migrations in this job)
- No changes to auth or RBAC
- No changes to any existing entity types or compliance rules (additive only)
- All new code must pass `flake8` with no errors
- Budget awareness: this is a targeted expansion job, not a rebuild. If a deliverable requires more than ~200 lines of new code, flag it before proceeding.
