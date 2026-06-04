/**
 * Global topbar search.
 *
 * Searches documents, insurers, clients, and core pages through
 * GET /api/global-search?q=...
 */
(function () {
  "use strict";

  const root = document.getElementById("global-search");
  const input = document.getElementById("global-search-input");
  const panel = document.getElementById("global-search-results");
  if (!root || !input || !panel) return;

  let debounceTimer = null;
  let activeIndex = -1;
  let lastResults = [];
  let requestId = 0;

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function openPanel() {
    panel.style.display = "block";
    input.setAttribute("aria-expanded", "true");
  }

  function closePanel() {
    panel.style.display = "none";
    input.setAttribute("aria-expanded", "false");
    activeIndex = -1;
  }

  function setLoading() {
    panel.innerHTML = `
      <div class="global-search-state">
        <span class="material-symbols-outlined">progress_activity</span>
        <span>Searching...</span>
      </div>`;
    openPanel();
  }

  function setEmpty(message) {
    lastResults = [];
    panel.innerHTML = `
      <div class="global-search-state">
        <span class="material-symbols-outlined">search_off</span>
        <span>${escapeHtml(message)}</span>
      </div>`;
    openPanel();
  }

  function renderResults(results) {
    lastResults = results || [];
    activeIndex = -1;
    if (!lastResults.length) {
      setEmpty("No matches found");
      return;
    }

    panel.innerHTML = lastResults.map((item, index) => `
      <a class="global-search-result"
         role="option"
         id="global-search-result-${index}"
         data-index="${index}"
         href="${escapeHtml(item.href)}">
        <span class="material-symbols-outlined global-search-icon">${escapeHtml(item.icon || "search")}</span>
        <span class="global-search-copy">
          <span class="global-search-title">${escapeHtml(item.label)}</span>
          <span class="global-search-meta">${escapeHtml(item.type)} · ${escapeHtml(item.meta)}</span>
        </span>
      </a>`).join("");
    openPanel();
  }

  function updateActive(nextIndex) {
    const items = [...panel.querySelectorAll(".global-search-result")];
    items.forEach((el) => el.classList.remove("active"));
    if (!items.length) return;

    activeIndex = (nextIndex + items.length) % items.length;
    const active = items[activeIndex];
    active.classList.add("active");
    input.setAttribute("aria-activedescendant", active.id);
    active.scrollIntoView({ block: "nearest" });
  }

  async function runSearch(query) {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      closePanel();
      return;
    }

    const currentRequest = ++requestId;
    setLoading();
    try {
      const data = await apiFetch(`/api/global-search?q=${encodeURIComponent(trimmed)}&limit=8`);
      if (currentRequest !== requestId) return;
      renderResults(data.results || []);
    } catch (err) {
      if (currentRequest !== requestId) return;
      setEmpty(err.message || "Search failed");
    }
  }

  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => runSearch(input.value), 180);
  });

  input.addEventListener("focus", () => {
    if (lastResults.length) openPanel();
  });

  input.addEventListener("keydown", (event) => {
    const items = panel.querySelectorAll(".global-search-result");
    if (event.key === "Escape") {
      closePanel();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (items.length) updateActive(activeIndex + 1);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (items.length) updateActive(activeIndex - 1);
      return;
    }
    if (event.key === "Enter") {
      if (activeIndex >= 0 && items[activeIndex]) {
        event.preventDefault();
        window.location.href = items[activeIndex].href;
      } else if (lastResults[0]) {
        event.preventDefault();
        window.location.href = lastResults[0].href;
      }
    }
  });

  document.addEventListener("click", (event) => {
    if (!root.contains(event.target)) closePanel();
  });
})();
