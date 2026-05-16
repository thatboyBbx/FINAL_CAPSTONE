"""
SQLAlchemy 2.0 model for Users.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class User(Base):
    """Platform user — staff member of the brokerage."""

    __tablename__ = "users"

    id:            Mapped[int]            = mapped_column(Integer, primary_key=True, index=True)
    staff_id:      Mapped[str]            = mapped_column(String(100), unique=True, nullable=False, index=True)
    email:         Mapped[str | None]     = mapped_column(String(255), unique=True, nullable=True, index=True)
    full_name:     Mapped[str]            = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str]            = mapped_column(String(255), nullable=False)
    role:          Mapped[str]            = mapped_column(String(50), nullable=False, default="user")
    is_active:     Mapped[bool]           = mapped_column(Boolean, nullable=False, default=True)
    created_at:    Mapped[datetime]       = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
