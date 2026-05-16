# Knowledge Base & UI Fixes
**Project:** Insurance Document Intelligence Platform

## Knowledge Base (RAG Layer)

### qa_engine.py
**Canonical location:** `app/ai/rag/qa_engine.py`
**Backward-compat stub:** `app/rag/qa_engine.py`

Changes applied:

1. **Module-level logger** (line 26): `logger = logging.getLogger(__name__)` — already present; confirmed.

2. **DEBUG log — query received** (in `QAEngine.answer`, after docstring):
   ```python
   logger.debug("QAEngine.answer — document_id=%s question=%r", document_id, question[:80])
   ```

3. **DEBUG log — documents retrieved** (after `_score_sentences` call):
   ```python
   logger.debug(
       "QAEngine: scored %d candidate sentences for document_id=%s",
       len(results), document_id,
   )
   ```

4. **DEBUG log — keywords extracted** (after `_extract_keywords` call):
   ```python
   logger.debug(
       "QAEngine: extracted %d keywords from question for document_id=%s",
       len(keywords), document_id,
   )
   ```

5. **WARNING — empty document_text** (empty document case):
   ```python
   logger.warning(
       "QAEngine: empty document_text for document_id=%s — returning fallback", document_id,
   )
   ```

6. **WARNING — no keywords extracted** (empty keyword case):
   ```python
   logger.warning(
       "QAEngine: no meaningful keywords extracted for document_id=%s question=%r", ...,
   )
   ```

7. **WARNING — zero documents retrieved** (empty results case):
   ```python
   logger.warning(
       "QAEngine: zero documents retrieved for document_id=%s question=%r — returning fallback", ...,
   )
   ```

8. **Structured fallback for empty retrieval** — explicit `_FALLBACK_EMPTY` dict defined at module level:
   ```python
   _FALLBACK_EMPTY: dict[str, Any] = {
       "answer": "No relevant documents found in the knowledge base for this query.",
       "sources": [], "confidence": 0.0,
   }
   ```
   Applied in the zero-results branch of `answer()`.

9. **ERROR — unhandled exception** (wrapping entire `answer()` body in try/except):
   ```python
   except Exception as exc:
       logger.error(
           "QAEngine: unhandled exception for document_id=%s: %s", document_id, exc, exc_info=True,
       )
       raise
   ```

---

### vector_store.py
**Canonical location:** `app/ai/rag/vector_store.py`
**Backward-compat stub:** `app/rag/vector_store.py`

Changes applied:

1. **Module-level logger** (line 10): `logger = logging.getLogger(__name__)` — already present; confirmed.

2. **ChromaDB collection init wrapped in try/except** (`VectorStore.__init__`):
   - ImportError already caught.
   - Added bare `except Exception` block:
     ```python
     except Exception as exc:
         logger.error(
             "ChromaDB collection could not be loaded from '%s': %s", persist_dir, exc, exc_info=True,
         )
         raise RuntimeError(
             f"VectorStore failed to initialise ChromaDB at '{persist_dir}': {exc}"
         ) from exc
     ```
   - This raises a descriptive `RuntimeError` instead of propagating the raw exception.

3. **`collection.add()` / upsert wrapped** (in `embed_and_store`): try/except already present around `self._col.upsert(...)`, logs via `logger.error`.

4. **`collection.query()` wrapped** (in `query`): try/except already present, logs via `logger.warning`, returns `[]` on failure.

5. **`collection.delete()` wrapped** (in `delete_document`): try/except already present, logs via `logger.error`.

6. **`health_check() -> bool` method added** to `VectorStore` class:
   ```python
   def health_check(self) -> bool:
       """Return True if the ChromaDB collection is reachable, False otherwise."""
       try:
           self._col.count()
           return True
       except Exception as exc:
           logger.warning("VectorStore health_check failed: %s", exc)
           return False
   ```
   Used by application startup lifespan to verify RAG layer availability.

---

## UI Error Visibility

### `app/ui/templates/base.html`
**Change:** Updated light-mode `.alert-error` rule and added `.error-visible` class.

Before:
```css
html:not(.dark) .alert-error { background:rgba(186,26,26,0.06); color:#ba1a1a; }
```

After:
```css
html:not(.dark) .alert-error { background:#fff1f0; color:#ff4d4f; border-color:#ffccc7; }
.error-visible {
  color:#ff4d4f;
  background:#fff1f0;
  border:1px solid #ffccc7;
  border-radius:4px;
  padding:8px 12px;
}
```

**Scope:** Applies to all pages using the base template — all error alerts rendered via
`alert_error()` macro (`app/ui/templates/macros/alerts.html`) and `form_error()` macro
(`app/ui/templates/macros/forms.html`) now display with the spec-compliant error colours
in light mode.

### `app/ui/templates/login.html`
**Change:** Updated inline `.alert-error` style and light-mode override.

Before:
```css
.alert-error { ... background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.28); color:#f87171; }
html:not(.dark) .alert-error { color:#dc2626; }
```

After:
```css
.alert-error { ... padding:8px 12px; border-radius:4px; background:rgba(239,68,68,0.1); ... color:#f87171; }
html:not(.dark) .alert-error { color:#ff4d4f; background:#fff1f0; border:1px solid #ffccc7; }
```

**Applies to:** The `{% if error %}` alert block at line 113 (login form validation error).

### `app/ui/templates/register.html`
**Change:** Updated inline `.alert-error` style and light-mode override.

Before:
```css
.alert-error { ... color:#f87171; }
html:not(.dark) .alert-error { color:#dc2626; }
```

After:
```css
.alert-error { ... padding:8px 12px; border-radius:4px; ... color:#f87171; }
html:not(.dark) .alert-error { color:#ff4d4f; background:#fff1f0; border:1px solid #ffccc7; }
```

**Applies to:** Registration form error and success alerts (lines 81, 84).

### Elements not modified
- `display: none` on accordion sidebar bodies (`base.html`) — navigation UI, not error state.
- `display: none` on `#globalErrorModal` — correctly hidden until `showGlobalError()` JS call.
- `display: none` on `#upload-error` (`documents/upload.html`) — correctly hidden by default;
  shown via `element.style.display = "block"` by the XHR error handler. Uses `.alert-error`
  class which now inherits the corrected light-mode styles from `base.html`.
- File preview and progress divs in upload form — functional UI state, not error displays.
