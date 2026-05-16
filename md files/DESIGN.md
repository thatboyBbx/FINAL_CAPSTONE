# InsureIntel Zimbabwe — Design System Reference

> Concise reference for developers building UI on the InsureIntel platform (FastAPI + Jinja2).

---

## 1. Color System (CSS Variables)

All colors are defined as CSS custom properties on `:root` (light mode) and overridden by the `html.dark` class (dark mode).

| Variable   | Role                          | Dark Mode Value           | Light Mode Value         |
|------------|-------------------------------|---------------------------|--------------------------|
| `--cp`     | Primary / Gold accent         | `#d4af37`                 | `#004ac6`                |
| `--cbg`    | Page background               | `#0f0f0f`                 | `#f8f9fb`                |
| `--csf`    | Surface (cards, panels)       | `#1a1a1a`                 | `#ffffff`                |
| `--csfc`   | Surface container (inputs)    | `#242424`                 | `#edeef0`                |
| `--col`    | Outline / border              | `#4a4a4a`                 | `#737686`                |
| `--cos`    | On-surface text (primary)     | `#f5f5f5`                 | `#191c1e`                |
| `--cosv`   | On-surface-variant (muted)    | `#a1a1a1`                 | `#434655`                |
| `--cerr`   | Error                         | `#ff4d4d`                 | `#ba1a1a`                |
| `--glass-bg`  | Glass card fill            | `rgba(26,26,26,0.6)`      | `rgba(255,255,255,0.85)` |
| `--glass-bdr` | Glass card border          | `rgba(212,175,55,0.10)`   | `rgba(0,74,198,0.12)`    |
| `--glow`   | Shadow / ambient glow         | `rgba(212,175,55,0.10)`   | `rgba(0,74,198,0.08)`    |

### CSS Variable Declaration Pattern

```css
:root {
  --cp:#d4af37; --cbg:#0f0f0f; --csf:#1a1a1a; --csfc:#242424;
  --col:#4a4a4a; --cos:#f5f5f5; --cosv:#a1a1a1; --cerr:#ff4d4d;
  --glass-bg:rgba(26,26,26,0.6); --glass-bdr:rgba(212,175,55,0.10);
  --glow:rgba(212,175,55,0.10);
}
html:not(.dark) {
  --cp:#004ac6; --cbg:#f8f9fb; --csf:#ffffff; --csfc:#edeef0;
  --col:#737686; --cos:#191c1e; --cosv:#434655; --cerr:#ba1a1a;
  --glass-bg:rgba(255,255,255,0.85); --glass-bdr:rgba(0,74,198,0.12);
  --glow:rgba(0,74,198,0.08);
}
```

> **Rule:** Always use `var(--cp)` etc. — never hardcode hex values in component styles.

---

## 2. Typography

| Font       | Weight(s)         | Use Case                                         |
|------------|-------------------|--------------------------------------------------|
| **Manrope**| 600, 700, 800     | Headlines, section titles, card headings (`h1`–`h3`) |
| **Inter**  | 400, 500, 600, 700| Body text, labels, inputs, paragraphs, UI copy   |

### Google Fonts Import

```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap" rel="stylesheet">
```

### Usage Classes

```css
.font-headline { font-family: 'Manrope', sans-serif; }
body           { font-family: 'Inter', sans-serif; }
```

### Type Scale (approximate)

| Token       | Size        | Use                          |
|-------------|-------------|------------------------------|
| Display     | 2rem+       | Hero/landing headings        |
| H1          | 1.75rem     | Page titles                  |
| H2          | 1.25–1.5rem | Section headings             |
| H3          | 1rem–1.1rem | Card/widget headings         |
| Body        | 0.9rem      | Default content              |
| Small       | 0.875rem    | Secondary text, captions     |
| Caption     | 0.75rem     | Footnotes, timestamps        |
| Label (UI)  | 0.7rem      | Form labels (UPPERCASE)      |

---

## 3. Spacing Scale

Base unit: **8px (0.5rem)**

| Token   | Value   | Pixels |
|---------|---------|--------|
| `xs`    | 0.5rem  | 8px    |
| `sm`    | 1rem    | 16px   |
| `md`    | 1.5rem  | 24px   |
| `lg`    | 2rem    | 32px   |
| `xl`    | 3rem    | 48px   |

All padding, margin, and gap values should be multiples of `0.5rem`.

---

## 4. Component Classes

### 4.1 Glassmorphism Card

```css
.glass-card {
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--glass-bdr);
  border-radius: 16px;
  box-shadow: 0 8px 40px rgba(0,0,0,0.25);
}
```

**Usage:** Wrap any card content in `<div class="glass-card">`. Used for login/register cards, analytics panels, modal dialogs.

### 4.2 Buttons

| Class              | Description                                  |
|--------------------|----------------------------------------------|
| `.btn-glass`       | Ghost/glass button — subtle, for secondary actions |
| `.btn-glass-gold`  | Gold-filled button — primary CTA             |
| `.btn-glass-danger`| Red-tinted button — destructive actions      |

```css
/* Base pattern for all glass buttons */
.btn-glass {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  padding: 0.625rem 1.25rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid var(--col);
  background: transparent;
  color: var(--cos);
  transition: background 0.15s, border-color 0.15s;
  font-family: inherit;
}
.btn-glass:hover { background: var(--csfc); border-color: var(--cp); }

.btn-glass-gold {
  background: var(--cp);
  color: #0f0f0f;
  border: none;
}
.btn-glass-gold:hover { opacity: 0.88; }

.btn-glass-danger {
  background: transparent;
  color: var(--cerr);
  border: 1px solid var(--cerr);
}
.btn-glass-danger:hover { background: rgba(255,77,77,0.08); }
```

### 4.3 Badges

```html
<!-- Status badges -->
<span class="badge badge-active">Active</span>
<span class="badge badge-pending">Pending</span>
<span class="badge badge-error">Expired</span>
```

```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.badge-active  { background: rgba(74,222,128,0.12); color: #4ade80; }
.badge-pending { background: rgba(212,175,55,0.12); color: var(--cp); }
.badge-error   { background: rgba(255,77,77,0.12);  color: var(--cerr); }
```

### 4.4 Alerts

```html
<div class="alert-error">
  <span class="material-symbols-outlined">error</span>
  Error message text here.
</div>
<div class="alert-success">
  <span class="material-symbols-outlined">check_circle</span>
  Success message text here.
</div>
<div class="alert-info">
  <span class="material-symbols-outlined">info</span>
  Informational message text here.
</div>
```

```css
.alert-error {
  display: flex; align-items: flex-start; gap: 0.5rem;
  padding: 0.75rem 1rem; border-radius: 0.5rem;
  border-left: 3px solid var(--cerr);
  background: rgba(255,77,77,0.08);
  color: var(--cerr); font-size: 0.875rem;
}
.alert-success {
  display: flex; align-items: flex-start; gap: 0.5rem;
  padding: 0.75rem 1rem; border-radius: 0.5rem;
  border-left: 3px solid #4ade80;
  background: rgba(74,222,128,0.08);
  color: #4ade80; font-size: 0.875rem;
}
.alert-info {
  display: flex; align-items: flex-start; gap: 0.5rem;
  padding: 0.75rem 1rem; border-radius: 0.5rem;
  border-left: 3px solid var(--cp);
  background: rgba(212,175,55,0.06);
  color: var(--cosv); font-size: 0.875rem;
}
```

### 4.5 Form Elements

```css
/* Label */
.form-label {
  display: block;
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--cosv);
  margin-bottom: 0.375rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

/* Input / Textarea / Select */
.form-input {
  width: 100%;
  padding: 0.625rem 0.875rem;
  border-radius: 0.5rem;
  font-size: 0.9rem;
  color: var(--cos);
  background: var(--csfc);
  border: 1px solid var(--col);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  font-family: inherit;
}
.form-input:focus {
  border-color: var(--cp);
  box-shadow: 0 0 0 3px rgba(212,175,55,0.12);
}
```

**Pattern:** Always pair `<label class="form-label" for="field_id">` with `<input id="field_id">` for accessibility.

### 4.6 Tables

```html
<div class="table-wrap glass-card" style="overflow:auto">
  <table class="data-table">
    <thead>
      <tr>
        <th>Column</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Value</td>
      </tr>
    </tbody>
  </table>
</div>
```

```css
.data-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
.data-table th {
  padding: 0.75rem 1rem;
  text-align: left;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--cosv);
  border-bottom: 1px solid var(--col);
}
.data-table td {
  padding: 0.75rem 1rem;
  color: var(--cos);
  border-bottom: 1px solid var(--csfc);
}
.data-table tbody tr:hover { background: var(--csfc); }
.data-table tbody tr:last-child td { border-bottom: none; }
```

---

## 5. Glassmorphism Patterns

### Standard Glass Card
```css
background: var(--glass-bg);
backdrop-filter: blur(20px);
-webkit-backdrop-filter: blur(20px);
border: 1px solid var(--glass-bdr);
border-radius: 16px;
box-shadow: 0 8px 40px rgba(0,0,0,0.25);
```

### Subtle Ambient Glow (primary color)
```css
box-shadow: 0 0 24px var(--glow);
```

### Background Decoration Blobs
```css
/* Top-right accent */
.bg-decor {
  position: fixed;
  top: -20%; right: -10%;
  width: 60%; height: 60%;
  background: rgba(212,175,55,0.05);
  border-radius: 50%;
  filter: blur(120px);
  pointer-events: none;
  z-index: 0;
}
```

---

## 6. Icons

**Library:** Material Symbols Outlined (variable font — supports weight, fill, grade, optical size axes)

```html
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
```

**Usage:**
```html
<span class="material-symbols-outlined">icon_name</span>
```

**Default axis settings:**
```css
.material-symbols-outlined {
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  vertical-align: middle;
}
```

**Filled variant:**
```css
font-variation-settings: 'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24;
```

Common icons used in the platform:

| Icon Name        | Used For                    |
|------------------|-----------------------------|
| `security`       | App logo, auth pages        |
| `shield_with_heart` | Register page logo       |
| `badge`          | Staff ID fields             |
| `lock`           | Password fields             |
| `login`          | Sign in button              |
| `person`         | User profile                |
| `mail`           | Email fields                |
| `description`    | Documents section           |
| `analytics`      | Analysis section            |
| `verified_user`  | Compliance / IPEC           |
| `error`          | Error alerts                |
| `check_circle`   | Success alerts              |
| `info`           | Info alerts                 |
| `chevron_right`  | Breadcrumb separator        |
| `expand_more`    | Dropdown chevron            |
| `light_mode`     | Theme toggle (dark→light)   |
| `dark_mode`      | Theme toggle (light→dark)   |

---

## 7. Dark / Light Mode

### Mechanism
- Default class: `html.dark` — the `<html>` element carries the `dark` class.
- Toggle: add/remove `dark` class on `<html id="html-root">`.
- Storage key: `insureIntelTheme` in `localStorage` (`"dark"` or `"light"`).

### FOUC Prevention Script (must be first script in `<head>`)

```html
<script>
  (function(){
    var t = localStorage.getItem('insureIntelTheme') || 'dark';
    if (t !== 'dark') document.documentElement.classList.remove('dark');
  })();
</script>
```

Place this **inline** as the very first `<script>` tag in `<head>` — before any stylesheet — so there is no flash of unstyled/wrong-theme content.

### Theme Toggle Button Pattern

```html
<button onclick="(function(){
    var d = document.documentElement.classList.toggle('dark');
    localStorage.setItem('insureIntelTheme', d ? 'dark' : 'light');
  })()"
  title="Toggle theme" aria-label="Toggle dark/light mode">
  <!-- Shows in dark mode (click to go light) -->
  <span class="material-symbols-outlined icon-dark-mode">dark_mode</span>
  <!-- Shows in light mode (click to go dark) -->
  <span class="material-symbols-outlined icon-light-mode">light_mode</span>
</button>
```

```css
/* Icon visibility per mode */
html.dark .icon-light-mode { display: none; }
html:not(.dark) .icon-dark-mode { display: none; }
```

---

## 8. Navigation Accordion

The sidebar (`app/ui/templates/partials/sidebar.html`) contains a 6-section accordion nav.

| # | Section Label  | Icon                  | Sub-items (example)                         |
|---|----------------|-----------------------|---------------------------------------------|
| 1 | Documents      | `description`         | Upload, Browse, Classify                    |
| 2 | Analysis       | `analytics`           | Clause Detection, Policy Compare, Risk Score|
| 3 | Intelligence   | `psychology`          | AI Insights, Trend Analysis, Anomaly Detect |
| 4 | Reports        | `bar_chart`           | Generate, Scheduled, Archive                |
| 5 | Clients        | `groups`              | Directory, Portfolios, Add Client           |
| 6 | System         | `settings`            | Users, Audit Log, Configuration             |

### Accordion Behavior
- Click section header → toggle `open` class.
- Sub-items slide in with CSS transition (`max-height: 0` → `max-height: 400px`).
- Active section highlighted with `var(--cp)` accent on left border.
- Stored expanded state optional (sessionStorage).

---

## 9. Page Layouts

### Authenticated Pages (with sidebar)
Extend `base.html` which provides:
- Sidebar with accordion nav
- Main content area: `{% block content %}{% endblock %}`
- User info, theme toggle in sidebar footer

### Auth Pages (login, register)
**Standalone** — do NOT extend `base.html`. These are full `<!DOCTYPE html>` pages with:
- Centered glassmorphic card layout
- No sidebar
- Inline FOUC prevention script

---

## 10. Partials

| File                              | Purpose                                    |
|-----------------------------------|--------------------------------------------|
| `partials/sidebar.html`           | Main nav sidebar (included by base.html)   |
| `partials/header.html`            | Optional page header (breadcrumbs, title)  |
| `partials/footer.html`            | Optional page footer (copyright notice)    |
| `partials/master_chatbot.html`    | AI assistant chatbot widget                |
| `partials/csp_report_card.html`   | CSP compliance report card widget          |

Partials are included with Jinja2 `{% include 'partials/header.html' %}`.

---

## 11. Quick Reference Checklist

When building a new page, verify:

- [ ] Page uses `var(--cp)`, `var(--cos)` etc. — no hardcoded colors
- [ ] Fonts loaded: Inter + Manrope from Google Fonts
- [ ] Icons loaded: Material Symbols Outlined
- [ ] `html.dark` class handling is correct (FOUC script in head)
- [ ] All form inputs have associated `<label for="id">` elements
- [ ] Buttons use `.btn-glass`, `.btn-glass-gold`, or `.btn-glass-danger`
- [ ] Cards use `.glass-card`
- [ ] Spacing is multiples of 0.5rem
- [ ] Auth pages are standalone (not extending base.html)
- [ ] Authenticated pages extend base.html
