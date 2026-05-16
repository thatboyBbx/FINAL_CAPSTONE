# JOB D SPECIFICATION — UI Navigation & Broken Button Fixes
**Consumed by:** JOB_D_PROMPT.txt agent team  
**Touches:** api.js · sidebar.js · ~30 Jinja2 template files

---

## BACKGROUND — WHY THIS JOB EXISTS

The platform UI has three categories of broken interaction:

1. **Dead links** — `href="#"` everywhere. Clicking does nothing. No feedback to the user.
2. **Browser alerts** — `window.alert()` used for errors. Ugly, blocks the page, doesn't match the glassmorphism design system.
3. **Forms pointing nowhere** — Some forms have incorrect or missing `action` attributes, so submitting them silently fails or 404s.

The fix is systematic: every button must either go somewhere real, trigger a real API call, or show an honest "coming soon" modal using the platform's own styled notification system.

---

## ROUTE REFERENCE MAP

Use this when fixing href and form action attributes:

```
UI Page Routes (all require login cookie):
  GET /home                          → Dashboard
  GET /documents-ui                  → Document list
  GET /upload-ui                     → Upload page
  GET /document-detail/{id}          → Document detail
  GET /document-comparison           → Document comparison
  GET /document-qa                   → Document Q&A
  GET /analytics                     → Analysis hub
  GET /compliance-center             → Compliance center
  GET /compliance-detail/{id}        → Compliance detail
  GET /clause-deviations             → Clause deviations
  GET /financial-position            → Insurer financial position
  GET /advisory                      → Advisory page
  GET /insurer-intelligence          → Insurer intelligence list
  GET /batch-portfolio               → Batch portfolio analysis
  GET /policy-tracker                → Policy expiry tracker
  GET /report                        → Reports center
  GET /audit-trail                   → Audit trail
  GET /feedback-panel                → Feedback panel
  GET /knowledge-base                → Knowledge base
  GET /settings                      → Settings
  GET /scraper-status                → Scraper status
  GET /alerts-ui                     → Alerts
  GET /analytics/settlement-power/   → CSP Settlement Power
  GET /clients/                      → Clients list
  GET /clients/{id}                  → Client profile
  GET /multilingual-analysis         → Multilingual analysis

API Routes (all require Authorization header or cookie):
  POST /documents/upload             → Upload a document
  GET  /documents/                   → List documents
  GET  /documents/{id}               → Get document
  POST /documents/{id}/analyse       → Trigger analysis
  GET  /documents/{id}/download      → Download document file
  POST /api/comparison/compare       → Compare two documents
  POST /api/chatbot/message          → Chatbot message
  POST /api/qa/ask                   → Document Q&A
  GET  /api/compliance/check/{id}    → Run compliance check
  GET  /csp/insurers/{id}/score      → Get CSP score
  GET  /insurers/                    → List insurers
  GET  /insurers/{id}                → Get insurer
  POST /api/reports/generate         → Generate report
  GET  /api/reports/{id}/pdf         → Download report PDF
  GET  /api/tracker/policies         → List tracked policies
  GET  /api/audit/logs               → Get audit logs
  GET  /api/feedback/                → List feedback
  POST /api/feedback/submit          → Submit feedback
  GET  /api/deviation/scores/{id}    → Get deviation scores
  POST /api/batch/start              → Start batch job
  GET  /api/batch/status/{id}        → Get batch status
```

---

## TASK 1 — Rewrite `app/ui/static/js/api.js`

Read the current file first, then replace it with a new version that:

1. Keeps all existing working functions
2. Adds the notification helpers at the TOP of the file
3. Replaces all `fetch(` calls with `apiFetch(` where the route needs auth
4. Removes all `window.alert(` and `alert(` calls

**Add these functions at the very top of api.js:**

```javascript
/**
 * api.js — InsureIntel Zimbabwe
 * Centralised API helpers. All authenticated calls use apiFetch().
 * All notifications use showErrorModal() or showSuccessModal().
 * Never use window.alert() or alert() anywhere in this codebase.
 */

/**
 * Show a styled error notification banner.
 * @param {string} message
 * @param {number} [durationMs=5000]
 */
function showErrorModal(message, durationMs = 5000) {
  _showBanner(message, 'insure-intel-error-banner', 'var(--cerr, #ff4d4d)', durationMs);
}

/**
 * Show a styled success notification banner.
 * @param {string} message
 * @param {number} [durationMs=3000]
 */
function showSuccessModal(message, durationMs = 3000) {
  _showBanner(message, 'insure-intel-success-banner', 'var(--cp, #d4af37)', durationMs);
}

/**
 * Internal banner renderer — do not call directly.
 */
function _showBanner(message, id, color, durationMs) {
  const existing = document.getElementById(id);
  if (existing) existing.remove();

  const banner = document.createElement('div');
  banner.id = id;
  Object.assign(banner.style, {
    position: 'fixed',
    top: '16px',
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: '9999',
    padding: '12px 20px',
    borderRadius: '8px',
    border: `1px solid ${color}`,
    background: color.replace(')', ', 0.12)').replace('var(', 'color-mix(in srgb, ') || 'rgba(0,0,0,0.12)',
    color: color,
    fontSize: '14px',
    fontFamily: 'Inter, sans-serif',
    maxWidth: '480px',
    width: 'max-content',
    textAlign: 'center',
    backdropFilter: 'blur(8px)',
    boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
    backgroundColor: `rgba(0,0,0,0.8)`,
    lineHeight: '1.4',
  });
  // Simpler background that works reliably with CSS variables
  banner.style.setProperty('border-color', color);
  banner.style.setProperty('color', color);
  banner.style.backgroundColor = 'rgba(15,15,15,0.92)';
  banner.textContent = message;

  document.body.appendChild(banner);
  setTimeout(() => { if (banner.parentNode) banner.remove(); }, durationMs);
}

/**
 * Authenticated fetch wrapper.
 * Sends the session cookie automatically (credentials: 'include').
 * Redirects to /login on 401. Throws on other errors.
 *
 * @param {string} url
 * @param {RequestInit} [options]
 * @returns {Promise<any>} Parsed JSON
 */
async function apiFetch(url, options = {}) {
  const defaultHeaders = {};
  // Only set Content-Type for JSON bodies (not FormData)
  if (options.body && !(options.body instanceof FormData)) {
    defaultHeaders['Content-Type'] = 'application/json';
  }

  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: { ...defaultHeaders, ...(options.headers || {}) },
  });

  if (response.status === 401) {
    window.location.href = '/login';
    throw new Error('Session expired. Redirecting to login.');
  }

  if (!response.ok) {
    let detail = `Server error (${response.status})`;
    try {
      const errData = await response.json();
      detail = errData.detail || errData.error || detail;
    } catch (_) { /* ignore JSON parse error on non-JSON error responses */ }
    throw new Error(detail);
  }

  // Handle empty responses (204 No Content)
  const contentType = response.headers.get('content-type') || '';
  if (response.status === 204 || !contentType.includes('application/json')) {
    return null;
  }

  return response.json();
}
```

**Then scan the rest of api.js for:**
- Every `fetch(` → change to `apiFetch(` (ensure the call signature still works)
- Every `window.alert(` → change to `showErrorModal(`
- Every `alert(` that is not `showErrorModal` → change to `showErrorModal(`

---

## TASK 2 — Fix Document & Analysis Templates

Fix every file listed. For each file: read it fully, then fix all broken interactions.

### `app/ui/templates/documents/upload.html`
- Upload form action: `action="/documents/upload"` `method="POST"` `enctype="multipart/form-data"`
- Cancel button: `href="/documents-ui"`
- Progress bar: if it has JS, ensure it uses `apiFetch()` not raw `fetch()`
- Any `href="#"` without purpose: add `onclick="showErrorModal('...')"`

### `app/ui/templates/documents/index.html`
- Every document row "View" link: `href="/document-detail/{{ doc.id }}"`
- Every "Analyse" button: `href="/document-detail/{{ doc.id }}"` or POST to `/documents/{{ doc.id }}/analyse`
- "Upload New" button: `href="/upload-ui"`
- Search/filter form: `method="GET"` `action="/documents-ui"`
- Pagination: `href="?page={{ n }}"`

### `app/ui/templates/document_detail.html`
- "Run Analysis" button: POST to `/documents/{{ document.id }}/analyse` via `apiFetch()`
- "Download" button: `href="/documents/{{ document.id }}/download"`
- "Compare" button: `href="/document-comparison?doc_id={{ document.id }}"`
- "Q&A" button: `href="/document-qa?doc_id={{ document.id }}"`
- "Back" button: `href="/documents-ui"`
- Remove any `onclick="undefined"` attributes

### `app/ui/templates/compliance_center.html`
- "Run Check" button: calls `apiFetch('/api/compliance/check/' + docId, {method:'GET'})` then shows result
- "Export" button: `href="/api/reports/compliance/{{ document_id }}"` or `onclick="showErrorModal('Export coming soon.')"`
- Any `href="#"`: fix as above

### `app/ui/templates/compliance_detail.html`
- "Back to Compliance Center" button: `href="/compliance-center"`
- "Export PDF" button: real download or `showErrorModal('Export coming soon.')`

### `app/ui/templates/clause_deviations.html`
- "Analyse" button: POST to `/api/deviation/scores/{{ document_id }}`
- "Back" button: `href="/analytics"`

### `app/ui/templates/document_comparison.html`
- "Compare" button: POST to `/api/comparison/compare` with `{ doc1_id, doc2_id }` via `apiFetch()`
- "Back" button: `href="/documents-ui"`

### `app/ui/templates/document_qa.html`
- Q&A form: POST to `/api/qa/ask` via `apiFetch()` then renders response in the page
- "Back" button: `href="/documents-ui"`

### `app/ui/templates/analysis/index.html` (Analysis hub)
- Each analysis category card/tile: must link to its real sub-page
  - NER → `/analytics`
  - Risk → `/analytics`
  - Deviation → `/clause-deviations`
  - Compliance → `/compliance-center`
  - ML → `/analytics` (ML predictions section)

### `app/ui/templates/feedback_panel.html`
- Submit feedback button: POST to `/api/feedback/submit` via `apiFetch()`
- Any `href="#"`: fix

---

## TASK 3 — Fix Intelligence & Reports Templates

### `app/ui/templates/intelligence/insurers/index.html`
- Each insurer row: `href="/intelligence/insurers/{{ insurer.id }}"`
- "Add Insurer" button: `href="#" onclick="showErrorModal('Manual insurer entry coming soon.')"` (feature not yet built)
- Pagination: `href="?page={{ n }}"`
- Search form: `method="GET"` `action="/insurer-intelligence"`

### `app/ui/templates/intelligence/insurers/profile.html`
- "View CSP Score" button: `href="/analytics/settlement-power/?insurer_id={{ insurer.id }}"`
- "Back" button: `href="/insurer-intelligence"`
- Export button: real href or `showErrorModal('Export coming soon.')`

### `app/ui/templates/analytics/settlement_power.html`
- "Calculate" / "Run Assessment" button: POST to `/csp/insurers/{{ insurer_id }}/score` via `apiFetch()`
- "Back" button: `href="/home"`
- Insurer selector: if it's a `<select>`, add `onchange` to update the displayed insurer

### `app/ui/templates/intelligence/advisory.html`
- Any action buttons: real API calls or `showErrorModal('...')`
- "Back" button: `href="/home"`

### `app/ui/templates/batch_portfolio.html`
- "Start Batch" button: POST to `/api/batch/start` via `apiFetch()`
- "Check Status" button: GET `/api/batch/status/{{ batch_id }}` via `apiFetch()`
- "Back" button: `href="/home"`

### `app/ui/templates/policy_tracker.html`
- "Add Policy" button: POST form to `/api/tracker/policies` or `showErrorModal('...')`
- "Renew" buttons on each row: POST to `/api/tracker/policies/{{ policy_id }}/renew` via `apiFetch()`
- "Back" button: `href="/home"`

### `app/ui/templates/reports/index.html`
- "Generate Report" button: POST form to `/api/reports/generate`
- "Download PDF" links: `href="/api/reports/{{ report.id }}/pdf"`
- "Back" button: `href="/home"`

### `app/ui/templates/reports/compliance.html`
- "Export" button: `href="/api/reports/{{ id }}/pdf"` or `showErrorModal('...')`
- "Back" button: `href="/report"`

### `app/ui/templates/knowledge_base.html`
- Search form: `method="GET"` `action="/knowledge-base"`
- Result links: real `href` values to relevant sections
- Any `href="#"`: fix

### `app/ui/templates/audit_trail.html`
- Filter/search form: `method="GET"` `action="/audit-trail"`
- "Export" button: `href="/api/audit/export"` or `showErrorModal('Export coming soon.')`
- Pagination: `href="?page={{ n }}"`

### `app/ui/templates/clients/index.html`
- "Add Client" button: link to a new client form page or `showErrorModal('...')`
- Each client card: `href="/clients/{{ client.id }}"`

### `app/ui/templates/clients/list.html`
- Each client row: `href="/clients/{{ client.id }}"`
- "View Policy" link: `href="/documents-ui?client_id={{ client.id }}"`

### `app/ui/templates/clients/profile.html`
- "Edit" button: `showErrorModal('Client editing coming soon.')` if not implemented
- "Add Note" button: POST to `/api/clients/{{ client.id }}/notes` via `apiFetch()`
- "Back" button: `href="/clients/"`

---

## TASK 4 (D4 Auditor) — Run these audit commands after D1+D2+D3 finish

```bash
echo "=== Audit 1: Dead href='#' without onclick ==="
grep -rn 'href="#"' app/ui/templates/ --include="*.html" | grep -v "onclick" | wc -l
echo "(Target: 0)"

echo ""
echo "=== Audit 2: alert() calls in templates ==="
grep -rn 'window\.alert\|[^w]alert(' app/ui/templates/ --include="*.html" | wc -l
echo "(Target: 0)"

echo ""
echo "=== Audit 3: alert() calls in JS files ==="
grep -rn 'window\.alert\|[^w]alert(' app/ui/static/ --include="*.js" | grep -v "showErrorModal\|showSuccessModal\|_showBanner" | wc -l
echo "(Target: 0)"

echo ""
echo "=== Audit 4: raw fetch() calls (should use apiFetch) ==="
grep -rn "[^a-zA-Z]fetch(" app/ui/static/ --include="*.js" | grep -v "apiFetch\|#" | wc -l
echo "(Target: 0 or very low — only non-auth fetches like CDN loads are OK)"

echo ""
echo "=== Audit 5: Key pages load with auth ==="
# Must have a valid cookie in /tmp/test_cookies.txt from Job B verification
for page in home documents-ui upload-ui compliance-center analytics audit-trail settings report insurer-intelligence clients; do
  CODE=$(curl -s -b /tmp/test_cookies.txt -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000/$page")
  echo "  /$page → $CODE"
done
echo "(All should be 200, none should be 500)"

echo ""
echo "=== Audit 6: apiFetch defined in api.js ==="
grep -n "function apiFetch" app/ui/static/js/api.js && echo "PASS: apiFetch defined" || echo "FAIL: apiFetch missing"

echo ""
echo "=== Audit 7: showErrorModal defined in api.js ==="
grep -n "function showErrorModal" app/ui/static/js/api.js && echo "PASS" || echo "FAIL"
```

---

## VERIFICATION STEPS (Final — run after all audits pass)

```bash
# V1 — Zero dead links
COUNT=$(grep -rn 'href="#"' app/ui/templates/ --include="*.html" | grep -v "onclick" | wc -l)
[ "$COUNT" = "0" ] && echo "PASS: no dead links" || echo "FAIL: $COUNT dead links remain"

# V2 — Zero browser alerts
COUNT=$(grep -rn 'window\.alert\|[^w]alert(' app/ui/ --include="*.html" --include="*.js" \
  | grep -v "showErrorModal\|showSuccessModal\|_showBanner" | wc -l)
[ "$COUNT" = "0" ] && echo "PASS: no alert() calls" || echo "FAIL: $COUNT alert() calls remain"

# V3 — api.js has all three helpers
for fn in showErrorModal showSuccessModal apiFetch; do
  grep -q "function $fn" app/ui/static/js/api.js \
    && echo "PASS: $fn defined" || echo "FAIL: $fn missing"
done

# V4 — All main pages return 200
for page in home documents-ui upload-ui compliance-center analytics audit-trail settings report; do
  CODE=$(curl -s -b /tmp/test_cookies.txt -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000/$page")
  [ "$CODE" = "200" ] && echo "PASS: /$page" || echo "FAIL: /$page → $CODE"
done
```
