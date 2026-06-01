"""Temporary smoke test for queue foundation — delete after verification."""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./smoke_test.db")

from app.core.db import Base, engine
import app.modules.jobs.model  # register tables
Base.metadata.create_all(bind=engine)

from app.queue.sqlite_queue import SQLiteJobQueue
from app.modules.jobs.repo import queue_stats
from app.core.db import session_scope

q = SQLiteJobQueue(retry_base_seconds=1)

# 1. Enqueue with step tracking
jid = q.enqueue(
    "ingestion_queue", "process_document",
    document_id=99, step_name="nlp", batch_id=1, max_attempts=2,
    some_kwarg="hello",
)
print(f"[1] enqueued job_id={jid}")

# 2. Claim
snap = q.claim_next("ingestion_queue", "test-worker")
assert snap is not None, "claim_next returned None"
print(f"[2] claimed id={snap.id} fn={snap.fn_name} payload={snap.payload}")

# 3. Mark processing
q.mark_processing(snap.id, "test-worker")
assert q.job_status(snap.id) == "processing"
print(f"[3] status=processing OK")

# 4. First failure — should retry (attempt 1 of 2)
q.mark_failed(snap.id, "connection error", "ConnectionError")
status = q.job_status(snap.id)
assert status == "queued", f"expected 'queued' after first fail, got {status!r}"
print(f"[4] after fail 1: status={status} (retry scheduled) OK")

# 5. Claim retry (scheduled_for may be 1s away — wait a moment)
import time; time.sleep(2)
snap2 = q.claim_next("ingestion_queue", "test-worker")
assert snap2 is not None, "retry claim returned None"
assert snap2.attempt == 1, f"expected attempt=1, got {snap2.attempt}"
print(f"[5] retry claim id={snap2.id} attempt={snap2.attempt} OK")

# 6. Second failure — should dead-letter (attempt 2 of 2 = max)
q.mark_processing(snap2.id, "test-worker")
q.mark_failed(snap2.id, "still broken", "ConnectionError")
status2 = q.job_status(snap2.id)
assert status2 == "dead_letter", f"expected 'dead_letter', got {status2!r}"
print(f"[6] after fail 2: status={status2} OK")

# 7. Stats
with session_scope() as db:
    stats = queue_stats(db)
print(f"[7] stats={stats}")
assert stats["dead_letter_total"] == 1
assert stats["dead_letter_pending_redrive"] == 1
print(f"[7] dead-letter counts OK")

# 8. Enqueue a second job and mark complete
jid2 = q.enqueue("ingestion_queue", "process_document", document_id=100, step_name="nlp")
snap3 = q.claim_next("ingestion_queue", "test-worker")
q.mark_processing(snap3.id, "test-worker")
q.mark_complete(snap3.id)
assert q.job_status(snap3.id) == "complete"
print(f"[8] complete path OK")

print("\nSMOKE TEST PASSED")
