# UI REDESIGN SPECIFICATION (INTERNAL)
**EXP_V3 → Modern InsurTech Interface**  
**Status**: Architecture, 4-Agent Team Composition  
**Stack**: Tailwind CSS + Vanilla JS + Jinja2 (NO React)  
**Theme**: Dark/Light Mode Toggle (localStorage-based) + Glassmorphism Aesthetic

---

## 1. AUDIT FINDINGS

### Current State
- **59 Jinja2 templates** across `/app/ui/templates/` (highly fragmented)
- **3 static files**: `main.css`, `api.js`, `sidebar.js` (CSS has glassmorphism foundation but JS is incomplete)
- **Routes**: 40+ endpoints in `router.py` 
- **Problem Pages**: 
  - `circulars_ui.html` (DATA-ONLY MODULE; must be removed from UI entirely)
  - Orphaned pages: `analytics.html`, `zse_market.html` (routes exist but unmaintained)
  - Dead button links: Missing validation, no error modals
  - Inconsistent styling: Mix of inline styles + classes + missing Tailwind

### UI Debt
- **No centralized navigation**: 59 templates, 0 shared layout structure
- **Button routing broken**: Many buttons link to non-existent routes (e.g., `/api/nonexistent`)
- **Dark mode half-implemented**: CSS vars exist but JS toggle missing
- **Mobile responsiveness**: Minimal breakpoint handling
- **Accessibility**: No ARIA labels, contrast issues on light mode

---

## 2. DESIGN SYSTEM (REFERENCE AESTHETIC)

### Color Palette (from Figma it-app.js reference)
**Dark Mode (default)**:
- **Primary Accent**: `#d4af37` (gold/royal)
- **Background**: `#0f0f0f` (ultra-dark) | `#1a1a1a` (card bg)
- **Text Primary**: `#f5f5f5` | **Secondary**: `#a1a1a1`
- **Border**: `rgba(212,175,55,0.15)` (subtle gold)

**Light Mode**:
- **Primary Accent**: `#004ac6` (deep blue)
- **Background**: `#ffffff` (white) | `#f8f9fb` (card bg)
- **Text Primary**: `#191c1e` | **Secondary**: `#434655`
- **Border**: `rgba(0,74,198,0.12)` (subtle blue)

### Typography
- **Headlines (h1-h3)**: Poppins Bold | 24px / 20px / 16px
- **Body**: Inter Regular | 14px | line-height 1.6
- **Labels**: Inter Semibold | 12px
- **Monospace** (code): `Courier New` | 12px

### Components
- **Buttons**: `.btn-glass`, `.btn-glass-gold`, `.btn-glass-danger` (glassmorphism with backdrop-filter)
- **Cards**: `.glass-card` (frosted background + subtle border)
- **Input**: Tailwind form styling + custom focus states
- **Sidebar**: Collapsible accordion (6 sections) + hamburger mobile toggle
- **Modals**: Error/success toasts via `#toast-container` + styled modal overlays

---

## 3. INFORMATION ARCHITECTURE

### Primary Navigation (6-Section Accordion)

#### 1. **Documents**  
- `/documents-ui` → Vault (list all uploaded documents)
- `/documents-ui/{doc_id}` → Document Detail Viewer
- `/documents-ui/compare` → Comparison Tool (2-doc side-by-side)
- `/upload-ui` → Drag-drop uploader + batch

#### 2. **Analysis**  
- `/analysis/ner` → Entity Extraction Results
- `/analysis/risk` → Risk Assessment Dashboard
- `/analysis/deviation` → Clause Deviation Scoring
- `/analysis/ml` → ML Predictions & Confidence

#### 3. **Intelligence**  
- `/intelligence/index` → Landing page (3-tile grid)
- `/intelligence/insurers` → Insurer Intelligence Hub
- `/intelligence/insurers/{id}` → Insurer Profile + CSP Score
- `/intelligence/settlement-power` → Settlement Power Matrix
- `/intelligence/advisory` → Advisor-generated recommendations

#### 4. **Reports**  
- `/reports/index` → Landing page (generate / history)
- `/reports/generate` → Report builder (compliance, news, custom)
- `/reports/compliance` → Compliance checklist export
- `/reports/news` → News & sentiment summary (silent backend, citations only)

#### 5. **Client Management**  
- `/clients/index` → Client CRM dashboard
- `/clients/list` → Client directory
- `/clients/profile/{id}` → Client detail page
- `/clients/expiry` → Policy expiry timeline
- `/clients/renewals` → Renewal tracker

#### 6. **System**  
- `/system/index` → Settings, audit log, scraper status
- `/settings` → User preferences + theme toggle
- `/scraper-status` → Background job monitoring
- `/audit-trail` → Event audit log (viewer only)

#### Standalone
- `/home` → Main dashboard (KPI summary, quick actions)
- `/login` → Auth gateway
- `/register` → New user signup
- `/logout` → Session cleanup

---

## 4. AGENT TEAM BREAKDOWN

### **Agent 1: Layout Architect** (Lead)
**Duration**: 4–6 hours | **Deliverables**: Base templates, theme system, navigation

**Tasks**:
1. Create `base.html` master layout:
   - Head block (meta, Tailwind CDN, CSS vars, dark-mode script)
   - Sidebar accordion structure (6 sections + collapsible mobile)
   - Main content area with `{% block content %}`
   - Toast container + progress bar
   - Dark/light toggle button (HTML only, JS in Agent 4)
2. Create `_shared_head.html` partial for all page `<head>` elements
3. Create `partials/sidebar.html` accordion with:
   - 6 collapsible sections (Documents, Analysis, Intelligence, Reports, Clients, System)
   - Navigation links per section (route hierarchy from IA above)
   - Active state detection via `request.url.path`
   - Mobile hamburger toggle
4. Create `partials/navbar.html` (top bar):
   - Logo/brand on left
   - Search icon (placeholder)
   - User dropdown (Profile, Settings, Logout)
   - Theme toggle button (icon only, JS in Agent 4)
5. Create `/partials/toasts.html` reusable modal structure:
   - Success toast (green border, gold accent on dark)
   - Error toast (red border, red text)
   - Info toast (blue border)
   - Auto-dismiss JavaScript included
6. Set CSS variables in `style block` of `base.html` (NO separate CSS file yet):
   - Primary accent (gold/blue depending on mode)
   - All semantic colors (text, bg, border)
   - Sidebar width variables

**Output**: 6 new Jinja2 files + inline `<style>` in base.html

---

### **Agent 2: Component Library** 
**Duration**: 5–8 hours | **Deliverables**: 12 reusable Jinja2 components + supporting CSS

**Tasks**:
1. Create **reusable macro components** in `/partials/components.html`:
   - `button_primary(label, href, onclick, disabled)` → `.btn-glass-gold`
   - `button_secondary(label, href)` → `.btn-glass`
   - `button_danger(label, onclick)` → `.btn-glass-danger`
   - `card(title, content, footer)` → `.glass-card` wrapper
   - `input_text(name, label, placeholder, value, required)` → Tailwind form input
   - `input_file(name, label, accept)` → Custom file input styled
   - `select_dropdown(name, label, options, selected)` → Styled select
   - `toggle_checkbox(name, label, checked)` → Custom checkbox
   - `badge_status(status)` → `.badge-status-*` (pending, processing, complete, error)
   - `badge_type(type)` → `.badge-type-*` (pdf, docx, img, other)
   - `table_striped(headers, rows)` → `.data-table` with alternating rows
   - `tile_grid(tiles)` → 3-col grid (responsive) with `.tile-card` hover effects

2. Create supporting CSS file `/static/css/components.css`:
   - All component styles referenced by macros
   - Glassmorphism effects (blur, saturate, border-color)
   - Tailwind utility integration (no conflicts)
   - Dark/light mode overrides via CSS vars

3. Add utility classes to `components.css`:
   - `.space-x-*`, `.space-y-*` (margin helpers)
   - `.text-truncate`, `.text-ellipsis` (text overflow)
   - `.fade-in`, `.slide-up` (micro-animations)
   - `.loading-pulse` (skeleton screen animation)

**Output**: 2 files (`/partials/components.html` + `/static/css/components.css`)

---

### **Agent 3: Core Pages (6/8 of them)**
**Duration**: 8–12 hours | **Deliverables**: 30+ page templates

**Tasks** (use Agent 2's macros everywhere):

**Landing Pages** (with tile grids):
- `/home` → Dashboard landing
  - KPI cards (doc count, avg risk score, pending analyses, system health)
  - Recent documents list (table)
  - Quick action buttons
- `/intelligence/index` → 3-tile grid (Insurers, Settlement Power, Advisory)
- `/reports/index` → 2-tile grid (Generate, History)
- `/clients/index` → CRM dashboard overview
- `/system/index` → Settings & monitoring dashboard

**List/Vault Pages**:
- `/documents-ui` → Document vault (search, filter by type, sort by date)
  - Table with `select_dropdown`, `badge_type`, status indicators
  - Bulk actions button row
  - Pagination (if >50 docs)
- `/clients/list` → Client directory
  - Search box + filter by status
  - Table with client name, policy count, last update
- `/intelligence/insurers` → Insurer list
  - Search + CSP score filter
  - Table with insurer name, CSP badge, last financials date
  - "View Profile" button per row

**Detail Pages**:
- `/documents-ui/{doc_id}` → Document detail viewer
  - Document metadata panel (left sidebar)
  - Main viewer area (embedded PDF/image or extracted text)
  - Analysis results panels (tabbed: NER, Risk, Deviation, ML)
  - Action buttons: Download, Archive, Share
- `/intelligence/insurers/{id}` → Insurer profile
  - CSP score card (large, with visual gauge)
  - Financials summary (table of last 3 quarters)
  - News sentiment timeline
  - Financial strength assessment text
- `/clients/profile/{id}` → Client detail
  - Contact info card
  - Policies table (active + expired)
  - Document history
  - Renewal alerts

**Action Pages**:
- `/documents-ui/compare` → 2-doc comparison side-by-side
  - Dropdowns to select 2 docs
  - Split-view with highlights of differences
  - Deviation summary panel
- `/upload-ui` → Drag-drop file uploader
  - Drag zone + file input button
  - Upload progress bar
  - Batch file list with clear button
  - Submit button

**Utility Pages**:
- `/intelligence/settlement-power` → CSP matrix visualization
  - Large table or scatter plot (Chart.js)
  - Filter by solvency/claims settlement capacity
  - Row details expansion
- `/intelligence/advisory` → Advisor recommendations (text-based)
  - Recommendation cards (one per risk category)
  - Action items list
  - Suggested clause alternatives
- `/reports/compliance` → Compliance report template
  - Checkbox table (regulatory requirements + pass/fail)
  - Summary card
  - Export button (PDF)
- `/reports/generate` → Report builder wizard
  - Step 1: Select document(s)
  - Step 2: Choose report type (compliance, risk, news)
  - Step 3: Customize fields
  - Step 4: Preview + Generate (button)
- `/settings` → User settings page
  - Profile form (name, email, role read-only)
  - Theme toggle (radio buttons: Dark / Light)
  - Notification prefs checkboxes
  - Password change form
  - Delete account button (danger style)
- `/scraper-status` → Job monitor
  - List of scheduled scrapers (status badges)
  - Last run timestamp per scraper
  - Manual trigger buttons
  - Log viewer (accordion per scraper)
- `/audit-trail` → Audit log viewer
  - Table (user, action, timestamp, IP)
  - Filter by user / action type / date range
  - Export button

**Output**: 30 .html files

---

### **Agent 4: Interactivity & Polish**
**Duration**: 6–10 hours | **Deliverables**: JS, final CSS, dark/light toggle, error handling

**Tasks**:

1. **Dark/Light Mode Toggle** (`/static/js/theme.js`):
   - Read localStorage for `theme` (default: "dark")
   - Add/remove `.dark` class on `<html>`
   - Apply CSS var overrides via `document.documentElement.style.setProperty()`
   - Bind toggle button click → localStorage update + page re-render
   - Persist across page reloads

2. **Master API client** (`/static/js/api-client.js`):
   - Fetch wrapper for all `/api/` calls
   - Auto-inject auth token from sessionStorage
   - Error handling: catch non-2xx → show toast + log
   - Success handling: show brief success toast (2s dismiss)
   - Loading state: show progress bar (top 3px gold)
   - **NO network calls allowed to external domains** (only `/api/*`)

3. **Interactive components JS** (`/static/js/components.js`):
   - Sidebar accordion toggle: click section header → expand/collapse + rotate chevron
   - Mobile hamburger: click → toggle `.mobile-open` class on sidebar + show overlay
   - File input custom styling: click hidden input → trigger browser dialog
   - Drag-drop zone: `dragover`, `drop` events → file validation + list preview
   - Search filters: type in search → real-time table filtering (client-side)
   - Pagination: previous/next buttons → fetch next page batch
   - Modal close button: click X → remove modal from DOM

4. **Form validation** (`/static/js/forms.js`):
   - Document upload: check file type (pdf, docx, doc, png, jpg)
   - Email input: regex validation
   - Required fields: blur event → check non-empty
   - Error display: append `.text-red-500` message below input
   - On submit: validate all fields → if error, show toast + prevent submit

5. **Table interactions** (`/static/js/table.js`):
   - Sort by column: click `th.sortable` → fetch `/api/` with `?sort=field&dir=asc|desc`
   - Row selection: checkbox → enable bulk actions
   - Bulk delete: button → confirm toast → fetch `DELETE /api/*`
   - Expand row details: click row → fetch detail data + insert below row

6. **Error modal system** (`/static/js/errors.js`):
   - Global `window.showError(message, details)` function
   - Global `window.showSuccess(message)` function
   - Global `window.showConfirm(message, onYes)` function
   - Replace all browser `alert()` calls with styled modals
   - Modal styling: glassmorphic, centered, with close button

7. **CSS refinements** (`/static/css/polish.css`):
   - Fix light mode text contrast issues
   - Add micro-interactions (hover scale, focus ring)
   - Loading skeleton animations
   - Smooth transitions on all interactive elements
   - Responsive adjustments for tables on mobile (horizontal scroll)

8. **Remove dead code**:
   - Delete `circulars_ui.html`
   - Delete `zse_market.html` (orphaned)
   - Delete orphaned imports from `router.py`
   - Delete `/modules/circulars` references from UI

**Output**: 6 JS files + 1 polish CSS file + updated HTML files (remove circulars route handlers)

---

## 5. STITCH MCP INTEGRATION

**Agent 1** will use Stitch MCP **manually** to extract design tokens from Figma `it-app.js`:
1. Open Stitch MCP (configured in the terminal)
2. Fetch Figma design file (provided URL in PROMPT.txt)
3. Read design README + view `it-app.js` code output
4. **Extract ONLY**:
   - Color variables (input → CSS var names)
   - Typography scale (px sizes, weights)
   - Border radius / spacing increments
   - Shadow depths
5. **DO NOT** use Stitch's React code generation; manually transcribe aesthetic principles into CSS variables + Tailwind utilities

**Why**: Stitch outputs React JSX, but our stack is Jinja2. Agent 1 reads the design, extracts tokens, writes Tailwind config + CSS.

---

## 6. TECHNICAL CONSTRAINTS

### Stack Rules
- **NO React, Vue, Angular** — Vanilla JS only
- **NO external JS frameworks** — Vanilla DOM API only
- **Tailwind CSS** — required for styling (via CDN in `<head>`)
- **Jinja2** — all templating
- **No SPA routing** — traditional page-reload navigation
- **Dark mode**: CSS vars + localStorage (not Tailwind dark: variant)

### Performance
- **Lazy load images**: Add `loading="lazy"` to `<img>` tags
- **Minimize CSS**: Avoid unused Tailwind utilities
- **No external API calls** from JS — only `/api/` routes
- **Gzip responses**: Server-side (FastAPI handles)
- **CSS-in-head**: Inline critical CSS, defer non-critical to `<link>`
- **Font optimization**: System fonts only (Poppins, Inter as @font-face locally)

### Accessibility (A11y)
- `<button>` over `<a>` for actions
- `aria-label` on icon buttons
- `alt` text on images
- `role="navigation"` on nav elements
- Color contrast ≥4.5:1 for text
- Focus indicators visible (`:focus-visible` ring)

### Browser Support
- Chrome/Firefox/Safari/Edge (last 2 versions)
- iOS Safari 14+
- Android Chrome 90+
- No IE11 support

---

## 7. FILE STRUCTURE (Post-Redesign)

```
app/ui/
├── templates/
│   ├── base.html                    [Agent 1 - new]
│   ├── _shared_head.html            [Agent 1 - new]
│   ├── partials/
│   │   ├── sidebar.html             [Agent 1 - new]
│   │   ├── navbar.html              [Agent 1 - new]
│   │   ├── toasts.html              [Agent 1 - new]
│   │   ├── components.html          [Agent 2 - new]
│   │   └── csp_report_card.html     [keep, update styling]
│   │   └── master_chatbot.html      [keep, update styling]
│   ├── home.html                    [Agent 3 - new]
│   ├── login.html                   [Agent 3 - new, from Stitch]
│   ├── register.html                [Agent 3 - new, from Stitch]
│   ├── documents/
│   │   ├── index.html               [Agent 3 - new]
│   │   ├── upload.html              [Agent 3 - new]
│   │   └── compare.html             [Agent 3 - new]
│   ├── intelligence/
│   │   ├── index.html               [Agent 3 - new]
│   │   ├── insurers/
│   │   │   ├── index.html           [Agent 3 - new]
│   │   │   └── profile.html         [Agent 3 - new]
│   │   ├── advisory.html            [Agent 3 - new]
│   │   └── settlement_power.html    [Agent 3 - new]
│   ├── reports/
│   │   ├── index.html               [Agent 3 - new]
│   │   ├── generate.html            [Agent 3 - new]
│   │   ├── compliance.html          [Agent 3 - new]
│   │   └── news.html                [Agent 3 - new]
│   ├── clients/
│   │   ├── index.html               [Agent 3 - new]
│   │   ├── list.html                [Agent 3 - new]
│   │   ├── profile.html             [Agent 3 - new]
│   │   ├── expiry.html              [Agent 3 - new]
│   │   └── renewals.html            [Agent 3 - new]
│   ├── system/
│   │   ├── index.html               [Agent 3 - new]
│   │   ├── settings.html            [Agent 3 - new]
│   │   ├── audit_trail.html         [Agent 3 - new]
│   │   └── scraper_status.html      [Agent 3 - new]
│   └── [DELETE circulars_ui.html, zse_market.html, etc.]
├── static/
│   ├── css/
│   │   ├── main.css                 [KEEP but refactor]
│   │   ├── components.css           [Agent 2 - new]
│   │   └── polish.css               [Agent 4 - new]
│   └── js/
│       ├── api-client.js            [Agent 4 - new]
│       ├── theme.js                 [Agent 4 - new]
│       ├── components.js            [Agent 4 - new]
│       ├── forms.js                 [Agent 4 - new]
│       ├── table.js                 [Agent 4 - new]
│       ├── errors.js                [Agent 4 - new]
│       └── [DELETE old sidebar.js, api.js if fully replaced]
├── router.py                        [UPDATE: remove /circulars-ui, /zse routes]
└── extra_router.py                  [AUDIT: ensure all routes mapped]
```

---

## 8. ROUTE VALIDATION CHECKLIST

**Agent 3/4** must verify every route in `router.py` maps to a template + works:

- [ ] `GET /` → redirect to `/home` or serve dashboard
- [ ] `GET /home` → home.html ✓
- [ ] `GET /login` → login.html ✓
- [ ] `POST /login-ui` → validate + redirect ✓
- [ ] `GET /register` → register.html ✓
- [ ] `GET /logout` → clear session + redirect `/login` ✓
- [ ] `GET /documents-ui` → documents/index.html ✓
- [ ] `GET /documents-ui/{id}` → documents detail page ✓
- [ ] `GET /upload-ui` → documents/upload.html ✓
- [ ] `POST /upload-ui` → process + return JSON ✓
- [ ] `GET /intelligence/insurers` → intelligence/insurers/index.html ✓
- [ ] `GET /intelligence/insurers/{id}` → intelligence/insurers/profile.html ✓
- [ ] `GET /intelligence/settlement-power` → intelligence/settlement_power.html ✓
- [ ] `GET /intelligence/advisory` → intelligence/advisory.html ✓
- [ ] `GET /reports/index` → reports/index.html ✓
- [ ] `GET /reports/generate` → reports/generate.html ✓
- [ ] `GET /reports/compliance` → reports/compliance.html ✓
- [ ] `GET /reports/news` → reports/news.html ✓
- [ ] `GET /clients/index` → clients/index.html ✓
- [ ] `GET /clients/list` → clients/list.html ✓
- [ ] `GET /clients/profile/{id}` → clients/profile.html ✓
- [ ] `GET /system/index` → system/index.html ✓
- [ ] `GET /settings` → system/settings.html ✓
- [ ] `GET /audit-trail` → system/audit_trail.html ✓
- [ ] `GET /scraper-status` → system/scraper_status.html ✓
- [ ] ~~`GET /circulars-ui`~~ → **DELETE**
- [ ] ~~`GET /zse-market`~~ → **DELETE**
- [ ] ~~`GET /analytics`~~ → **DELETE** (consolidate into intelligence or reports)

**Remove broken button links**:
- Search across all templates for `href="/undefined"`, `href="null"`, `onclick="undefined()"`
- Replace with actual routes or disable button

---

## 9. DARK MODE CSS VARIABLE MAP

All CSS vars applied at `<html>` level (both `.dark` and light):

```css
:root {
  /* Dark mode (default) */
  --text-primary: #f5f5f5;
  --text-secondary: #a1a1a1;
  --bg-light: #1a1a1a;
  --bg-dark: #0f0f0f;
  --accent: #d4af37;
  --border: rgba(212,175,55,0.15);
}
html:not(.dark) {
  /* Light mode */
  --text-primary: #191c1e;
  --text-secondary: #434655;
  --bg-light: #ffffff;
  --bg-dark: #f8f9fb;
  --accent: #004ac6;
  --border: rgba(0,74,198,0.12);
}
```

**All component classes** must reference `var(--*)` not hardcoded colors.

---

## 10. TESTING CHECKLIST (Post-Build)

- [ ] All 40+ routes render without 404
- [ ] Dark mode toggle persists across refresh
- [ ] Light mode contrast passes WCAG AA
- [ ] Sidebar accordion expand/collapse works
- [ ] Mobile hamburger menu works
- [ ] File drag-drop uploads files
- [ ] Search filters work client-side
- [ ] Forms validate before submit
- [ ] Error toasts display + auto-dismiss
- [ ] No console errors or warnings
- [ ] Buttons link to correct routes (no dead links)
- [ ] Responsive layout at 320px, 768px, 1440px widths
- [ ] Images lazy-load
- [ ] Tables sort/paginate correctly
- [ ] No "circulars" references in UI

---

## 11. DELIVERABLES SUMMARY

| Agent | Scope | Output | LOC |
|-------|-------|--------|-----|
| **1** | Base, navigation, theme system | 6 Jinja2 + inline CSS | 1200 |
| **2** | Reusable component library | components.html + components.css | 800 |
| **3** | 30+ core pages | 30 Jinja2 templates | 5000 |
| **4** | JS interactivity, polish, error handling | 6 JS files + 1 CSS | 2000 |
| | **TOTAL** | | **9000** |

---

## 12. SEQUENCE & DEPENDENCIES

1. **Agent 1 starts immediately** (base.html, sidebar, navbar, theme script)
2. **Agent 2 starts after Agent 1** (needs base.html extends)
3. **Agent 3 starts after Agent 2** (needs component macros)
4. **Agent 4 starts after Agent 3** (needs HTML rendered to test JS)

**Parallel allowed**: Agent 1 & 2 can finalize while Agent 3 builds pages

---

## NOTES FOR AGENTS

- **Use Tailwind utilities** wherever possible; only add custom CSS if Tailwind can't express it
- **NO CSS frameworks beyond Tailwind** (no Bootstrap, no custom grid)
- **Jinja2 if-statements** for conditional rendering (dark mode, user role, etc.)
- **Comments required** on all non-obvious logic
- **No console.log()** left in production JS (use error.js for errors only)
- **Test dark mode toggle** early and often (Agent 4)
- **Validate routes** against FastAPI `router.py` BEFORE implementing page
- **Accessibility**: ARIA labels, semantic HTML, keyboard navigation for all interactive elements
