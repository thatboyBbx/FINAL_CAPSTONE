# SYSTEM UPGRADE MASTER SPEC

## 1. ARCHITECTURE REFACTOR

Reorganize into:

app/
 ├── core/
 ├── api/
 ├── domains/
 │   ├── insurance/
 │   ├── clients/
 │   ├── compliance/
 │   ├── analytics/
 │
 ├── ai/
 │   ├── models/
 │   ├── training/
 │   ├── inference/
 │   ├── rag/
 │   ├── multilingual/
 │
 ├── infrastructure/
 │   ├── scrapers/
 │   ├── storage/
 │   ├── db/
 │
 ├── ui/

Rules:
- Move ml/, rag/, multilingual → ai/
- Move scrapers → infrastructure
- Split services into domain-based structure


---

## 2. MODEL JUSTIFICATION

Analyze:
- csp_xgboost_model.py
- csp_wcs_scorer.py
- csp_training_pipeline.py
- rag/qa_engine.py
- multilingual modules

Produce:
- Purpose of each model
- Why selected
- Why not deep learning
- Zimbabwe data constraints justification


---

## 3. SYNTHETIC DATA GENERATION

Dataset:
- 1500+ rows

Fields:
- insurer_name
- solvency_ratio
- claims_ratio
- premium_growth
- risk_score
- compliance_score

Requirements:
- Zimbabwe insurance context
- Include anomalies:
  - high claims + low solvency
  - inconsistent growth patterns

Save to:
storage/training_data/insurance_synthetic.csv


---

## 4. KNOWLEDGE BASE FIX

Files:
- rag/qa_engine.py
- rag/vector_store.py

Fix:
- Add try/except
- Handle empty retrieval
- Add logging
- Prevent crashes


---

## 5. UI IMPROVEMENTS

Fix:
- Error visibility

Use:
- color: #ff4d4f
- background: #fff1f0

Apply to:
- Forms
- Alerts
- Exception messages


---

## 6. OUTPUT REQUIREMENTS

Generate the following files:

1. md_files/output/system_upgrade_report.md
   - Architecture changes
   - Files moved
   - Fixes applied

2. md_files/output/model_justification_final.txt

3. md_files/output/data_generation_report.md

4. md_files/output/kb_ui_fixes.md

Ensure:
- No hallucination
- Only reflect actual code changes