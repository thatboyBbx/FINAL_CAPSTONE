/**
 * sidebar.js — Accordion sidebar logic for InsureIntel Zimbabwe
 *
 * Features:
 *  - Single-open accordion: opening one section collapses all others
 *  - Persists collapsed/expanded state to localStorage("sidebar_state")
 *  - Auto-expands the active section based on window.location.pathname
 *  - Hamburger toggle: collapsed (64px) ↔ expanded (256px)
 *  - Emits a CustomEvent("sidebarToggle") on width change so pages can adapt
 *
 * Loaded via <script src="/static/js/sidebar.js"> in base.html before </body>.
 */

(function () {
  "use strict";

  /* ── Constants ───────────────────────────────────────────────────────────── */

  const STORAGE_KEY  = "sidebar_state";       // localStorage key for accordion state
  const COLLAPSE_KEY = "sidebar_collapsed";   // localStorage key for sidebar width
  const EXPANDED_W   = "250px";
  const COLLAPSED_W  = "64px";
  const MAIN_EXPAND  = "250px";
  const MAIN_COLLAPSE = "64px";
  const MOBILE_QUERY = "(max-width: 1023px)";

  /* ── State ───────────────────────────────────────────────────────────────── */

  /** @type {Object.<string, boolean>} section id → open state */
  let accordionState = {};
  /** @type {boolean} whether the sidebar is in icon-only (collapsed) mode */
  let sidebarCollapsed = false;

  /* ── Load persisted state ────────────────────────────────────────────────── */

  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) accordionState = JSON.parse(stored);
  } catch (_) {}

  try {
    sidebarCollapsed = localStorage.getItem(COLLAPSE_KEY) === "true";
  } catch (_) {}

  /* ── Helpers ─────────────────────────────────────────────────────────────── */

  /** Persist current accordionState to localStorage. */
  function _saveAccordionState() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(accordionState));
    } catch (_) {}
  }

  /** Persist sidebarCollapsed to localStorage. */
  function _saveCollapseState() {
    try {
      localStorage.setItem(COLLAPSE_KEY, String(sidebarCollapsed));
    } catch (_) {}
  }

  function _isMobile() {
    return window.matchMedia(MOBILE_QUERY).matches;
  }

  /**
   * _applyAccordion — show/hide the child <ul> of a section based on state.
   * @param {string} sectionId — the data-section-id attribute value
   * @param {boolean} open     — whether to open
   * @param {boolean} animate  — whether to animate (false for initial paint)
   */
  function _applyAccordion(sectionId, open, animate = true) {
    const ul = document.querySelector(`[data-accordion-body="${sectionId}"]`);
    const trigger = document.querySelector(`[data-accordion-trigger="${sectionId}"]`);
    const chevron = trigger && trigger.querySelector(".chevron");
    if (!ul) return;

    if (open) {
      ul.style.display = "block";
      if (animate) {
        ul.style.animation = "accordionOpen 0.18s ease forwards";
      }
      if (chevron) chevron.style.transform = "rotate(90deg)";
    } else {
      if (animate) {
        ul.style.animation = "accordionClose 0.15s ease forwards";
        setTimeout(() => {
          if (!accordionState[sectionId]) ul.style.display = "none";
        }, 160);
      } else {
        ul.style.display = "none";
      }
      if (chevron) chevron.style.transform = "rotate(0deg)";
    }
  }

  /**
   * toggleSection — toggle one section; collapses all others (single-open).
   * @param {string} sectionId — the section to toggle
   */
  function toggleSection(sectionId) {
    const wasOpen = !!accordionState[sectionId];

    // Close all sections
    Object.keys(accordionState).forEach((id) => {
      accordionState[id] = false;
      _applyAccordion(id, false, true);
    });

    // Also close any sections not yet in state
    document.querySelectorAll("[data-accordion-trigger]").forEach((el) => {
      const id = el.getAttribute("data-accordion-trigger");
      if (!(id in accordionState)) {
        accordionState[id] = false;
        _applyAccordion(id, false, true);
      }
    });

    // Open the clicked section (unless it was already open)
    if (!wasOpen) {
      accordionState[sectionId] = true;
      _applyAccordion(sectionId, true, true);
    }

    _saveAccordionState();
  }

  /**
   * _autoExpand — detect current path and open the relevant section.
   * Compares window.location.pathname against data-section-paths attribute.
   */
  function _autoExpand() {
    const path = window.location.pathname;
    document.querySelectorAll("[data-accordion-trigger]").forEach((el) => {
      const sectionId = el.getAttribute("data-accordion-trigger");
      const paths = (el.getAttribute("data-section-paths") || "").split(",").map((p) => p.trim());
      const isActive = paths.some((p) => p && path.startsWith(p));
      if (isActive && !accordionState[sectionId]) {
        // Close others first
        Object.keys(accordionState).forEach((id) => {
          if (id !== sectionId) {
            accordionState[id] = false;
            _applyAccordion(id, false, false);
          }
        });
        accordionState[sectionId] = true;
        _applyAccordion(sectionId, true, false);
        _saveAccordionState();
      }
    });
  }

  /* ── Sidebar collapse / expand ───────────────────────────────────────────── */

  /**
   * applySidebarWidth — sets the sidebar and main-content widths.
   * @param {boolean} collapsed — true = 64px icon-only mode
   * @param {boolean} animate   — whether to apply CSS transitions
   */
  function _applySidebarWidth(collapsed, animate = true) {
    const sidebar = document.getElementById("sidebar");
    const wrapper = document.getElementById("main-wrapper");
    const labels  = document.querySelectorAll(".sidebar-label");
    const logo    = document.getElementById("sidebar-logo-text");
    const dockBtn = document.getElementById("sidebar-dock-toggle");

    if (!sidebar) return;

    if (_isMobile()) {
      document.body.classList.remove("sidebar-collapsed");
      sidebar.style.width = EXPANDED_W;
      if (wrapper) {
        wrapper.style.marginLeft = "0";
        wrapper.style.width = "100%";
        wrapper.style.maxWidth = "100%";
      }
      labels.forEach((l) => {
        l.style.display = "";
        l.style.opacity = "1";
      });
      if (logo) logo.style.display = "";
      if (dockBtn) {
        dockBtn.setAttribute("aria-expanded", sidebar.classList.contains("mobile-open") ? "true" : "false");
        dockBtn.title = "Close sidebar";
        const icon = dockBtn.querySelector(".material-symbols-outlined");
        if (icon) icon.textContent = "close";
      }
      return;
    }

    if (animate) {
      sidebar.style.transition = "width 0.25s ease";
      if (wrapper) wrapper.style.transition = "margin-left 0.25s ease, width 0.25s ease, max-width 0.25s ease";
    }

    document.body.classList.toggle("sidebar-collapsed", collapsed);
    sidebar.style.width = collapsed ? COLLAPSED_W : EXPANDED_W;
    sidebar.style.overflowX = "visible";

    if (wrapper) {
      const sidebarWidth = collapsed ? MAIN_COLLAPSE : MAIN_EXPAND;
      wrapper.style.marginLeft = sidebarWidth;
      wrapper.style.width = `calc(100% - ${sidebarWidth})`;
      wrapper.style.maxWidth = `calc(100% - ${sidebarWidth})`;
    }

    // Show/hide text labels
    labels.forEach((l) => {
      l.style.display = collapsed ? "none" : "";
      l.style.opacity = collapsed ? "0" : "1";
    });

    if (logo) logo.style.display = collapsed ? "none" : "";

    document.querySelectorAll("[data-accordion-body]").forEach((el) => {
      const id = el.getAttribute("data-accordion-body");
      el.style.display = collapsed ? "none" : (accordionState[id] ? "block" : "none");
    });

    // Update hamburger icon
    const hbIcon = document.getElementById("sidebar-toggle-icon");
    if (hbIcon) hbIcon.textContent = collapsed ? "menu" : "menu_open";

    if (dockBtn) {
      dockBtn.setAttribute("aria-expanded", collapsed ? "false" : "true");
      dockBtn.title = collapsed ? "Dock sidebar" : "Collapse sidebar";
      const icon = dockBtn.querySelector(".material-symbols-outlined");
      if (icon) icon.textContent = "keyboard_double_arrow_left";
    }

    // Update nav-section labels
    document.querySelectorAll(".nav-section").forEach((el) => {
      el.style.display = collapsed ? "none" : "";
    });

    // Dispatch event so charts/tables can resize
    window.dispatchEvent(new CustomEvent("sidebarToggle", { detail: { collapsed } }));
  }

  /**
   * toggleSidebar — public: called by hamburger button onclick.
   */
  window.toggleSidebar = function () {
    if (_isMobile()) {
      const sidebar = document.getElementById("sidebar");
      if (!sidebar) return;
      if (sidebar.classList.contains("mobile-open")) {
        if (typeof window.mobileSidebarClose === "function") {
          window.mobileSidebarClose();
        } else {
          sidebar.classList.remove("mobile-open");
        }
      } else if (typeof window.mobileSidebarOpen === "function") {
        window.mobileSidebarOpen();
      } else {
        sidebar.classList.add("mobile-open");
      }
      _applySidebarWidth(false, true);
      return;
    }

    sidebarCollapsed = !sidebarCollapsed;
    _saveCollapseState();
    _applySidebarWidth(sidebarCollapsed, true);
  };

  /* Accordion keyframes (.chevron / #sidebar / #main-content transitions)
     live in static/css/main.css and static/css/layout.css. */

  /* ── Init on DOMContentLoaded ────────────────────────────────────────────── */

  function init() {
    // Wire up accordion triggers
    document.querySelectorAll("[data-accordion-trigger]").forEach((el) => {
      const sectionId = el.getAttribute("data-accordion-trigger");
      el.addEventListener("click", (e) => {
        e.preventDefault();
        // Only toggle if sidebar is expanded; if collapsed, expand sidebar first
        if (sidebarCollapsed) {
          sidebarCollapsed = false;
          _saveCollapseState();
          _applySidebarWidth(false, true);
          // Open section after sidebar expands
          setTimeout(() => toggleSection(sectionId), 260);
        } else {
          toggleSection(sectionId);
        }
      });
    });

    // Restore accordion state (no animation for initial render)
    document.querySelectorAll("[data-accordion-body]").forEach((el) => {
      const id = el.getAttribute("data-accordion-body");
      el.style.display = accordionState[id] ? "block" : "none";
      const trigger = document.querySelector(`[data-accordion-trigger="${id}"]`);
      const chevron = trigger && trigger.querySelector(".chevron");
      if (chevron) chevron.style.transform = accordionState[id] ? "rotate(90deg)" : "rotate(0deg)";
    });

    // Auto-expand based on current path
    _autoExpand();

    // Apply sidebar collapsed/expanded state (no animation for initial render)
    _applySidebarWidth(sidebarCollapsed, false);

    window.addEventListener("resize", () => {
      _applySidebarWidth(sidebarCollapsed, false);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  /* Expose toggleSection globally so inline onclick= attributes can call it */
  window.toggleSection = toggleSection;
})();
