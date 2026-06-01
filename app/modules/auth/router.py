"""
app/modules/auth/router.py
===========================
Public auth endpoints:
  POST /auth/register          — self-registration (role always "user")
  POST /auth/login             — credential exchange → access + refresh tokens
  POST /auth/refresh           — refresh token → new token pair
  POST /auth/logout            — revoke current session
  GET  /auth/me                — return authenticated user profile

Admin-only endpoints:
  POST /auth/admin/users       — create a user with a specified role

Rate limiting is applied via slowapi (limiter from app.core.rate_limit).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.rate_limit import limiter
from app.modules.audit.audit_logger import get_audit_logger
from app.modules.auth import service as auth_service
from app.modules.auth.dependencies import get_current_user, require_role
from app.modules.auth.schemas import (
    CurrentUserResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from app.modules.auth.token_store import (
    blacklist_jti,
    create_refresh_token,
    revoke_refresh_token,
    verify_refresh_token,
)
from app.modules.users import service as users_service
from app.modules.users.model import User
from app.modules.users.schemas import UserAdminCreate, UserCreate, UserRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_client_ip(request: Request) -> str:
    from app.core.rate_limit import _real_ip
    return _real_ip(request)


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set both auth cookies with uniform, security-appropriate flags."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.access_token_expire_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/auth/refresh",  # Scope the refresh cookie to the refresh endpoint
    )


def _build_token_response(
    user: User,
    access_token: str,
) -> TokenResponse:
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user_id=user.id,
        staff_id=user.staff_id,
        full_name=user.full_name,
        role=user.role,
    )


def _audit_login_success(db: Session, actor: str, ip: str, user_id: int) -> None:
    get_audit_logger().log(
        db,
        event_type="USER_LOGIN",
        actor=actor,
        ip_address=ip,
        details={"user_id": user_id, "outcome": "success"},
    )


def _audit_login_failure(db: Session, attempted_staff_id: str, ip: str, reason: str) -> None:
    get_audit_logger().log(
        db,
        event_type="LOGIN_FAILED",
        actor=attempted_staff_id or "unknown",
        ip_address=ip,
        details={"reason": reason},
    )


# ---------------------------------------------------------------------------
# Self-registration (always creates "user" role)
# ---------------------------------------------------------------------------

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.rate_limit_register)
def register_user(
    request: Request,
    payload: UserCreate,
    db: Session = Depends(get_db),
) -> User:
    """
    Public self-registration.  The caller cannot choose their own role —
    all self-registered accounts are assigned the 'user' role by the service
    layer regardless of what was submitted in the request body.
    """
    try:
        password_hash = auth_service.hash_password(payload.password)
        user = users_service.create_user(db, payload, password_hash=password_hash, role="user")
        get_audit_logger().log(
            db,
            event_type="USER_REGISTERED",
            actor=user.staff_id,
            ip_address=_get_client_ip(request),
            details={"user_id": user.id},
        )
        return user
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.rate_limit_login)
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Exchange credentials for an access token + refresh token.
    Both tokens are also set as HttpOnly cookies for browser clients.
    """
    ip = _get_client_ip(request)

    user = auth_service.authenticate_user(db, payload.staff_id, payload.password)
    if not user:
        _audit_login_failure(db, payload.staff_id, ip, "bad_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid staff ID or password.",
        )

    access_token = auth_service.create_access_token(user)
    refresh_raw = create_refresh_token(db, user.id, settings.refresh_token_expire_days, ip)

    _set_auth_cookies(response, access_token, refresh_raw)
    _audit_login_success(db, user.staff_id, ip, user.id)

    return _build_token_response(user, access_token)


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    # Cookie-based refresh (preferred for browsers)
    refresh_token_cookie: str | None = Cookie(default=None, alias="refresh_token"),
    # Body-based refresh (for non-browser API clients)
    body: RefreshRequest | None = None,
) -> TokenResponse:
    """
    Exchange a valid refresh token for a new access token + refresh token pair.
    The old refresh token is revoked on success (token rotation).
    """
    raw = refresh_token_cookie or (body.refresh_token if body else None)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required.",
        )

    record = verify_refresh_token(db, raw)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or has expired. Please log in again.",
        )

    # Load the user
    from app.modules.users.model import User as UserModel
    user: UserModel | None = db.get(UserModel, record.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or deactivated.",
        )

    # Rotate: revoke old refresh token, issue new pair
    revoke_refresh_token(db, raw)
    new_access = auth_service.create_access_token(user)
    new_refresh = create_refresh_token(
        db, user.id, settings.refresh_token_expire_days, _get_client_ip(request)
    )

    _set_auth_cookies(response, new_access, new_refresh)

    get_audit_logger().log(
        db,
        event_type="TOKEN_REFRESHED",
        actor=user.staff_id,
        ip_address=_get_client_ip(request),
        details={"user_id": user.id},
    )

    return _build_token_response(user, new_access)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    refresh_token_cookie: str | None = Cookie(default=None, alias="refresh_token"),
) -> dict:
    """
    Revoke the current session: blacklist the access token JTI and revoke
    the refresh token.  Clears both cookies.
    """
    ip = _get_client_ip(request)

    # Blacklist the access token JTI
    token_src = access_token_cookie or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if token_src:
        payload = auth_service.decode_access_token(token_src)
        if payload:
            jti = payload.get("jti")
            exp_raw = payload.get("exp")
            if jti and exp_raw:
                try:
                    exp_dt = datetime.fromtimestamp(
                        exp_raw if isinstance(exp_raw, (int, float)) else exp_raw.timestamp(),
                        tz=timezone.utc,
                    )
                    blacklist_jti(db, jti, current_user.id, exp_dt)
                except Exception:
                    pass

    # Revoke refresh token
    if refresh_token_cookie:
        revoke_refresh_token(db, refresh_token_cookie)

    # Clear cookies
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/auth/refresh")

    get_audit_logger().log(
        db,
        event_type="USER_LOGOUT",
        actor=current_user.staff_id,
        ip_address=ip,
        details={"user_id": current_user.id},
    )

    return {"detail": "Logged out successfully."}


# ---------------------------------------------------------------------------
# Current user profile
# ---------------------------------------------------------------------------

@router.get("/me", response_model=CurrentUserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the authenticated user's profile."""
    return current_user


# ---------------------------------------------------------------------------
# Admin: create user with explicit role
# ---------------------------------------------------------------------------

@router.post(
    "/admin/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_user(
    request: Request,
    payload: UserAdminCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
) -> User:
    """
    Admin-only endpoint to create users with a specified role.
    Requires the caller to hold the 'admin' role.
    """
    try:
        password_hash = auth_service.hash_password(payload.password)
        user = users_service.create_user(
            db, payload, password_hash=password_hash, role=payload.role
        )
        get_audit_logger().log(
            db,
            event_type="ADMIN_ACTION",
            actor=admin.staff_id,
            ip_address=_get_client_ip(request),
            details={
                "action": "create_user",
                "target_user_id": user.id,
                "assigned_role": user.role,
            },
        )
        return user
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
