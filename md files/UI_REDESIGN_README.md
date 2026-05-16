# UI Redesign v3.0 - Multi-Agent Claude Code Job

**Status:** Ready to execute  
**Agents Required:** 4 (Architect → Component Builder → Page Developer → Integration & QA)  
**Estimated Duration:** 3–5 days  
**Stack:** Jinja2 + HTML + Vanilla JS + Tailwind CSS (NO REACT)

---

## 📋 Quick Start (3 Steps)

### Step 1: Connect Stitch MCP
Before starting any agent work:
1. Go to your Claude.ai settings
2. Enable **Stitch MCP** (Design extraction tool)
3. When Agent 2 (Component Builder) requests, authorize Stitch to access:
   ```
   https://api.anthropic.com/v1/design/h/qakgguKo21hsl5BnJMoAMg?open_file=it-app.js
   ```
4. Stitch will extract design tokens → Agent 2 documents in `DESIGN.md`

### Step 2: Open Claude Code Terminal
1. Open Claude Code (VS Code terminal mode in Claude.ai)
2. You will receive the single **PROMPT.txt** below
3. Copy the entire prompt into the terminal
4. The multi-agent team will self-organize and execute

### Step 3: Agent Workflow
```
PROMPT.txt (single, comprehensive prompt)
    ↓
Agent 1 (Architect) — 1 day
  Creates: base.html, CSS var system, theme.css, layout.css, dark/light toggle
    ↓
Agent 2 (Component Builder) — 1.5 days
  Extracts Figma design via Stitch MCP
  Creates: DESIGN.md, all Jinja2 macros (buttons, cards, forms, modals)
    ↓
Agent 3 (Page Developer) — 2 days
  Builds 10 core pages using Agents 1 & 2 outputs
  Wires all buttons to valid routes
    ↓
Agent 4 (Integration & QA) — 1 day
  Tests all pages (light/dark, mobile/desktop)
  Audits button wiring (0 broken links)
  Performance check (CSS <50KB, Lighthouse ≥80)
  Removes all circulars references
    ↓
Deliverable: Complete production-ready UI
```

---

## 📄 Files Included

### 1. **UI_REDESIGN_PROMPT.txt** ← **COPY THIS INTO CLAUDE CODE TERMINAL**
- Single, comprehensive prompt for multi-agent team
- Includes all 4 agent roles, deliverables, constraints, success metrics
- 12KB, self-contained
- Paste entire content into Claude Code terminal when starting job

### 2. **UI_REDESIGN_SPEC.md** ← **Agents Reference This Internally**
- Technical specification document (agents read, you don't need to)
- CSS variable system, component specs, routes, folder structure
- Figma design token extraction guide for Agent 2
- Button wiring map, error handling patterns, performance targets
- 45KB, detailed reference material

### 3. **UI_REDESIGN_README.md** ← **You Are Here**
- Quick-start guide
- Setup instructions
- Success checklist

---

## 🎨 Design Reference

**Figma Design File:**
```
https://api.anthropic.com/v1/design/h/qakgguKo21hsl5BnJMoAMg?open_file=it-app.js
```

Agent 2 (Component Builder) will use **Stitch MCP** to extract:
- Color palette (light & dark modes)
- Spacing scale (8px base)
- Typography (font families, sizes, weights)
- Component specs (buttons, cards, forms, modals)
- Glassmorphism details (blur amount, opacity)

All extracted into `DESIGN.md` for reference.

---

## ✅ Success Checklist (Final QA Criteria)

- [ ] All 10 pages render without 404 or CSS errors
- [ ] Every button has valid href or onclick handler (0 broken links)
- [ ] Dark/light mode toggle persists across page reload
- [ ] Mobile responsive (tested on 320px, 768px, 1024px breakpoints)
- [ ] Lighthouse score ≥80 on all pages
- [ ] CSS total <50KB (minified)
- [ ] JS total <20KB (gzipped)
- [ ] No circulars module visible in UI (backend only)
- [ ] Error modals display on 404/500 (no browser alerts)
- [ ] Accessibility: color contrast ≥4.5:1 (AA standard)
- [ ] Folder structure matches spec: static/css/{theme,layout,components,utilities}, templates/{macros,pages,partials}
- [ ] All components use CSS variables (no hardcoded colors)
- [ ] DESIGN.md created (from Figma extraction)

---

## 🚀 How to Execute

### Option A: Interactive (Recommended)
1. Open Claude Code in Claude.ai
2. Copy entire `UI_REDESIGN_PROMPT.txt` content
3. Paste into terminal
4. Agents will execute step-by-step with progress updates
5. When Agent 2 asks for Stitch authorization → approve in Claude settings
6. Watch agents hand off to each other (Agent 1 → 2 → 3 → 4)
7. Final QA results displayed

### Option B: Copy-Paste (If Terminal Not Available)
1. Copy `UI_REDESIGN_PROMPT.txt`
2. Paste into Claude chat as a new conversation
3. Say: "Execute this multi-agent UI redesign job"
4. Follow same steps as Option A

---

## 📊 Output Folder Structure

After completion, generated files will be in `app/ui/`:

```
app/ui/
├── static/
│   ├── css/
│   │   ├── theme.css           (CSS variables)
│   │   ├── layout.css          (Grid, flexbox, responsive)
│   │   ├── components.css      (Reusable classes)
│   │   └── utilities.css       (Tailwind-style helpers)
│   └── js/
│       ├── api.js              (Fetch wrapper)
│       ├── theme-toggle.js     (Dark/light mode + localStorage)
│       ├── sidebar.js          (Accordion nav)
│       └── modal.js            (Error modal handler)
├── templates/
│   ├── base.html               (Master template with {% block %}s)
│   ├── DESIGN.md               (Extracted from Figma)
│   ├── macros/
│   │   ├── buttons.html
│   │   ├── cards.html
│   │   ├── forms.html
│   │   ├── modals.html
│   │   └── alerts.html
│   ├── pages/
│   │   ├── auth/ (login, register)
│   │   ├── documents/ (index, upload, detail)
│   │   ├── analysis/ (index, ner, risk, ml, deviation)
│   │   ├── intelligence/ (index, insurers, advisory, settlement_power)
│   │   ├── reports/ (index, generate, compliance, news)
│   │   ├── clients/ (index, list, profile, expiry, renewals)
│   │   ├── system/ (index)
│   │   └── home.html (main dashboard)
│   └── partials/
│       ├── sidebar.html (accordion nav)
│       ├── header.html
│       └── footer.html
```

---

## 🔧 Key Technologies Used

- **Jinja2** — Server-side templating (FastAPI integration)
- **HTML5** — Semantic markup
- **CSS3** — Variables, Flexbox, Grid, Media queries, Transitions
- **Vanilla JavaScript** — No frameworks, <20KB total
- **Tailwind CSS** — Utility classes via CSS variables
- **Stitch MCP** — Figma design extraction (Agent 2)

**NO React, NO Vue, NO Angular, NO framework complexity.**

---

## ❓ FAQ

**Q: Can I start only Agent 2 and skip Agent 1?**  
A: No. Agent 1 (Architect) must run first because it creates the CSS variable system and base.html structure that Agents 2–4 depend on.

**Q: What if Stitch MCP is unavailable?**  
A: Agent 2 will manually reference the Figma link and extract design tokens. It will take longer (~2 hours) but is still feasible.

**Q: Can I modify pages while agents are working?**  
A: Not recommended. Wait for Agent 4 (QA) to finish, then make modifications. Any manual edits may be overwritten during hand-offs.

**Q: How do I know if an agent finished?**  
A: Agent 4 will run a test matrix (40 cells: 10 pages × 4 conditions) and provide a final report. "All tests passed" = job complete.

**Q: What if a button link doesn't exist in the backend?**  
A: Agent 4 will flag this in the button wiring audit. The corresponding route must be added to `app/ui/router.py` before the UI goes to production.

**Q: Dark/Light toggle not persisting?**  
A: Check browser localStorage settings. theme-toggle.js uses `localStorage.setItem('theme', ...)`. If localStorage is disabled, toggle won't persist across sessions.

---

## 📞 Support

If agents encounter errors:
1. **CSS Variable Errors** → Check theme.css for typos in `--color-*` names
2. **Jinja2 Template Errors** → Ensure macros are imported with `{% from "macros/..." import ... %}`
3. **Route 404s** → Verify route exists in `app/ui/router.py` (reference SPEC.md button wiring map)
4. **Stitch MCP Fails** → Authorize in Claude settings, retry Agent 2
5. **Performance Issues** → Check CSS file sizes, minify if needed, use `gzip` for JS

---

## 📈 Timeline

| Phase | Agent | Duration | Output |
|-------|-------|----------|--------|
| **Day 1** | Agent 1 (Architect) | 6 hrs | base.html, theme.css, dark/light toggle, sidebar blueprint |
| **Day 2-3** | Agent 2 (Component Builder) | 12 hrs | DESIGN.md, all macros (buttons, cards, forms, modals) |
| **Day 3-4** | Agent 3 (Page Developer) | 16 hrs | 10 working pages with all buttons wired |
| **Day 4-5** | Agent 4 (Integration & QA) | 8 hrs | Test matrix (40 cells), button wiring audit, performance report |
| **Total** | All | **3–5 days** | Production-ready UI |

---

## 🎯 Next Steps After Completion

1. **Merge to main branch** — Copy generated files from `app/ui/` to your production repo
2. **Backend Integration** — Verify all routes in SPEC.md exist in main.py
3. **Testing** — Run pytest on all routes (Agent 4 provides test plan)
4. **Deployment** — Build Docker image, deploy to staging/prod
5. **User Feedback** — Collect feedback on dark/light mode, button placement, page navigation

---

**Created:** 2026-04-26  
**Version:** v3.0  
**Status:** Ready to Execute

Copy `UI_REDESIGN_PROMPT.txt` and paste into Claude Code terminal to begin.
