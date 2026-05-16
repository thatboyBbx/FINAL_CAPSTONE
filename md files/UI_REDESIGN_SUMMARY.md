# UI REDESIGN JOB - COMPLETE DELIVERY PACKAGE
**Insurance Document Intelligence Platform (EXP_V3)**

---

## 📦 DELIVERABLES SUMMARY

You have received **3 files** ready for immediate execution:

### 1. **UI_REDESIGN_PROMPT.txt** (5.2 KB)
**Purpose:** Single, comprehensive prompt for multi-agent Claude Code team  
**Action:** Copy entire content → Paste into Claude Code terminal  
**Contains:**
- 4-agent team structure (Architect, Component Builder, Page Developer, Integration & QA)
- Detailed responsibilities for each agent
- Deliverables checklist
- 10 core design/implementation constraints
- Success metrics
- Hand-off sequence between agents

### 2. **UI_REDESIGN_SPEC.md** (45 KB)
**Purpose:** Technical specification reference (agents use this internally)  
**Action:** Agents will reference this during execution (you don't need to)  
**Contains:**
- Current state audit (143 templates, 6 broken areas)
- Figma design integration guide (Stitch MCP instructions)
- Complete CSS variable system (light/dark modes)
- Component specifications (buttons, cards, forms, modals)
- Full page structure & routes (10 core pages)
- Navigation architecture (6-section accordion)
- Folder organization guide
- Dark/light mode implementation
- Button wiring map (all routes cross-referenced)
- Error handling patterns
- Performance targets (CSS <50KB, JS <20KB, Lighthouse ≥80)

### 3. **UI_REDESIGN_README.md** (3.8 KB)
**Purpose:** Quick-start guide for you  
**Action:** Read before starting  
**Contains:**
- 3-step execution guide
- Stitch MCP setup instructions
- Agent workflow diagram
- Success checklist (16 items)
- FAQ (10 questions)
- Timeline (3–5 days)
- Post-completion steps

---

## 🎯 EXECUTION FLOW

```
┌─────────────────────────────────────────────────────┐
│ YOU: Copy UI_REDESIGN_PROMPT.txt content            │
│ YOU: Paste into Claude Code terminal                │
│ YOU: Authorize Stitch MCP when Agent 2 requests     │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ AGENT 1: ARCHITECT (6 hours)                        │
│ ✓ base.html (master template)                       │
│ ✓ theme.css (CSS variables: colors, spacing, typo) │
│ ✓ layout.css (grid, flexbox, responsive)           │
│ ✓ theme-toggle.js (dark/light mode + localStorage)│
│ ✓ Sidebar accordion blueprint                       │
│ ✓ Error modal system                                │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ AGENT 2: COMPONENT BUILDER (12 hours)               │
│ ✓ Extract Figma design via Stitch MCP              │
│ ✓ DESIGN.md (design tokens documented)             │
│ ✓ buttons.html macro (primary, glass, gold, danger)│
│ ✓ cards.html macro (info, metric, glass)           │
│ ✓ forms.html macro (inputs, selects, validation)   │
│ ✓ modals.html macro (error, confirm, info)         │
│ ✓ All components support dark/light mode           │
│ ✓ All components use CSS variables only            │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ AGENT 3: PAGE DEVELOPER (16 hours)                  │
│ ✓ login.html, register.html (centered layout)      │
│ ✓ home.html (main dashboard + sidebar)             │
│ ✓ documents/index.html, upload.html, detail.html   │
│ ✓ analysis/index.html + 4 detail pages             │
│ ✓ intelligence/index.html + sub-pages              │
│ ✓ reports/index.html + sub-pages                   │
│ ✓ clients/index.html + sub-pages                   │
│ ✓ system/index.html (settings)                     │
│ ✓ All buttons wired to valid routes                │
│ ✓ Mobile responsive (320px, 768px, 1024px)        │
│ ✓ Dark/light mode compatible                       │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ AGENT 4: INTEGRATION & QA (8 hours)                 │
│ ✓ Test matrix: 10 pages × 4 conditions = 40 cells │
│ ✓ Button wiring audit (0 broken links)             │
│ ✓ Performance audit (Lighthouse ≥80)               │
│ ✓ Dark/light toggle verification (100+ cycles)     │
│ ✓ Accessibility audit (WCAG AA)                    │
│ ✓ Circulars removal verification                   │
│ ✓ Error modal demo on 404/500                      │
│ ✓ Final report + all tests passing                 │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ DELIVERABLE: Production-Ready UI                    │
│ Location: app/ui/static/ + app/ui/templates/        │
│ Ready for: Backend integration + Testing + Deploy   │
└─────────────────────────────────────────────────────┘
```

---

## 🔑 KEY FEATURES IMPLEMENTED

### 1. **Dark/Light Mode**
- Toggle button in header (moon/sun icon)
- localStorage persistence (survives page reload)
- CSS variable-driven (no separate stylesheets)
- Smooth transitions between modes
- Applied to 100+ UI elements

### 2. **Modular CSS Architecture**
```
theme.css        → All colors, spacing, typography (CSS variables)
layout.css       → Grid, flexbox, responsive breakpoints
components.css   → Reusable classes (.btn, .card, .form-input, etc.)
utilities.css    → Tailwind-style helpers (.hidden, .flex, .gap-*, etc.)
───────────────────────────────────────────────────────
Total: <50KB (minified), loads in <100ms
```

### 3. **Glassmorphism Design**
- Buttons: `backdrop-filter: blur(16px)`, rgba backgrounds, 1px borders
- Variants: `.btn-glass-gold` (premium), `.btn-glass-danger` (alerts)
- Cards: Frosted glass effect on glassmorphic tiles
- Consistent across light/dark modes

### 4. **6-Section Accordion Sidebar**
```
📄 Documents
   └─ List, Upload, Vault

🔍 Analysis
   └─ NER, Risk, ML, Deviation, Compliance

💡 Intelligence
   └─ Insurers, Settlement Power, Advisory

📊 Reports
   └─ List, Generate, Compliance, News

👥 Clients
   └─ List, Expiry Tracker, Renewals

⚙️ System
   └─ Settings, Preferences, Logout
```

### 5. **Error Handling**
- Styled modal for all errors (no browser alerts)
- User-friendly messages (no stack traces)
- Dismiss button, accessible, keyboard-closeable
- Triggered on 404, 500, API failures

### 6. **Responsive Design**
- Mobile: 320px (iPhone SE)
- Tablet: 768px (iPad)
- Desktop: 1024px+ (laptops)
- All pages tested at all breakpoints

### 7. **Accessibility (WCAG AA)**
- Color contrast ≥4.5:1 on all text
- Keyboard navigation on all interactive elements
- aria-labels on icons
- Focus indicators visible
- Form labels associated with inputs

### 8. **Button Wiring**
- Every button has valid href or onclick
- Cross-referenced against main.py routes
- No placeholder links (#, /todo, etc.)
- All internal links relative (no hardcoded domains)

### 9. **Circulars Module Removal**
- No `/circulars-ui` route
- No `circulars_ui.html` template
- No circulars nav item in sidebar
- Backend module untouched (training data only)

### 10. **Performance**
- CSS: <50KB (minified)
- JS: <20KB (gzipped)
- Lighthouse score: ≥80 on all pages
- Page load: <3s on 4G mobile

---

## 📋 CHECKLIST FOR YOU

### Before Starting:
- [ ] Read UI_REDESIGN_README.md (3 min)
- [ ] Understand 4-agent flow (diagram above)
- [ ] Enable Stitch MCP in Claude settings
- [ ] Have Figma link ready: https://api.anthropic.com/v1/design/h/qakgguKo21hsl5BnJMoAMg?open_file=it-app.js

### During Execution:
- [ ] Copy UI_REDESIGN_PROMPT.txt → Paste into Claude Code terminal
- [ ] Let Agent 1 run (6 hours, monitor progress)
- [ ] When Agent 2 asks for Stitch authorization → Approve
- [ ] Let Agents 2, 3, 4 run in sequence (monitor hand-offs)
- [ ] Take notes on any manual fixes needed

### After Completion:
- [ ] Review Agent 4's test report (40-cell matrix)
- [ ] Verify all 10 pages render without errors
- [ ] Test dark/light toggle (localStorage persists?)
- [ ] Test on mobile (responsive? buttons clickable?)
- [ ] Check button links (none broken?)
- [ ] Confirm circulars module not visible in UI
- [ ] Copy generated files to your project repo

---

## 🎨 DESIGN REFERENCE

**Figma File:**
```
https://api.anthropic.com/v1/design/h/qakgguKo21hsl5BnJMoAMg?open_file=it-app.js
```

Agent 2 will extract:
- Colors (light & dark palette)
- Spacing scale (8px baseline)
- Typography (fonts, sizes, weights)
- Component patterns (buttons, cards, etc.)
- Glassmorphism specs (blur 16px, rgba, borders)

All saved to `DESIGN.md` for future reference.

---

## ⚡ QUICK REFERENCE

| Item | Details |
|------|---------|
| **Total Files** | 3 (PROMPT.txt, SPEC.md, README.md) |
| **Agents** | 4 (Architect, Component Builder, Page Dev, QA) |
| **Pages** | 10 (login, home, docs, analysis, intel, reports, clients, system) |
| **Time** | 3–5 days |
| **CSS Size** | <50KB (minified) |
| **JS Size** | <20KB (gzipped) |
| **Dark Mode** | Yes (localStorage) |
| **Responsive** | Yes (320px, 768px, 1024px) |
| **Accessibility** | WCAG AA |
| **Buttons** | 100% wired (0 broken links) |
| **Circulars** | Completely removed from UI |
| **Tech Stack** | Jinja2 + HTML + Vanilla JS + Tailwind CSS |

---

## 🚀 EXECUTION COMMAND

```bash
# Step 1: Open Claude Code terminal
# Step 2: Copy entire UI_REDESIGN_PROMPT.txt
# Step 3: Paste into terminal
# Step 4: Watch agents execute

# Example paste:
================================================================================
INSURANCE DOCUMENT INTELLIGENCE PLATFORM - UI REDESIGN & RESTRUCTURING
Claude Code Multi-Agent Team Orchestration
[... rest of PROMPT.txt ...]
```

---

## 📞 SUPPORT DURING EXECUTION

| Issue | Solution |
|-------|----------|
| Agent 1 takes >8 hours | Check for CSS syntax errors; ask agent to refactor |
| Agent 2 Stitch fails | Re-authorize in Claude settings, check Figma link |
| Agent 3 buttons broken | Cross-reference routes in SPEC.md button wiring map |
| Agent 4 Lighthouse <80 | Check JS file size (minify if needed) + CSS optimization |
| localStorage not persisting | Check browser settings (allow localStorage) + Dev tools |
| Mobile layout broken | Test breakpoints at 320px, 768px in browser Dev tools |

---

## 📈 SUCCESS METRICS (Final QA)

✅ All metrics from Agent 4's test report must show PASS:

```
Test Matrix Results: 40/40 PASS
├─ Pages Render: 10/10 ✓
├─ Button Wiring: 0 broken links ✓
├─ Dark/Light Toggle: Works 100+ cycles ✓
├─ Responsive: 320px, 768px, 1024px ✓
├─ Lighthouse: ≥80 on all pages ✓
├─ Accessibility: WCAG AA ✓
├─ Performance: CSS <50KB, JS <20KB ✓
├─ Circulars Removed: ✓
└─ Error Modals: Display on 4xx/5xx ✓
```

---

## 📄 FILES LOCATION

All files are in `/mnt/user-data/outputs/`:

```
/mnt/user-data/outputs/
├── UI_REDESIGN_PROMPT.txt       ← COPY & PASTE THIS
├── UI_REDESIGN_SPEC.md          ← Agents reference this
├── UI_REDESIGN_README.md        ← Read this first
└── UI_REDESIGN_SUMMARY.md       ← You are here
```

---

## ✅ READY TO BEGIN?

1. **Read:** UI_REDESIGN_README.md (5 min)
2. **Copy:** UI_REDESIGN_PROMPT.txt (entire content)
3. **Open:** Claude Code terminal
4. **Paste:** The prompt
5. **Approve:** Stitch MCP authorization when Agent 2 asks
6. **Wait:** 3–5 days for agents to complete
7. **Review:** Agent 4's final test report
8. **Deploy:** Copy generated UI files to your project repo

---

**Status:** ✅ Ready to Execute  
**Created:** 2026-04-26  
**Version:** 3.0  

**Next Action:** Copy UI_REDESIGN_PROMPT.txt → Paste into Claude Code → Start multi-agent job
