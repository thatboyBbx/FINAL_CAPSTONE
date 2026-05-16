/**
 * theme-toggle.js — Standalone theme toggle for InsureIntel Zimbabwe
 * localStorage key: "insureIntelTheme" (values: "dark" | "light")
 * Toggled by calling toggleTheme() — exposed on window
 */
(function () {
  'use strict';

  const STORAGE_KEY = 'insureIntelTheme';

  function applyTheme(theme) {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }

  window.toggleTheme = function () {
    const isDark = document.documentElement.classList.toggle('dark');
    const theme = isDark ? 'dark' : 'light';
    try { localStorage.setItem(STORAGE_KEY, theme); } catch (_) {}
  };

  // Apply persisted theme on load (also done inline in base.html for FOUC prevention)
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) applyTheme(stored);
  } catch (_) {}
})();
