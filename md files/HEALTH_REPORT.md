# InsureIntel Zimbabwe — MVP Health Report
**Date:** 2026-04-25  
**Fix Campaign:** Jobs A through E completed

---

## Critical Bugs Fixed

| # | Bug | Status |
|---|-----|--------|
| 1 | SECRET_KEY regenerating on restart | ✅ Fixed — static dev fallback key, production validation added |
| 2 | Zero route protection (RBAC) | ✅ Fixed — 19 router groups protected with `get_current_user` |
| 3 | pydantic[email] missing | ✅ Fixed — added + email-validator to requirements.txt |
| 4 | Dead circulars_router registered | ✅ Fixed — removed from main.py |
| 5 | Deprecated on_event("startup") | ✅ Fixed — lifespan context manager |
| 6 | Single Alembic migration for 27 tables | ✅ Fixed — baseline migration created (9e599c7786d4) |
| 7 | Anthropic paid API in chatbot | ✅ Fixed — offline rule-based engine (13 intents) |
| 8 | Anthropic paid API in Q&A engine | ✅ Fixed — offline keyword search over document text |
| 9 | Broken buttons (href="#") | ✅ Fixed — all wired or "coming soon" modal |
| 10 | window.alert() error messages | ✅ Fixed — styled modal banners via showErrorModal() |

---

## Final Audit Results (E3 Checks)

| Check | Description | Result |
|-------|-------------|--------|
| 1 | No `import anthropic` in app code | ✅ PASS |
| 2 | No deprecated `on_event` usage | ✅ PASS |
| 3 | No `secrets.token_urlsafe()` in config | ✅ PASS |
| 4 | API routers with auth dependency | ✅ PASS — 19 routers protected |
| 5 | `/auth/login` public (422 on bad input, not 401) | ✅ PASS |
| 5b | `/health` endpoint returns 200 | ✅ PASS — `{"status":"ok","env":"dev"}` |
| 5c | `/documents/` without auth → redirect | ✅ PASS — 307 to login |
| 6 | `function apiFetch` in api.js | ✅ PASS |
| 7 | No dead `href="#"` without onclick in templates | ✅ PASS — 0 occurrences |

---

## Test Results

| Metric | Count |
|--------|-------|
| Total tests | **72** |
| Passing | **72** |
| Failing | **0** |

**Test files:**
- `tests/conftest.py` — fixtures: setup_db, db, client, test_user, auth_headers, auth_client, authenticated_client
- `tests/test_chatbot.py` — 6 tests (greeting, IPEC intent, CSP intent, fallback, auth required, help intent)
- `tests/test_clients.py` — 6 tests (CRUD, expiry, renewals)
- `tests/test_compliance.py` — 3 tests (statistics, invalid ID, missing doc)
- `tests/test_csp_module.py` — 13 tests (WCS formula, normalizer, NLG, fuzzy lookup, SHAP)
- `tests/test_documents.py` — 5 tests (upload, list, folder, compare)
- `tests/test_insurers.py` — 4 tests (CSV import, list, not found)
- `tests/test_reports.py` — 3 tests (missing body, invalid doc, bad type)
- `tests/test_settlement_power.py` — 6 tests (WCS formula, class scorer, HTTP)
- `tests/test_ui_routes.py` — 26 tests (all category/sub-page routes)

---

## Alembic Migration State

| Revision | Description | Status |
|----------|-------------|--------|
| `001_add_document_folder_client_id` | Add folder & client_id columns to documents | Applied |
| `9e599c7786d4` | baseline_full_schema_post_fix_campaign | Applied (HEAD) |

**Current head:** `9e599c7786d4`  
**DB tables tracked:** 27 tables across all modules

---

## App Stats

| Metric | Value |
|--------|-------|
| Total registered routes | 183 |
| Protected router groups | 19 |
| Public routes | `/login`, `/register`, `/logout`, `/health`, `/` |
| Offline features | Chatbot (13 intents), Document Q&A (keyword search), Full NLP pipeline |
| Authentication | JWT (HS256) via cookie + Authorization header |

---

## Known Limitations (not bugs — documented for dissertation)

- **OCR accuracy:** ~87% avg confidence (Tesseract) — acceptable for thesis demo
- **NER model:** Trained on ~50 documents — requires more training data for production
- **CSP weights** (35/30/20/15) require ablation study validation for dissertation defence
- **Shona translation accuracy** varies — formal legal terms translate better than colloquial
- **Chatbot:** Rule-based pattern matching (13 intents) — no LLM integration; this is the architectural choice justified in the dissertation as a controlled, reproducible baseline (Manning et al., 2008)

---

## MVP Status: READY FOR DEMONSTRATION

All critical bugs from the fix campaign (Jobs A–E) are resolved. The platform operates fully offline with no external API dependencies. Test suite achieves 100% pass rate (72/72). Authentication protects all data-bearing routes. Alembic migration history is clean and the schema baseline is documented.

**Signed off by E3 — Senior Code Reviewer**  
**Date:** 2026-04-25
