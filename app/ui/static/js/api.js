/**
 * api.js — InsureIntel Zimbabwe
 *
 * Centralised API helpers (apiGet/apiPost/apiPatch/apiDelete + apiFetch),
 * UI helpers (showToast, showErrorModal, showSuccessModal, showProgress,
 * confirmDialog), and a reusable fetch core that standardises error
 * handling across the whole front-end.
 *
 * Loaded via <script defer src="/static/js/api.js"> from base.html.
 * Never use window.alert() anywhere in this codebase.
 */

function showErrorModal(message, durationMs = 5000) {
  _showBanner(message, 'insure-intel-error-banner', 'var(--cerr, #ff4d4d)', durationMs);
}

function showSuccessModal(message, durationMs = 3000) {
  _showBanner(message, 'insure-intel-success-banner', 'var(--cp, #d4af37)', durationMs);
}

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
    fontSize: '14px',
    fontFamily: 'Inter, sans-serif',
    maxWidth: '480px',
    width: 'max-content',
    textAlign: 'center',
    backdropFilter: 'blur(8px)',
    boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
    lineHeight: '1.4',
  });
  banner.style.setProperty('border', `1px solid ${color}`);
  banner.style.setProperty('color', color);
  banner.style.backgroundColor = 'rgba(15,15,15,0.92)';
  banner.textContent = message;

  document.body.appendChild(banner);
  setTimeout(() => { if (banner.parentNode) banner.remove(); }, durationMs);
}

async function apiFetch(url, options = {}) {
  const defaultHeaders = {};
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
    } catch (_) {}
    throw new Error(detail);
  }

  const contentType = response.headers.get('content-type') || '';
  if (response.status === 204 || !contentType.includes('application/json')) {
    return null;
  }

  return response.json();
}


/* ──────────────────────────────────────────────────────────────────────────
   INTERNAL HELPERS
   ────────────────────────────────────────────────────────────────────────── */

/**
 * _defaultHeaders — returns the standard headers for every request.
 * Reads the access_token cookie (set as httponly=false for JS access).
 * @returns {Object} headers object
 */
function _defaultHeaders() {
  const headers = { "Content-Type": "application/json" };
  // Read token from cookie — set samesite=lax, not httponly, so JS can read it
  const match = document.cookie.match(/(?:^|;\s*)access_token=([^;]+)/);
  if (match) {
    headers["Authorization"] = `Bearer ${decodeURIComponent(match[1])}`;
  }
  return headers;
}

/**
 * _handleResponse — parses response and throws on non-2xx.
 * Always tries to parse JSON; falls back to text for non-JSON bodies.
 * @param {Response} resp — raw fetch Response
 * @returns {Promise<any>} parsed body
 * @throws {Error} with .status and .detail populated
 */
async function _handleResponse(resp) {
  let body;
  const ct = resp.headers.get("content-type") || "";
  try {
    body = ct.includes("application/json") ? await resp.json() : await resp.text();
  } catch (_) {
    body = null;
  }
  if (!resp.ok) {
    const err = new Error(
      (body && body.detail) || (typeof body === "string" ? body : `HTTP ${resp.status}`)
    );
    err.status = resp.status;
    err.detail = body;
    throw err;
  }
  return body;
}


/* ──────────────────────────────────────────────────────────────────────────
   PUBLIC API FUNCTIONS
   ────────────────────────────────────────────────────────────────────────── */

/**
 * apiPost — POST JSON to the given URL.
 * @param {string} url       — endpoint path e.g. "/api/documents/upload"
 * @param {Object} body      — payload, serialised to JSON
 * @param {Object} [opts={}] — extra fetch options (e.g. signal for AbortController)
 * @returns {Promise<any>} parsed response body
 */
async function apiPost(url, body, opts = {}) {
  const resp = await fetch(url, {
    method: "POST",
    headers: _defaultHeaders(),
    body: JSON.stringify(body),
    ...opts,
  });
  return _handleResponse(resp);
}

/**
 * apiGet — GET the given URL.
 * @param {string} url       — endpoint path
 * @param {Object} [opts={}] — extra fetch options
 * @returns {Promise<any>} parsed response body
 */
async function apiGet(url, opts = {}) {
  const headers = { ..._defaultHeaders() };
  delete headers["Content-Type"]; // GET requests should not send Content-Type
  const resp = await fetch(url, {
    method: "GET",
    headers,
    ...opts,
  });
  return _handleResponse(resp);
}

/**
 * apiDelete — DELETE the given URL.
 * @param {string} url — endpoint path
 * @returns {Promise<any>} parsed response body
 */
async function apiDelete(url) {
  const headers = { ..._defaultHeaders() };
  delete headers["Content-Type"];
  const resp = await fetch(url, {
    method: "DELETE",
    headers,
  });
  return _handleResponse(resp);
}

/**
 * apiPatch — PATCH JSON to the given URL.
 * @param {string} url  — endpoint path
 * @param {Object} body — payload, serialised to JSON
 * @returns {Promise<any>} parsed response body
 */
async function apiPatch(url, body) {
  const resp = await fetch(url, {
    method: "PATCH",
    headers: _defaultHeaders(),
    body: JSON.stringify(body),
  });
  return _handleResponse(resp);
}


/* ──────────────────────────────────────────────────────────────────────────
   TOAST NOTIFICATION SYSTEM
   ────────────────────────────────────────────────────────────────────────── */

/**
 * showToast — displays a dismissible toast notification.
 * Injects into #toast-container (added to base.html).
 *
 * @param {string} msg         — message text
 * @param {string} [type]      — "success" | "error" | "warning" | "info"
 * @param {number} [durationMs] — auto-dismiss delay in ms (default 4000)
 */
function showToast(msg, type = "success", durationMs = 4000) {
  // Ensure the container exists (graceful fallback if base.html updated)
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.style.cssText =
      "position:fixed;bottom:1.5rem;right:1.5rem;z-index:9999;display:flex;flex-direction:column;gap:0.5rem;pointer-events:none;";
    document.body.appendChild(container);
  }

  // Colour map matching the design token palette
  const colours = {
    success: { bg: "#052e16", border: "#4ade80", label: "Success", accent: "#bbf7d0" },
    error:   { bg: "#450a0a", border: "#f87171", label: "Error",   accent: "#fecaca" },
    warning: { bg: "#451a03", border: "#fbbf24", label: "Warning", accent: "#fde68a" },
    info:    { bg: "#172554", border: "#60a5fa", label: "Info",    accent: "#bfdbfe" },
  };
  const c = colours[type] || colours.info;

  const toast = document.createElement("div");
  toast.style.cssText = `
    display:flex;align-items:flex-start;gap:0.625rem;
    padding:0.75rem 1rem;border-radius:0.625rem;
    background:${c.bg};border:1px solid ${c.border};
    min-width:260px;max-width:380px;pointer-events:all;
    box-shadow:0 12px 32px rgba(0,0,0,0.32);
    animation:toastIn 0.25s ease forwards;
    font-family:'Inter',sans-serif;font-size:0.875rem;
  `;
  toast.innerHTML = `
    <span style="color:${c.accent};font-size:0.68rem;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;flex-shrink:0;margin-top:0.15rem">${c.label}</span>
    <span style="color:#ffffff;flex:1;line-height:1.45;font-weight:600">${msg}</span>
    <button onclick="this.closest('[data-toast]').remove()"
            style="background:none;border:none;color:#ffffff;cursor:pointer;font-size:1.1rem;opacity:0.78;
                   padding:0;line-height:1;flex-shrink:0;margin-top:1px" aria-label="dismiss">
      <span aria-hidden="true">&times;</span>
    </button>
  `;
  toast.setAttribute("data-toast", "true");
  container.appendChild(toast);

  // Auto-dismiss after durationMs
  if (durationMs > 0) {
    setTimeout(() => {
      toast.style.animation = "toastOut 0.25s ease forwards";
      setTimeout(() => toast.remove(), 260);
    }, durationMs);
  }
}


/* ──────────────────────────────────────────────────────────────────────────
   PROGRESS BAR
   ────────────────────────────────────────────────────────────────────────── */

/**
 * showProgress — updates or hides the fixed top progress bar (#progress-bar).
 * @param {number} pct    — 0–100; pass 0 or <0 to hide
 * @param {string} [label] — optional aria-label for accessibility
 */
function showProgress(pct, label = "") {
  const bar = document.getElementById("progress-bar");
  if (!bar) return;
  if (pct <= 0) {
    bar.style.display = "none";
    bar.style.width = "0%";
    return;
  }
  bar.style.display = "block";
  bar.style.width = `${Math.min(100, pct)}%`;
  if (label) bar.setAttribute("aria-label", label);
}


/* ──────────────────────────────────────────────────────────────────────────
   CONFIRM DIALOG
   ────────────────────────────────────────────────────────────────────────── */

/**
 * confirmDialog — shows a custom glassmorphic confirmation modal.
 * Falls back to native window.confirm if the modal scaffold is absent.
 *
 * @param {string} msg — question to display to the user
 * @returns {Promise<boolean>} resolves true if confirmed, false if cancelled
 */
function confirmDialog(msg) {
  return new Promise((resolve) => {
    // Try to find or create a generic confirm modal
    let modal = document.getElementById("_confirmModal");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "_confirmModal";
      modal.style.cssText = `
        position:fixed;inset:0;z-index:10000;
        background:rgba(0,0,0,0.6);
        display:flex;align-items:center;justify-content:center;
        backdrop-filter:blur(4px);
      `;
      modal.innerHTML = `
        <div style="
          background:rgba(26,26,26,0.95);
          border:1px solid rgba(212,175,55,0.20);
          border-radius:1rem;padding:1.75rem 2rem;
          max-width:420px;width:90%;
          box-shadow:0 8px 40px rgba(0,0,0,0.4);
          font-family:'Inter',sans-serif;
        ">
          <p id="_confirmMsg" style="color:#f5f5f5;font-size:0.9375rem;line-height:1.5;margin:0 0 1.5rem"></p>
          <div style="display:flex;gap:0.75rem;justify-content:flex-end">
            <button id="_confirmCancel" style="
              background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);
              border-radius:0.5rem;color:#a1a1a1;padding:0.5rem 1.25rem;
              cursor:pointer;font-size:0.875rem;font-weight:600;
            ">Cancel</button>
            <button id="_confirmOk" style="
              background:rgba(212,175,55,0.18);border:1px solid rgba(212,175,55,0.4);
              border-radius:0.5rem;color:#d4af37;padding:0.5rem 1.25rem;
              cursor:pointer;font-size:0.875rem;font-weight:600;
            ">Confirm</button>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
    }

    document.getElementById("_confirmMsg").textContent = msg;
    modal.style.display = "flex";

    // Clean up and resolve
    const cleanup = (result) => {
      modal.style.display = "none";
      resolve(result);
    };

    document.getElementById("_confirmOk").onclick    = () => cleanup(true);
    document.getElementById("_confirmCancel").onclick = () => cleanup(false);
    modal.onclick = (e) => { if (e.target === modal) cleanup(false); };
  });
}


/* toastIn / toastOut keyframes live in static/css/main.css */


/* ──────────────────────────────────────────────────────────────────────────
   MODAL FOCUS MANAGEMENT
   Automatically traps focus, handles Escape, and restores focus on close
   for any element with role="dialog". Works with existing markup — no
   changes to individual pages needed to get keyboard accessibility.
   ────────────────────────────────────────────────────────────────────────── */

(function () {
  const FOCUSABLE = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
  ].join(',');

  function _trapFocus(modal, e) {
    const els = Array.from(modal.querySelectorAll(FOCUSABLE));
    if (!els.length) return;
    const first = els[0], last = els[els.length - 1];
    if (e.shiftKey) {
      if (document.activeElement === first) { last.focus(); e.preventDefault(); }
    } else {
      if (document.activeElement === last) { first.focus(); e.preventDefault(); }
    }
  }

  function _onModalOpen(modal) {
    document.body.style.overflow = 'hidden';
    const firstFocusable = modal.querySelector(FOCUSABLE);
    if (firstFocusable) firstFocusable.focus();
    modal._escapeFn = (e) => { if (e.key === 'Escape') closeModal(modal.id); };
    modal._tabFn    = (e) => { if (e.key === 'Tab') _trapFocus(modal, e); };
    document.addEventListener('keydown', modal._escapeFn);
    document.addEventListener('keydown', modal._tabFn);
  }

  function _onModalClose(modal) {
    if (modal._escapeFn) { document.removeEventListener('keydown', modal._escapeFn); modal._escapeFn = null; }
    if (modal._tabFn)    { document.removeEventListener('keydown', modal._tabFn);    modal._tabFn    = null; }
    const anyOpen = Array.from(document.querySelectorAll('[role="dialog"]'))
      .some((m) => !m.classList.contains('hidden'));
    if (!anyOpen) document.body.style.overflow = '';
    if (modal._trigger) { modal._trigger.focus(); modal._trigger = null; }
  }

  // MutationObserver watches class changes on all [role="dialog"] elements
  const _dialogObserver = new MutationObserver((mutations) => {
    mutations.forEach((m) => {
      if (m.type === 'attributes' && m.attributeName === 'class') {
        const el = m.target;
        const wasHidden = m.oldValue && m.oldValue.includes('hidden');
        const isHidden  = el.classList.contains('hidden');
        if (wasHidden && !isHidden) _onModalOpen(el);
        if (!wasHidden && isHidden) _onModalClose(el);
      }
    });
  });

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[role="dialog"]').forEach((el) => {
      _dialogObserver.observe(el, { attributes: true, attributeOldValue: true, attributeFilter: ['class'] });
    });
  });

  /**
   * openModal — show a modal by ID and wire up focus management.
   * @param {string} id — the modal element's id attribute
   * @param {Element|null} triggerEl — the element that opened the modal (focus returns here on close)
   */
  window.openModal = function (id, triggerEl) {
    const modal = document.getElementById(id);
    if (!modal) return;
    if (triggerEl) modal._trigger = triggerEl;
    modal.classList.remove('hidden');
  };

  /**
   * closeModal — hide a modal by ID and restore page state.
   * @param {string} id — the modal element's id attribute
   */
  window.closeModal = function (id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.add('hidden');
  };
})();
