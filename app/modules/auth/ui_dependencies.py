"""
app/modules/auth/ui_dependencies.py
=====================================
Auth dependency for Jinja2 HTML page routes.

Returns a redirect to /login when the session is missing or invalid.
This is DIFFERENT from the API dependency (dependencies.py) which returns 401 JSON.

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

from fastapi import Cookie, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.service import decode_access_token
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
        RedirectResponse to /login if the session is missing or invalid.

    The redirect includes ?next=<original path> so after login the user
    returns to where they were trying to go.
    """
    if not access_token:
        return RedirectResponse(
            url=f"/login?next={request.url.path}",
            status_code=302,
        )

    payload = decode_access_token(access_token)
    if payload is None:
        # Expired or tampered token — clear cookie and redirect
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
