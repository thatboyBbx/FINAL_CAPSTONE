# Knowledge Base Stability Fix

## Problem Areas
- qa_engine.py
- vector_store.py

## Fixes
- Add try/except around retrieval
- Handle empty embeddings
- Add logging

## Expected
- No crashes on query
- Graceful fallback response