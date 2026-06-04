"""
app/modules/auth/ui_dependencies.py
=====================================
Auth dependency for Jinja2 HTML page routes.

Returns a redirect to /login when the session is missing, invalid, revoked,
or expired.  This is DIFFERENT from the API dependency (dependencies.py)
which returns 401 JSON.

Usage in any UI route:
    from app.modules.auth.ui_dependencies import require_ui_login
    from fastapi.responses import RedirectResponse

    @router.get("/some-page")
    def some_page(
        request: Request,
        current_user=Depends(require_ui_login),
    ):
        if isinstance(current_user, RedirectResponse):
            return current_user
        return templates.TemplateResponse(
            "page.html",
            {"request": request, "user": current_user},
        )
"""
from __future__ import annotations

import logging
from typing import Callable

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.audit.audit_logger import AuditLogger, get_audit_logger
from app.modules.auth.service import verify_access_token
from app.modules.users.model import User

logger = logging.getLogger(__name__)


def require_ui_login(
    request: Request,
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User | RedirectResponse:
    """
    Check the session cookie for browser page requests.

    Returns:
        User object if the session is valid.
        RedirectResponse to /login if the session is missing, invalid,
        expired, or revoked.

    The redirect includes ?next=<original path> so after login the user
    returns to where they were trying to go.
    """
    if not access_token:
        return RedirectResponse(
            url=f"/login?next={request.url.path}",
            status_code=302,
        )

    payload, reason = verify_access_token(db, access_token)

    if payload is None:
        if reason in ("token_invalid", "token_missing_claims"):
            logger.warning(
                "UI session rejected for %s — reason: %s",
                request.client.host if request.client else "?",
                reason,
            )
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("access_token")
        return response

    user_id: int | None = payload.get("user_id")
    if user_id is None:
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("access_token")
        return response

    user: User | None = db.get(User, user_id)
    if user is None or not user.is_active:
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("access_token")
        return response

    return user


def require_ui_role(*allowed_roles: str) -> Callable[..., User | RedirectResponse]:
    """
    HTML-page role guard. Unauthenticated users are redirected to login; logged
    in users without the required role receive the standard 403 page.
    """
    def _check(
        request: Request,
        current_user: User | RedirectResponse = Depends(require_ui_login),
        db: Session = Depends(get_db),
    ) -> User | RedirectResponse:
        if isinstance(current_user, RedirectResponse):
            return current_user

        if current_user.role not in allowed_roles:
            try:
                get_audit_logger().log(
                    db,
                    event_type=AuditLogger.PERMISSION_DENIED,
                    actor=current_user.staff_id,
                    ip_address=request.client.host if request.client else None,
                    details={
                        "required_roles": list(allowed_roles),
                        "user_role": current_user.role,
                        "path": request.url.path,
                    },
                )
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {' or '.join(allowed_roles)}.",
            )

        return current_user

    return _check
