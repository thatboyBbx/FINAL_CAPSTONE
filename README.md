# InsureIntel Zimbabwe — Platform v2.0
**R228131Q | BSc Artificial Intelligence & Machine Learning (Honours) Dissertation**

An AI-powered insurance document intelligence platform built for the Zimbabwean insurance brokerage sector. Provides NER-based document analysis, compliance checking, settlement power scoring (WCS/CSP), and conversational document Q&A — all within a Jinja2 + FastAPI + Tailwind glassmorphic UI.

---

## Architecture

```
app/
├── core/           config.py, db.py, logging.py
├── models/         insurer.py, insurer_financials.py, csp_score.py, client.py
├── modules/
│   ├── auth/       JWT auth (cookie-based)
│   ├── documents/  upload, OCR, NER, compliance pipeline
│   ├── insurers/   insurer CRUD, CSV import, IPEC data
│   ├── intel/      insurer intelligence, settlement router
│   ├── ml/         ML analysis endpoints
│   ├── news/       GDELT news scraping + article storage
│   ├── qa/         Conversational RAG Q&A (ChromaDB)
│   ├── comparison/ Hungarian-algorithm document comparison
│   ├── deviation/  Clause deviation scoring
│   ├── feedback/   Active learning feedback loop
│   ├── batch/      Portfolio batch processing
│   ├── tracker/    Policy tracker
│   ├── audit/      Audit trail middleware + logger
│   ├── multilingual/ Shona-English support
│   ├── users/      Client management (NEW v2.0)
│   ├── chatbot/    Master chatbot — claude-sonnet-4-5 (NEW v2.0)
│   └── reports/    PDF report generation via weasyprint (NEW v2.0)
├── ml/             csp_wcs_scorer.py, csp_xgboost_model.py
├── services/       compliance_checker.py, advisory_service.py, csp_service.py, ...
├── scrapers/       news_scraper.py, ipec_scraper.py, zse_scraper.py
├── deviation/      clause_scorer.py, knowledge_base_seeder.py
├── comparison/     comparison_service.py, clause_aligner.py
├── tracker/        policy_tracker_service.py
├── feedback/       feedback_store.py, retraining_pipeline.py
├── audit/          audit_logger.py, audit_middleware.py
├── api/routes/     csp_routes.py
└── ui/
    ├── router.py           Primary UI routes
    ├── extra_router.py     Secondary UI routes
    ├── static/
    │   ├── js/api.js       Global fetch API layer + toast/progress (NEW v2.0)
    │   └── js/sidebar.js   Accordion sidebar + localStorage (NEW v2.0)
    │   └── css/main.css    Glassmorphism system + CSS vars (NEW v2.0)
    └── templates/
        ├── base.html                   Master layout (dark Royal Gold theme)
        ├── partials/sidebar.html       7-section accordion sidebar
        ├── partials/master_chatbot.html Global floating chatbot
        ├── documents/                  vault, upload, compare
        ├── analysis/                   ml, deviation, ner, risk
        ├── intelligence/               insurers/, settlement_power, advisory
        ├── reports/                    compliance, generate, news
        ├── clients/                    list, profile, expiry, renewals
        └── system/                     settings, audit, active-learning
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + FastAPI |
| ORM | SQLAlchemy 2.0 (`Mapped[]`/`mapped_column()`) |
| Validation | Pydantic v2 (`ConfigDict`) |
| Database (dev) | SQLite (`app.db`) |
| Vector DB | ChromaDB |
| Templates | Jinja2 |
| CSS | Tailwind CSS (CDN) + custom glassmorphism (`main.css`) |
| JS | Vanilla JS + Chart.js (CDN) |
| ML | spaCy 3.7, XGBoost 2.0, scikit-learn, SHAP, sentence-transformers |
| LLM | Anthropic claude-sonnet-4-5 (chatbot + advisory) |
| PDF | weasyprint |
| Auth | JWT (python-jose) + bcrypt, cookie-based |

---

## Setup

### 1. Clone & create environment
```bash
git clone <repo>
cd EXPERIMENT
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env and fill in:
#   SECRET_KEY=<random 32-char hex>
#   ANTHROPIC_API_KEY=<your-key>
#   DATABASE_URL=sqlite:///./app.db  (default)
```

### 3. Run the server
```bash
uvicorn app.main:app --reload --port 8000
```
Open http://localhost:8000 — register an account, then log in.

### 4. Import insurers (optional)
```bash
python scripts/import_insurers_csv.py insurers.csv
# Or via the UI: Intelligence → Insurer Intel → [Import CSV]
```

---

## Key Features (v2.0)

### Navigation
- **Accordion sidebar** — 7 sections, single-open, localStorage state persistence, 64px collapsed / 256px expanded, mobile overlay
- **Global chatbot** — floating FAB (bottom-right), slide-up panel, document-aware, sessionStorage conversation history

### Documents
- **Vault** — folder organisation, inline action buttons (Open / Analyse / Download / Delete / Move), real-time search, sortable columns, file type + status badges
- **Upload** — drag-drop, progress bar
- **Compare** — dual-panel, vault picker or direct upload, clause-level diff

### Analysis
- **ML Analytics** — manual multi-select batch analysis (risk + NER + clause)
- **Clause Deviation** — template vs. document scoring via `app/deviation/clause_scorer.py`
- **NER Extraction** — entity highlighting (insurer, policy, clause, monetary, date entities)
- **Risk Analysis** — factor scoring and recommendations

### Intelligence
- **Insurer Intel** — full profile view (IPEC licence, solvency, CSP, news), CSV import
- **Settlement Power (WCS)** — radar/bubble/bar charts, SHAP explanation, XGBoost anomaly detection
  - Formula: `WCS = 0.35×solvency + 0.30×claims + 0.20×reserves + 0.15×liquidity`
- **Advisory** — policy doc → ranked insurer match with gap analysis

### Reports
- **Compliance Engine** — IPEC/ICA compliance check, 0-100 score gauge, violation table
- **Generate Report** — executive / detailed / compliance PDF download (weasyprint)
- **News Feed** — GDELT scraper with real-time progress polling

### Client Management
- **Client List** — search, segment filter (retail/corporate/SME), sort
- **Client Profile** — tabbed: Policies | Notes | Interactions | Alerts | Documents
- **Policy Expiry** — 30/60/90-day tabs, color-coded rows, mini calendar
- **Renewal Tracker** — drag-drop kanban (Pending → In Progress → Renewed)

### System
- **Settings**, **Audit Log**, **Active Learning** feedback interface

---

## Testing

```bash
pytest tests/ -v
# 68 tests, 0 failures
```

Test files:
- `tests/test_documents.py` — upload, list, folder, compare
- `tests/test_compliance.py` — compliance endpoint validation
- `tests/test_settlement_power.py` — WCS formula unit test + HTTP
- `tests/test_clients.py` — client CRUD + expiry/renewals
- `tests/test_chatbot.py` — Anthropic mock
- `tests/test_reports.py` — PDF generation validation
- `tests/test_insurers.py` — CSV import + list
- `tests/test_ui_routes.py` — 26 UI route smoke tests (200/302/303)

---

## Dissertation Mapping

| Chapter | Platform Evidence |
|---------|-----------------|
| System Architecture | `app/main.py` — 23 registered routers, modular structure |
| NLP Pipeline | `app/modules/documents/` — OCR → classify → NER → compliance → risk |
| Risk Scoring (WCS) | `app/ml/csp_wcs_scorer.py` — weighted formula, SHAP explainability |
| LLM Integration | `app/modules/chatbot/`, `app/services/advisory_service.py` |
| Regulatory Compliance | `app/services/compliance_checker.py` — Zimbabwe ICA Chapter 24:07 |
| Active Learning | `app/modules/feedback/`, `app/modules/deviation/` |
| Evaluation Evidence | `tests/test_results.txt`, `tests/test_settlement_power.py` (WCS unit test) |

---

## Environment Variables

See `.env.example` for full list. Required:
- `SECRET_KEY` — JWT signing key
- `ANTHROPIC_API_KEY` — for chatbot + advisory features
- `DATABASE_URL` — defaults to `sqlite:///./app.db`
