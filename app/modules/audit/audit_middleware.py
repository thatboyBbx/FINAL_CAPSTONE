"""
AuditMiddleware — automatically logs every API request as an audit event.
Runs asynchronously so it does not add latency to responses.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.modules.audit.audit_logger import AuditLogger

logger = logging.getLogger(__name__)

# Map URL path prefixes to event type constants
_PATH_EVENT_MAP = {
    "/api/documents":         AuditLogger.DOCUMENT_UPLOADED,
    "/api/qa/ask":            AuditLogger.QA_QUESTION_ASKED,
    "/api/comparison":        AuditLogger.COMPARISON_RUN,
    "/api/feedback":          AuditLogger.FEEDBACK_SUBMITTED,
    "/api/batch":             AuditLogger.BATCH_UPLOADED,
    "/api/tracker":           AuditLogger.POLICY_ALERT_SENT,
    "/auth/login":            AuditLogger.USER_LOGIN,
    "/auth/logout":           AuditLogger.USER_LOGOUT,
    "/api/feedback/trigger":  AuditLogger.RETRAINING_TRIGGERED,
    "/api/audit":             AuditLogger.ADMIN_ACTION,
}


def _event_type_for_path(path: str) -> str | None:
    """Return the most specific matching event type for a request path."""
    # Longest matching prefix wins
    matched_prefix = ""
    matched_event = None
    for prefix, event in _PATH_EVENT_MAP.items():
        if path.startswith(prefix) and len(prefix) > len(matched_prefix):
            matched_prefix = prefix
            matched_event = event
    return matched_event


def _extract_actor(request: Request) -> str:
    """
    Extract the actor identifier from the request.
    Tries the Authorization Bearer token first, then cookie, then 'anonymous'.
    """
    actor = "anonymous"
    token: str | None = None

    # Try Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    # Try cookie fallback
    if not token:
        token = request.cookies.get("access_token")

    if token:
        try:
            from app.modules.auth.service import decode_access_token
            payload = decode_access_token(token)
            if payload:
                actor = payload.get("sub") or payload.get("user_id") or "unknown"
                actor = str(actor)
        except Exception:
            pass  # invalid token — treat as anonymous

    return actor


def _get_ip(request: Request) -> str:
    """Return the client IP, honouring X-Forwarded-For if present."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


class AuditMiddleware(BaseHTTPMiddleware):
    """
    FastAPI/Starlette middleware that logs every /api/ request to audit_log.
    Logging is fire-and-forget (asyncio.create_task) so it never adds latency.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Process the request first — do not delay the response
        response: Response = await call_next(request)

        path = request.url.path

        # Only log API paths; skip health checks and static assets
        if not (path.startswith("/api") or path.startswith("/auth")):
            return response

        # Determine event type from path
        event_type = _event_type_for_path(path)
        if not event_type:
            # Generic access event for unmapped API paths
            event_type = AuditLogger.DOCUMENT_ACCESSED

        actor = _extract_actor(request)
        ip = _get_ip(request)
        status_code = response.status_code
        details: dict = {"method": request.method, "path": path}
        if status_code >= 400:
            details["error"] = status_code

        # Fire-and-forget audit log write to avoid blocking the response
        asyncio.create_task(
            _write_audit_async(event_type, actor, ip, details)
        )

        return response


async def _write_audit_async(
    event_type: str,
    actor: str,
    ip: str,
    details: dict,
) -> None:
    """
    Write an audit log entry in a background task.
    Creates its own DB session to avoid cross-thread session issues.
    """
    try:
        from app.core.db import SessionLocal
        from app.modules.audit.audit_logger import get_audit_logger

        db = SessionLocal()
        try:
            get_audit_logger().log(
                db,
                event_type=event_type,
                actor=actor,
                ip_address=ip,
                details=details,
            )
        finally:
            db.close()
    except Exception as exc:
        # Audit failure must never surface to the user
        logger.debug("Async audit write failed: %s", exc)
