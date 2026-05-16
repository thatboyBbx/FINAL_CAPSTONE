You are a senior developer performing a structural cleanup and UI unification on a FastAPI + Jinja2 project.

CONTEXT:
The project currently has TWO competing UI systems:
1. Old standalone templates (e.g., master.html, root-level templates using rgb(var(--os)))
2. New base.html system (uses var(--cos), structured layout, modern navigation)

Your job is to CONSOLIDATE into ONE system (base.html) and eliminate conflicts.

---

PRIMARY GOAL:
Make base.html the SINGLE source of truth for layout, styling, and navigation.

---

PHASE 1 — STRUCTURAL CLEANUP (MANDATORY FIRST)

1. REMOVE OR DISABLE:
   - master.html (completely remove or ensure it is never used)
   - All root-level legacy templates that duplicate subdirectory templates
   - _shared_head.html (orphaned)
   - partials/sidebar.html (empty, misleading)

2. KEEP ONLY:
   - Templates that EXTEND base.html
   - Subdirectory-based structure (documents/, analysis/, intelligence/, reports/, clients/)

3. RESOLVE DUPLICATES:
   - Keep ONLY:
     documents/upload.html (remove root upload.html)
     documents/index.html (remove documents.html)
     analysis/* (remove analytics.html)
     intelligence/* (remove advisory.html, insurer_intelligence.html, insurers_intel.html)
     system/index.html (remove scraper_status.html)

4. ENSURE:
   - All remaining templates extend base.html
   - No standalone layouts remain (except login/register)

---

PHASE 2 — DESIGN SYSTEM UNIFICATION

1. REMOVE old CSS variable system:
   - Eliminate rgb(var(--os)), rgb(var(--p)), etc.
   - Standardize ONLY on base.html variables (var(--cos), etc.)

2. STANDARDIZE BUTTONS:
   - Use ONLY one system:
     .btn, .btn-primary, .btn-secondary, etc.
   - Remove conflicting variants (.btn-glass if redundant)

3. CLEAN STYLING:
   - Remove inline styles
   - Apply consistent spacing using a single pattern

---

PHASE 3 — NAVIGATION FIX

1. Use ONLY the base.html sidebar (accordion)
2. Remove stale routes:
   - /upload-ui → /documents/upload
   - /documents-ui → /documents/index
   - /analytics → /analysis/ml

3. FIX ACTIVE STATES:
   - Ensure only ONE active item at a time
   - Parent should not double-highlight with children

4. REMOVE DUPLICATE FEATURES:
   - Consolidate Policy Tracker into ONE location

---

PHASE 4 — MVP SCOPING

HIDE (do not delete, just remove from navigation):
- Multilingual Analysis
- NER
- Settlement Power
- Advisory Engine
- Batch Portfolio
- Kanban features
- Chatbot (if incomplete)

---

OUTPUT REQUIREMENTS:
- Provide FULL updated files
- Clearly indicate removed files
- No explanations
- Do NOT modify backend logic unless required to fix routing inconsistencies

---

CONSTRAINT:
Do NOT redesign everything — preserve working structure, only unify and clean.