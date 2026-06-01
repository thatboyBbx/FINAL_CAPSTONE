"""
app/modules/auth/dependencies.py
==================================
JWT authentication dependency for FastAPI API routes.

This is for JSON API endpoints — it returns HTTP 401/403 on failure.
For HTML page routes (browser redirects), see ui_dependencies.py.

Usage:
    from app.modules.auth.dependencies import get_current_user, require_role

    # Protect an entire router:
    router = APIRouter(dependencies=[Depends(get_current_user)])

    # Protect a single endpoint:
    @router.get("/me")
    def get_me(user: User = Depends(get_current_user)):
        return user

    # Role-based access:
    @router.delete("/admin-action")
    def admin_action(user: User = Depends(require_role("admin"))):
        ...
"""
from __future__ import annotations

import logging
from typing import Callable

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.audit.audit_logger import AuditLogger, get_audit_logger
from app.modules.auth.service import verify_access_token
from app.modules.users.model import User

logger = logging.getLogger(__name__)

# auto_error=False so we can fall back to cookie when header is absent
_bearer = HTTPBearer(auto_error=False)


def _extract_raw_token(
    credentials: HTTPAuthorizationCredentials | None,
    access_token: str | None,
) -> str | None:
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    if access_token:
        return access_token
    return None


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """
    Validate the JWT (including blacklist and revocation-fence checks) and
    return the authenticated User.

    Sources checked in order: Authorization header, then access_token cookie.

    Raises:
        HTTP 401 — missing token, expired token, invalid or revoked token,
                   user not found
        HTTP 403 — user account is deactivated
    """
    token = _extract_raw_token(credentials, access_token)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload, reason = verify_access_token(db, token)

    if payload is None:
        # Log security-relevant failure reasons internally; return generic message to caller
        if reason in ("token_invalid", "token_missing_claims"):
            logger.warning(
                "Rejected token from %s — reason: %s",
                request.client.host if request.client else "?",
                reason,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: int | None = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token.",
        )

    user: User | None = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Contact your administrator.",
        )

    return user


def require_role(*allowed_roles: str) -> Callable[..., User]:
    """
    Return a dependency that enforces role membership.

    Logs a PERMISSION_DENIED audit event when access is denied so that
    privilege-escalation attempts are visible in the audit trail.

    Example:
        @router.post("/approve")
        def approve(user: User = Depends(require_role("admin", "manager"))):
            ...
    """
    def _check(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if current_user.role not in allowed_roles:
            # Audit the denied access attempt
            try:
                get_audit_logger().log(
                    db,
                    event_type=AuditLogger.PERMISSION_DENIED,
                    actor=current_user.staff_id,
                    ip_address=(
                        request.client.host if request.client else None
                    ),
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
                detail=(
                    f"Access denied. Required role: {' or '.join(allowed_roles)}."
                ),
            )
        return current_user

    return _check
