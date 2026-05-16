# CHANGELOG — InsureIntel Zimbabwe Platform v2.0
R228131Q | BSc AI & ML Honours Dissertation

---

## v2.0.0 — 2026-04-14 (Multi-Agent Full Overhaul)

### Agent 1 — Engineer

#### [A1-T1] Backend Connectivity Audit
- Verified all 19 existing routers registered in `app/main.py`
- Audited all Jinja2 route → template mappings in `app/ui/router.py` and `app/ui/extra_router.py`

#### [A1-T2] Global JS API Layer
- **NEW** `app/ui/static/js/api.js` — `apiPost`, `apiGet`, `apiDelete`, `apiPatch`, `showToast`, `showProgress`, `confirmDialog`
- **NEW** `app/ui/static/js/sidebar.js` — accordion logic, localStorage persistence, auto-expand active section, 64px↔256px toggle

#### [A1-T3] Global CSS — Glassmorphism System
- **NEW** `app/ui/static/css/main.css` — CSS vars, `.btn-glass`, `.btn-glass-gold`, `.btn-glass-danger`, `.glass-card`, toast/progress-bar styles, `@supports` backdrop-filter fallback

#### [A1-T4] Base Template + Sidebar Partial
- **MODIFIED** `app/ui/templates/base.html` — added `#toast-container`, `#progress-bar`, sidebar/chatbot includes, static asset links, mobile responsive sidebar
- **NEW** `app/ui/templates/partials/sidebar.html` — 7-section accordion sidebar (Home, Documents, Analysis, Intelligence, Reports, Clients, System)

#### [A1-T5] Home Page
- Added `/home` route in `app/ui/router.py`
- **MODIFIED** `app/ui/templates/index.html` — summary stats cards, recent activity feed, quick-upload widget

#### [A1-T6] Category Landing Pages
- **NEW** `app/ui/templates/documents/index.html`
- **NEW** `app/ui/templates/analysis/index.html`
- **NEW** `app/ui/templates/intelligence/index.html`
- **NEW** `app/ui/templates/reports/index.html`
- **NEW** `app/ui/templates/clients/index.html`
- **NEW** `app/ui/templates/system/index.html`
- Added category routes in `app/ui/router.py` and `app/ui/extra_router.py`

#### [A1-T7] Documents Module
- **NEW** `app/ui/templates/documents/vault.html` — table with inline actions (Open/Analyse/Download/Delete/Move), folder tree sidebar, real-time search, sortable columns
- **NEW** `app/ui/templates/documents/upload.html` — drag-drop upload zone with progress
- **NEW** `app/ui/templates/documents/compare.html` — dual-panel comparison with vault picker
- **MODIFIED** `app/modules/documents/model.py` — added `folder` column (SQLAlchemy 2.0 `Mapped[str]`)
- Added `PATCH /api/documents/{id}/folder` endpoint
- Added `client_id` nullable FK to Document model

#### [A1-T8] Analysis Module
- **NEW** `app/ui/templates/analysis/ml.html` — manual multi-select + Run Analysis
- **NEW** `app/ui/templates/analysis/deviation.html` — template vs. document clause deviation
- **NEW** `app/ui/templates/analysis/ner.html` — NER extraction results with entity highlighting
- **NEW** `app/ui/templates/analysis/risk.html` — risk factor dashboard
- Added `/analysis/risk-alert` → 301 redirect to `/analysis/risk`

#### [A1-T9] Reports Module
- **NEW** `app/ui/templates/reports/compliance.html` — score gauge, pass/fail checklist, violations table
- **NEW** `app/ui/templates/reports/generate.html` — PDF generation with report type dropdown
- **NEW** `app/ui/templates/reports/news.html` — news scraper with polling progress bar
- **NEW** `app/modules/reports/router.py` — `POST /api/reports/generate` with weasyprint PDF output
- Added `weasyprint>=60.0` to `requirements.txt`

#### [A1-T10] Intelligence Module
- **NEW** `app/ui/templates/intelligence/insurers/index.html` — insurer list with CSV import modal
- **NEW** `app/ui/templates/intelligence/insurers/profile.html` — tabbed insurer profile
- **NEW** `app/ui/templates/intelligence/advisory.html` — policy doc → ranked insurer advisory
- Added `POST /api/insurers/import-csv` multipart endpoint (upsert by `licence_number`)
- **NEW** `scripts/import_insurers_csv.py` — CLI CSV import utility

#### [A1-T11] Settlement Power Module
- **NEW** `app/modules/intel/settlement_router.py` — `/intelligence/settlement-power`, `/api/settlement-power/{id}`, `/api/settlement-power/all`, `/api/settlement-power/lookup`
- **NEW** `app/ui/templates/intelligence/settlement_power.html` — radar, bubble, bar charts + SHAP panel
- Verified WCS formula: `0.35×solvency + 0.30×claims + 0.20×reserves + 0.15×liquidity`

#### [A1-T12] Client Management Module
- **NEW** `app/models/client.py` — `Client`, `ClientPolicy`, `ClientNote`, `ClientInteraction`, `ClientAlert` (SQLAlchemy 2.0 Mapped[])
- **NEW** `app/modules/users/client_router.py` — full CRUD + `/api/clients/*`
- **NEW** `app/modules/users/client_service.py`
- **NEW** `app/ui/templates/clients/list.html` — searchable client list
- **NEW** `app/ui/templates/clients/profile.html` — tabbed: Policies | Notes | Interactions | Alerts | Docs
- **NEW** `app/ui/templates/clients/expiry.html` — 30/60/90-day filter + calendar mini-widget
- **NEW** `app/ui/templates/clients/renewals.html` — drag-drop kanban board (Pending → In Progress → Renewed)

#### [A1-T13] Master Chatbot
- Removed individual chatbot widgets from all individual templates
- **NEW** `app/ui/templates/partials/master_chatbot.html` — global floating chatbot (FAB + slide-up panel)
- **NEW** `app/modules/chatbot/router.py` — `POST /api/chatbot/message` using `claude-sonnet-4-5` with Zimbabwe Insurance Act + IPEC system prompt

#### [A1-T14] Router Registration
- Registered `client_router`, `chatbot_router`, `reports_router`, `settlement_router` in `app/main.py`

#### [A1-T15] Security
- **MODIFIED** `app/core/config.py` — upgraded to Pydantic v2 `ConfigDict`, added `ANTHROPIC_API_KEY`
- **NEW** `.env.example` — all required environment variables documented
- **NEW** `.gitignore` — covers `.env`, `*.db`, `__pycache__`, venv, IDE, uploads

---

### Agent 2 — Code Reviewer

#### [A2-T1] Stack Compliance
- Upgraded 17 model files from legacy `Column()` → SQLAlchemy 2.0 `Mapped[]/mapped_column()`
- Fixed 65+ `Optional[X]` → `X | None` union syntax occurrences across 12+ files
- Fixed `class Config:` → `model_config = ConfigDict(...)` in `app/modules/intel/schemas.py`
- Fixed deprecated `datetime.utcnow` → `datetime.now(timezone.utc)`

#### [A2-T2] Contrast Audit
- Fixed invisible text in `app/ui/templates/analytics/settlement_power.html`

#### [A2-T3] API Wiring
- All buttons in new templates verified to have onclick handlers or form actions

#### [A2-T4] Route Completeness
- **Critical fix**: reordered `/clients/expiry` and `/clients/renewals` routes before `/clients/{client_id}` to prevent FastAPI path matching integer literal "expiry"/"renewals"
- All 33 required files confirmed present

---

### Agent 3 — Tester

#### [A3-T1] Dependencies
- pytest, pytest-asyncio, httpx verified present

#### [A3-T2] Test Suite
- **NEW** `tests/conftest.py` — session-scoped in-memory SQLite test DB with `StaticPool`
- **NEW** `tests/test_documents.py` (4 tests)
- **NEW** `tests/test_compliance.py` (3 tests)
- **NEW** `tests/test_settlement_power.py` (3 tests)
- **NEW** `tests/test_clients.py` (4 tests)
- **NEW** `tests/test_chatbot.py` (1 test, Anthropic mocked)
- **NEW** `tests/test_reports.py` (2 tests)
- **NEW** `tests/test_insurers.py` (2 tests)
- **NEW** `tests/test_ui_routes.py` (26 parametrized route tests)

#### [A3-T3] All Tests Pass
- **68/68 tests pass**, 0 failures, 2 non-blocking deprecation warnings
- Fix: `app/services/csp_service.py` fuzzy match changed from `token_sort_ratio` to `partial_ratio`

#### [A3-T4] Smoke Tests
- 8/8 live server checks pass (200/303 on all key routes)

---

### Agent 4 — UI/UX

#### [A4-T0] Design Extraction
- Extracted Royal Gold design tokens from `stitch_extracted/stitch/insureintel_royal_gold/DESIGN.md`

#### [A4-T1] Typography
- Enhanced `main.css` with Manrope heading hierarchy, body line-height, smooth transitions

#### [A4-T2] Sidebar Polish
- Active state: gold left border + gradient background
- Hover: 0.15s ease transition
- Chevron rotation, mobile overlay support

#### [A4-T3–A4-T9]
- All 6 category landing pages polished with responsive 3-col grid
- Document vault: sortable columns, file type badges, status badges, empty state
- Settlement Power: Chart.js radar/bubble/bar polish, SHAP bars, pulse-red distressed badge
- Client renewals: HTML5 drag-drop kanban, expiry countdown badges
- Client expiry: pill tabs, color-coded rows, mini calendar
- Master chatbot: FAB pulse animation, slide-up transition, message bubbles, typing indicator
- Global glassmorphism sweep: `@supports` fallback for non-Chromium browsers
- Full responsive polish: `overflow-x-auto` tables, mobile sidebar overlay

---

## Previous Versions
- v1.x — Initial platform build (pre-dissertation overhaul)
