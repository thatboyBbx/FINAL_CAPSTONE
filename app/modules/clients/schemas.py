"""
app/modules/clients/schemas.py
================================
Pydantic v2 schemas for the clients module.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClientBase(BaseModel):
    name:      str
    company:   str | None = None
    email:     str | None = None
    phone:     str | None = None
    address:   str | None = None
    broker_id: int | None = None
    segment:   str = "retail"


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name:      str | None = None
    company:   str | None = None
    email:     str | None = None
    phone:     str | None = None
    address:   str | None = None
    broker_id: int | None = None
    segment:   str | None = None


class ClientRead(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id:         int
    created_at: datetime
    updated_at: datetime
