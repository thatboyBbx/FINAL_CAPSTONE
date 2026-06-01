"""
AuditMiddleware — automatically logs every API/auth request as an audit event.
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

# Map URL path prefixes → event type constants (longest match wins)
_PATH_EVENT_MAP: dict[str, str] = {
    "/api/documents":         AuditLogger.DOCUMENT_UPLOADED,
    "/api/qa/ask":            AuditLogger.QA_QUESTION_ASKED,
    "/api/comparison":        AuditLogger.COMPARISON_RUN,
    "/api/feedback/trigger":  AuditLogger.RETRAINING_TRIGGERED,
    "/api/feedback":          AuditLogger.FEEDBACK_SUBMITTED,
    "/api/batch":             AuditLogger.BATCH_UPLOADED,
    "/api/tracker":           AuditLogger.POLICY_ALERT_SENT,
    "/api/audit":             AuditLogger.ADMIN_ACTION,
    "/api/admin/jobs":        AuditLogger.ADMIN_ACTION,
    "/auth/login":            AuditLogger.USER_LOGIN,
    "/auth/logout":           AuditLogger.USER_LOGOUT,
    "/auth/refresh":          AuditLogger.TOKEN_REFRESHED,
    "/auth/register":         AuditLogger.USER_REGISTERED,
    "/auth/admin":            AuditLogger.ADMIN_ACTION,
}


def _event_type_for_path(path: str, status_code: int) -> str:
    """
    Return the most specific event type for a request path.
    Failed login attempts get a distinct event type regardless of path match.
    """
    # 401 on the login endpoint is always a LOGIN_FAILED event
    if path.startswith("/auth/login") and status_code == 401:
        return AuditLogger.LOGIN_FAILED

    matched_prefix = ""
    matched_event: str | None = None
    for prefix, event in _PATH_EVENT_MAP.items():
        if path.startswith(prefix) and len(prefix) > len(matched_prefix):
            matched_prefix = prefix
            matched_event = event

    return matched_event or AuditLogger.DOCUMENT_ACCESSED


def _extract_actor(request: Request) -> str:
    """
    Extract the actor identifier from the request.
    Tries the Authorization Bearer token first, then cookie, then 'anonymous'.
    Only does a stateless decode — no DB access here.
    """
    actor = "anonymous"
    token: str | None = None

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    if not token:
        token = request.cookies.get("access_token")

    if token:
        try:
            from app.modules.auth.service import decode_access_token
            payload = decode_access_token(token)
            if payload:
                actor = str(payload.get("sub") or payload.get("user_id") or "unknown")
        except Exception:
            pass

    return actor


def _get_ip(request: Request) -> str:
    """
    Return the client IP.  X-Forwarded-For is only trusted when the direct
    client is a configured trusted proxy — prevents IP spoofing in audit logs.
    """
    from app.core.config import settings

    client_ip: str = request.client.host if request.client else ""
    trusted = {ip.strip() for ip in settings.trusted_proxy_ips.split(",") if ip.strip()}

    if client_ip in trusted:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()

    return client_ip


class AuditMiddleware(BaseHTTPMiddleware):
    """
    FastAPI/Starlette middleware that logs every /api/ and /auth/ request
    to the audit_log table.  Logging is fire-and-forget (asyncio.create_task)
    so it never adds latency to responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)

        path = request.url.path

        if not (path.startswith("/api") or path.startswith("/auth")):
            return response

        status_code = response.status_code
        event_type = _event_type_for_path(path, status_code)
        actor = _extract_actor(request)
        ip = _get_ip(request)

        details: dict = {"method": request.method, "path": path, "status": status_code}
        if status_code >= 400:
            details["error"] = status_code

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
    try:
        from app.core.db import session_scope
        from app.modules.audit.audit_logger import get_audit_logger

        with session_scope() as db:
            get_audit_logger().log(
                db,
                event_type=event_type,
                actor=actor,
                ip_address=ip,
                details=details,
            )
    except Exception as exc:
        logger.debug("Async audit write failed: %s", exc)
