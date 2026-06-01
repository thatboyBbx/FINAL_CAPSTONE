"""
app/modules/auth/lockout.py
============================
In-process per-staff_id login lockout.

slowapi rate-limits by IP, which a distributed credential-stuffing attacker
bypasses trivially. This module adds a complementary defence: after
``AUTH_LOCKOUT_MAX_FAILURES`` failed password attempts within
``AUTH_LOCKOUT_WINDOW_SECONDS``, all further attempts against the same
``staff_id`` are rejected for the rest of the window — regardless of source IP.

State lives in process memory. Single-instance deployments only; for a
multi-instance fleet, swap the dict for a Redis-backed counter and keep the
function signatures.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict

from app.core.config import settings

_lock = threading.Lock()
_failures: Dict[str, Deque[float]] = {}


def _prune(staff_id: str, now: float, window: int) -> Deque[float]:
    """Drop failure timestamps older than the window; return the remaining deque."""
    dq = _failures.get(staff_id)
    if dq is None:
        dq = deque()
        _failures[staff_id] = dq
    cutoff = now - window
    while dq and dq[0] < cutoff:
        dq.popleft()
    return dq


def is_locked(staff_id: str) -> bool:
    """True when the account has hit the failure ceiling within the window."""
    window = settings.auth_lockout_window_seconds
    ceiling = settings.auth_lockout_max_failures
    if ceiling <= 0 or window <= 0:
        return False
    with _lock:
        dq = _prune(staff_id, time.monotonic(), window)
        return len(dq) >= ceiling


def record_failure(staff_id: str) -> None:
    """Note one failed password attempt against this staff_id."""
    window = settings.auth_lockout_window_seconds
    if window <= 0:
        return
    with _lock:
        dq = _prune(staff_id, time.monotonic(), window)
        dq.append(time.monotonic())


def clear_failures(staff_id: str) -> None:
    """Reset the counter — called after a successful authentication."""
    with _lock:
        _failures.pop(staff_id, None)
