"""
app/modules/auth/token_store.py
================================
ORM models and helper functions for:
  - Refresh token lifecycle (issue, verify, rotate, revoke)
  - Access token blacklist (explicit logout / password-change revocation)
  - Per-user revocation fence (tokens_valid_after — mass-revoke on pw change)

Design notes
------------
- Refresh tokens are stored as SHA-256 hashes; the raw value is only held in
  the cookie and never persisted, so a DB breach does not leak usable tokens.
- Access token JTIs are blacklisted individually on logout.  Because tokens are
  short-lived (30 min) the blacklist stays small; stale entries can be purged
  once their `expires_at` has passed.
- `UserRevocationFence` lets an admin force-expire ALL tokens for a user (e.g.
  after a password change) without enumerating every outstanding JTI.  The iat
  claim added to every access token is compared against `tokens_valid_after`.
"""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------

class RefreshToken(Base):
    """One row per issued refresh token (stored as a hash)."""

    __tablename__ = "refresh_tokens"

    id:          Mapped[int]          = mapped_column(Integer, primary_key=True)
    token_hash:  Mapped[str]          = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id:     Mapped[int]          = mapped_column(Integer, nullable=False, index=True)
    ip_address:  Mapped[str | None]   = mapped_column(String(45), nullable=True)
    issued_at:   Mapped[datetime]     = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    expires_at:  Mapped[datetime]     = mapped_column(DateTime, nullable=False, index=True)
    revoked:     Mapped[bool]         = mapped_column(Boolean, nullable=False, default=False)
    revoked_at:  Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_refresh_user_active", "user_id", "revoked"),
    )


class AccessTokenBlacklist(Base):
    """Blacklisted access token JTIs.  Entries may be purged after expires_at."""

    __tablename__ = "access_token_blacklist"

    id:              Mapped[int]      = mapped_column(Integer, primary_key=True)
    jti:             Mapped[str]      = mapped_column(String(36), unique=True, nullable=False, index=True)
    user_id:         Mapped[int]      = mapped_column(Integer, nullable=False, index=True)
    blacklisted_at:  Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    expires_at:      Mapped[datetime] = mapped_column(DateTime, nullable=False)


class UserRevocationFence(Base):
    """
    Per-user 'tokens issued before this timestamp are invalid'.
    Updated on password change or admin force-logout.
    """

    __tablename__ = "user_revocation_fence"

    user_id:           Mapped[int]      = mapped_column(Integer, primary_key=True)
    tokens_valid_after: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Refresh token API
# ---------------------------------------------------------------------------

def create_refresh_token(
    db: Session,
    user_id: int,
    expires_days: int,
    ip_address: str | None = None,
) -> str:
    """
    Generate a cryptographically random refresh token, persist its hash,
    and return the raw token string (stored only in the caller's cookie).
    """
    raw = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

    record = RefreshToken(
        token_hash=_hash(raw),
        user_id=user_id,
        ip_address=ip_address,
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()
    return raw


def verify_refresh_token(db: Session, raw: str) -> RefreshToken | None:
    """
    Return the RefreshToken ORM record if the token is valid (not revoked,
    not expired).  Returns None if the token is unknown or invalid.
    """
    record: RefreshToken | None = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == _hash(raw),
            RefreshToken.revoked == False,       # noqa: E712
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    return record


def revoke_refresh_token(db: Session, raw: str) -> bool:
    """
    Revoke a single refresh token by its raw value.
    Returns True if the token was found and revoked, False otherwise.
    """
    record: RefreshToken | None = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == _hash(raw))
        .first()
    )
    if not record or record.revoked:
        return False
    record.revoked = True
    record.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return True


def revoke_all_refresh_tokens(db: Session, user_id: int) -> int:
    """
    Revoke every active refresh token for a user (e.g. after password change).
    Returns the number of tokens revoked.
    """
    now = datetime.now(timezone.utc)
    records = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.revoked == False)  # noqa: E712
        .all()
    )
    for r in records:
        r.revoked = True
        r.revoked_at = now
    db.commit()
    return len(records)


# ---------------------------------------------------------------------------
# Access token blacklist API
# ---------------------------------------------------------------------------

def blacklist_jti(
    db: Session,
    jti: str,
    user_id: int,
    token_exp: datetime,
) -> None:
    """Add an access token's JTI to the blacklist (used on explicit logout)."""
    existing = db.query(AccessTokenBlacklist).filter(AccessTokenBlacklist.jti == jti).first()
    if existing:
        return
    entry = AccessTokenBlacklist(jti=jti, user_id=user_id, expires_at=token_exp)
    db.add(entry)
    db.commit()
    invalidate_jti_cache(jti)


# ── JTI blacklist TTL cache ────────────────────────────────────────────────
# Every authenticated request consults the blacklist. Without a cache that's
# one DB hit per request — under load, this multiplies pressure on a database
# we already need to keep cool. Blacklist additions are rare (logout / password
# change) so eventual consistency within JTI_BLACKLIST_CACHE_TTL_SECONDS is
# acceptable: a logged-out token will be honoured for at most that long.

_jti_cache_lock = threading.Lock()
# jti -> (is_blacklisted, fetched_at_monotonic)
_jti_cache: Dict[str, tuple[bool, float]] = {}


def _jti_cache_get(jti: str, ttl: int) -> bool | None:
    if ttl <= 0:
        return None
    with _jti_cache_lock:
        entry = _jti_cache.get(jti)
        if entry is None:
            return None
        value, fetched_at = entry
        if (time.monotonic() - fetched_at) > ttl:
            _jti_cache.pop(jti, None)
            return None
        return value


def _jti_cache_put(jti: str, value: bool) -> None:
    with _jti_cache_lock:
        _jti_cache[jti] = (value, time.monotonic())
        # Cheap bound to keep memory in check on long-running processes.
        if len(_jti_cache) > 5000:
            # Drop ~10% of the oldest entries
            oldest = sorted(_jti_cache.items(), key=lambda kv: kv[1][1])[:500]
            for k, _ in oldest:
                _jti_cache.pop(k, None)


def invalidate_jti_cache(jti: str | None = None) -> None:
    """Clear one or all cached JTI lookups. Called after blacklist mutations."""
    with _jti_cache_lock:
        if jti is None:
            _jti_cache.clear()
        else:
            _jti_cache.pop(jti, None)


def is_jti_blacklisted(db: Session, jti: str) -> bool:
    """Return True if the JTI has been explicitly revoked and the entry is unexpired."""
    from app.core.config import settings

    ttl = getattr(settings, "jti_blacklist_cache_ttl_seconds", 0)
    cached = _jti_cache_get(jti, ttl)
    if cached is not None:
        return cached

    result = (
        db.query(AccessTokenBlacklist)
        .filter(
            AccessTokenBlacklist.jti == jti,
            AccessTokenBlacklist.expires_at > datetime.now(timezone.utc),
        )
        .first()
    ) is not None
    _jti_cache_put(jti, result)
    return result


# ---------------------------------------------------------------------------
# Per-user revocation fence API
# ---------------------------------------------------------------------------

def set_revocation_fence(db: Session, user_id: int) -> None:
    """
    Mark all tokens issued before *now* as invalid for this user.
    Called on password change or admin force-logout.
    Also revokes all outstanding refresh tokens.
    """
    now = datetime.now(timezone.utc)
    fence = db.get(UserRevocationFence, user_id)
    if fence:
        fence.tokens_valid_after = now
    else:
        db.add(UserRevocationFence(user_id=user_id, tokens_valid_after=now))
    revoke_all_refresh_tokens(db, user_id)
    db.commit()


def get_revocation_fence(db: Session, user_id: int) -> datetime | None:
    """
    Return the tokens_valid_after timestamp for a user, or None if no fence is set.
    Access tokens with iat < this value must be rejected.
    """
    fence = db.get(UserRevocationFence, user_id)
    return fence.tokens_valid_after if fence else None
