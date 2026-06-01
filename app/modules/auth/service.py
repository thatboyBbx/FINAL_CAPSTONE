"""
app/modules/auth/service.py
============================
Authentication helpers: password hashing, JWT creation and validation.

Token payload schema
--------------------
  sub        str   staff_id (JWT standard subject)
  user_id    int   primary key from users table
  role       str   user role string
  jti        str   UUID4 — unique token ID (used for blacklisting)
  iat        int   issued-at (Unix timestamp UTC)
  exp        int   expiry   (Unix timestamp UTC)

decode_access_token(token) → dict | None
  Stateless decode only.  Used by the audit middleware where we need the
  actor identity but do not need DB access.  Returns None on any JWT error.

verify_access_token(db, token) → (dict | None, str | None)
  Full verification including blacklist check and per-user revocation fence.
  Used by auth dependencies that guard protected routes.
  Returns (payload, None) on success, (None, reason_string) on failure.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.users import service as users_service
from app.modules.users.model import User

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# Pre-computed hash of a throwaway password. Used to flatten the timing
# difference between "user does not exist" and "user exists, wrong password"
# so an attacker cannot enumerate valid staff_ids via response-time analysis.
_DUMMY_PASSWORD_HASH = pwd_context.hash("invalid-placeholder-password")


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def authenticate_user(db: Session, staff_id: str, password: str) -> User | None:
    """
    Constant-time-ish authentication.

    Always runs one password verification regardless of whether the user
    exists, so the response time does not leak existence of a staff_id.
    Also consults the per-staff_id lockout counter — if the account is
    locked, the lookup short-circuits BEFORE checking the password (we still
    burn a hash to keep timing flat).
    """
    from app.modules.auth.lockout import is_locked, record_failure, clear_failures

    user = users_service.get_user_by_staff_id(db, staff_id)
    locked = is_locked(staff_id)

    # Always run verify_password against something so failed-existing and
    # failed-unknown take the same amount of time.
    if user is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None

    password_ok = verify_password(password, user.password_hash)

    if locked or not user.is_active or not password_ok:
        # Only count password failures against the lockout — disabled accounts
        # and locked accounts do not feed the counter further.
        if user.is_active and not locked and not password_ok:
            record_failure(staff_id)
        return None

    clear_failures(staff_id)
    return user


# ---------------------------------------------------------------------------
# Access token
# ---------------------------------------------------------------------------

def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": user.staff_id,
        "user_id": user.id,
        "role": user.role,
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    """
    Stateless JWT decode — no database access.

    Returns the payload dict on success, or None on any error.
    Used by the audit middleware (actor extraction) where DB access is not
    practical.  For route guards, use verify_access_token() instead.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        # Require the claims we always embed
        if not all(k in payload for k in ("sub", "user_id", "jti", "iat")):
            return None
        return payload
    except ExpiredSignatureError:
        return None
    except JWTError as exc:
        logger.debug("JWT decode failed: %s", exc)
        return None


def verify_access_token(db: Session, token: str) -> tuple[dict | None, str | None]:
    """
    Full token verification including blacklist and revocation fence checks.

    Returns:
        (payload, None)        — token is valid
        (None, reason_string)  — token is invalid; reason describes why

    Reason strings are safe to log but should not be returned verbatim
    to HTTP clients (use generic 401 messages externally).
    """
    # --- Step 1: stateless decode ---
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except ExpiredSignatureError:
        return None, "token_expired"
    except JWTError as exc:
        logger.warning("JWT signature/format error: %s", exc)
        return None, "token_invalid"

    # --- Step 2: required claims ---
    if not all(k in payload for k in ("sub", "user_id", "jti", "iat")):
        return None, "token_missing_claims"

    jti: str = payload["jti"]
    user_id: int = payload["user_id"]
    iat: int = payload["iat"]

    # --- Step 3: JTI blacklist (explicit logout) ---
    from app.modules.auth.token_store import is_jti_blacklisted, get_revocation_fence

    if is_jti_blacklisted(db, jti):
        return None, "token_revoked"

    # --- Step 4: per-user revocation fence (password change / force logout) ---
    fence_ts = get_revocation_fence(db, user_id)
    if fence_ts is not None:
        issued_at = datetime.fromtimestamp(iat, tz=timezone.utc)
        if issued_at < fence_ts:
            return None, "token_superseded"

    return payload, None
