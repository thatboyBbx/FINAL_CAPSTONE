"""
app/modules/clients/model.py
============================
Client SQLAlchemy models — canonical location (moved from app/models/client.py).

Tables:
  clients             — Core client record
  client_policies     — Insurance policies linked to clients
  client_notes        — Internal broker notes
  client_interactions — Meeting/call/email log
  client_alerts       — Expiry and follow-up alerts
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.db import Base


class Client(Base):
    """Core client record for an insurance brokerage client."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    name:     Mapped[str]        = mapped_column(String(200), nullable=False, index=True)
    company:  Mapped[str | None] = mapped_column(String(200), nullable=True)

    email:   Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone:   Mapped[str | None] = mapped_column(String(50),  nullable=True)
    address: Mapped[str | None] = mapped_column(Text,        nullable=True)

    broker_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    segment:   Mapped[str]        = mapped_column(String(50), default="retail", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )


class ClientPolicy(Base):
    """Insurance policy linked to a client."""

    __tablename__ = "client_policies"

    id:          Mapped[int]      = mapped_column(Integer, primary_key=True, index=True)
    client_id:   Mapped[int]      = mapped_column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    document_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=True, index=True
    )

    policy_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    insurer_name:  Mapped[str | None] = mapped_column(String(200), nullable=True)
    policy_type:   Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_date:    Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date:      Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    premium_usd:   Mapped[float | None] = mapped_column(Float, nullable=True)
    coverage_usd:  Mapped[float | None] = mapped_column(Float, nullable=True)

    status:     Mapped[str]  = mapped_column(String(50), default="active",  nullable=False, index=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean,    default=False,     nullable=False)


class ClientNote(Base):
    """Internal broker note attached to a client record."""

    __tablename__ = "client_notes"

    id:        Mapped[int]        = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int]        = mapped_column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    author:    Mapped[str | None] = mapped_column(String(200), nullable=True)
    content:   Mapped[str]        = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime]  = mapped_column(DateTime, nullable=False, default=func.now())


class ClientInteraction(Base):
    """Log of a meeting, call, email, or other interaction with a client."""

    __tablename__ = "client_interactions"

    id:             Mapped[int]        = mapped_column(Integer, primary_key=True, index=True)
    client_id:      Mapped[int]        = mapped_column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    type:           Mapped[str | None] = mapped_column(String(100), nullable=True)
    summary:        Mapped[str | None] = mapped_column(Text, nullable=True)
    date:           Mapped[date | None] = mapped_column(Date, nullable=True)
    follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class ClientAlert(Base):
    """System-generated or manual alert for a client (e.g. policy expiry)."""

    __tablename__ = "client_alerts"

    id:         Mapped[int]        = mapped_column(Integer, primary_key=True, index=True)
    client_id:  Mapped[int]        = mapped_column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    alert_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message:    Mapped[str | None] = mapped_column(Text,        nullable=True)
    due_date:   Mapped[date | None] = mapped_column(Date,       nullable=True, index=True)
    resolved:   Mapped[bool]        = mapped_column(Boolean, default=False, nullable=False)
