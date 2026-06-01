# TRANSACTION_RULES.md
## InsureIntel Zimbabwe — Transaction Handling Standards

---

## 1. Standard Request Lifecycle (FastAPI Dependency)

All HTTP-request-scoped database sessions are managed by `app.core.db.get_db`.
This generator opens a session, yields it to the handler, and closes it on completion.
The `get_db` dependency must never be modified to auto-commit.

```python
# app/core/db.py — canonical pattern (do not change)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## 2. Commit Ownership

**Rule:** The service layer owns commit/rollback. Repos must not call `db.commit()` or `db.rollback()`.

This keeps transaction boundaries explicit and allows a service to perform multiple repo
operations inside a single atomic unit.

**Correct pattern (service commits):**
```python
class InsurerService:
    def create_insurer(self, db: Session, payload: InsurerCreate) -> Insurer:
        if self.repo.get_by_name(db, payload.name):
            raise ValueError("Insurer already exists.")
        insurer = self.repo.build(payload)   # creates ORM object, does NOT commit
        db.add(insurer)
        db.commit()
        db.refresh(insurer)
        return insurer
```

**Wrong pattern (repo commits — present in `InsurerRepo.create` and several other repos):**
```python
# VIOLATION: repo must not commit
def create(self, db, payload):
    insurer = Insurer(...)
    db.add(insurer)
    db.commit()   # ← move this to the service
    db.refresh(insurer)
    return insurer
```

---

## 3. Known Deviations

The following files currently call `db.commit()` inside repo methods. These are tracked technical
debt items. Do not introduce new occurrences.

| File | Method | Planned fix |
|---|---|---|
| `app/modules/insurers/repo.py` | `InsurerRepo.create` | Move commit to `InsurerService.create_insurer` |
| `app/modules/financials/repo.py` | (verify) | Audit and move commits to service layer |
| `app/modules/circulars/repo.py` | (verify) | Audit and move commits to service layer |

---

## 4. Multi-Step Service Transactions

When a service performs multiple writes that must succeed or fail together, wrap them in a
single transaction block:

```python
def process_document(self, db: Session, doc_id: int) -> None:
    doc = self.doc_repo.get(db, doc_id)
    entities = self.extractor.extract(doc.extracted_text)
    self.entity_repo.bulk_insert(db, doc_id, entities)   # does not commit
    self.doc_repo.set_status(db, doc_id, "processed")     # does not commit
    db.commit()   # single commit — atomically persists entities + status
```

Never commit inside a loop unless each loop iteration is intentionally its own independent unit
of work. If one document in a batch may fail without rolling back others, commit per iteration
with explicit per-iteration `try/except db.rollback()`.

---

## 5. Background / Batch Jobs

Background tasks (FastAPI `BackgroundTasks`, scheduler jobs) must manage their own sessions.
They must **not** reuse the request-scoped `db` session passed from a router.

**Pattern for background tasks:**
```python
def _process_in_background(doc_id: int) -> None:
    db = SessionLocal()
    try:
        # ... do work ...
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Background task failed for doc_id=%s", doc_id)
        raise
    finally:
        db.close()
```

---

## 6. Batch Processor Commit Strategy

`app/batch/batch_processor.py` currently commits once per document inside a loop. This is
intentional — each document record is an independent unit; a failure on one document should not
prevent the rest from being recorded. Maintain this per-iteration commit pattern with per-iteration
rollback on error.

---

## 7. Nested Transactions

Do not use SQLAlchemy `db.begin_nested()` (savepoints) unless you have explicitly verified
the underlying SQLite/PostgreSQL driver supports it. SQLite's savepoint support is limited.
Use the single-session, single-commit pattern instead.

---

## 8. Session Reuse Across Modules

Pass the same `db: Session` down the call stack within a single request. Never instantiate
`SessionLocal()` inside a service method that was called from a router (the router already has
a session from `Depends(get_db)`).
