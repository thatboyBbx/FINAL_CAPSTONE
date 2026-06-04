"""
app/modules/clients/router.py
==============================
API routes for the Client Management module.

All routes return JSON (HTML routes live in extra_router.py).
API prefix: /api/clients
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.clients import service as svc
from app.modules.auth.access_control import can_access_client, is_admin, require_client_access
from app.modules.auth.dependencies import get_current_user
from app.modules.users.model import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/clients",
    tags=["clients"],
    dependencies=[Depends(get_current_user)],
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _client_to_dict(c) -> dict:
    """Serialise a Client ORM object to a JSON-compatible dict."""
    return {
        "id":         c.id,
        "name":       c.name,
        "company":    c.company,
        "email":      c.email,
        "phone":      c.phone,
        "address":    c.address,
        "segment":    c.segment,
        "broker_id":  c.broker_id,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _document_to_dict(d) -> dict:
    return {
        "id": d.id,
        "title": d.title,
        "original_filename": d.original_filename,
        "document_category": d.document_category,
        "status": d.status,
        "folder": getattr(d, "folder", None),
        "client_id": getattr(d, "client_id", None),
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


def _policy_to_dict(p) -> dict:
    """Serialise a ClientPolicy ORM object."""
    return {
        "id":            p.id,
        "client_id":     p.client_id,
        "document_id":   p.document_id,
        "policy_number": p.policy_number,
        "insurer_name":  p.insurer_name,
        "policy_type":   p.policy_type,
        "start_date":    p.start_date.isoformat() if p.start_date else None,
        "end_date":      p.end_date.isoformat()   if p.end_date   else None,
        "premium_usd":   p.premium_usd,
        "coverage_usd":  p.coverage_usd,
        "status":        p.status,
        "auto_renew":    p.auto_renew,
    }


def _note_to_dict(n) -> dict:
    """Serialise a ClientNote ORM object."""
    return {
        "id":         n.id,
        "client_id":  n.client_id,
        "author":     n.author,
        "content":    n.content,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


def _interaction_to_dict(i) -> dict:
    """Serialise a ClientInteraction ORM object."""
    return {
        "id":             i.id,
        "client_id":      i.client_id,
        "type":           i.type,
        "summary":        i.summary,
        "date":           i.date.isoformat()           if i.date           else None,
        "follow_up_date": i.follow_up_date.isoformat() if i.follow_up_date else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLIENT ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=None)
def list_clients(
    segment: str | None = Query(None),
    search:  str | None = Query(None),
    limit:   int        = Query(100, ge=1, le=500),
    offset:  int        = Query(0,   ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    clients = svc.list_clients_with_counts(db, segment=segment, search=search, limit=limit, offset=offset)
    if not is_admin(current_user):
        clients = [row for row in clients if can_access_client(current_user, row["client"])]
    return [
        {
            **_client_to_dict(row["client"]),
            "policy_count": row["policy_count"],
            "document_count": row["document_count"],
        }
        for row in clients
    ]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=None)
def create_client(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if not payload.get("name"):
        raise HTTPException(status_code=400, detail="name is required.")
    if not is_admin(current_user):
        payload["broker_id"] = current_user.id
    else:
        payload.setdefault("broker_id", current_user.id)
    client = svc.create_client(db, payload)
    return _client_to_dict(client)


@router.get("/expiry", response_model=None)
def clients_expiry(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    rows = svc.get_expiring_policies(db, days_ahead=days)
    if is_admin(current_user):
        return rows
    return [
        row for row in rows
        if can_access_client(current_user, svc.get_client(db, row["client_id"]))
    ]


@router.get("/renewals", response_model=None)
def clients_renewals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    pipeline = svc.get_renewal_pipeline(db)
    if is_admin(current_user):
        return pipeline
    return {
        key: [
            row for row in rows
            if can_access_client(current_user, svc.get_client(db, row["client_id"]))
        ]
        for key, rows in pipeline.items()
    }


@router.get("/{client_id}", response_model=None)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    c = require_client_access(db, current_user, client_id)
    return _client_to_dict(c)


@router.put("/{client_id}", response_model=None)
def update_client(
    client_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    require_client_access(db, current_user, client_id)
    if not is_admin(current_user):
        payload.pop("broker_id", None)
    c = svc.update_client(db, client_id, payload)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found.")
    return _client_to_dict(c)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    require_client_access(db, current_user, client_id)
    ok = svc.delete_client(db, client_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Client not found.")


# ─────────────────────────────────────────────────────────────────────────────
# POLICY ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{client_id}/policies", response_model=None)
def list_client_policies(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    require_client_access(db, current_user, client_id)
    return [_policy_to_dict(p) for p in svc.list_policies(db, client_id)]


@router.post("/{client_id}/policies", status_code=201, response_model=None)
def add_client_policy(
    client_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    require_client_access(db, current_user, client_id)
    policy = svc.add_policy(db, client_id, payload)
    return _policy_to_dict(policy)


@router.get("/{client_id}/documents", response_model=None)
def list_client_documents(
    client_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    require_client_access(db, current_user, client_id)
    return [
        _document_to_dict(d)
        for d in svc.list_client_documents(db, client_id, offset=offset, limit=limit)
    ]


@router.get("/{client_id}/document-suggestions", response_model=None)
def list_document_suggestions(
    client_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    require_client_access(db, current_user, client_id)
    docs = svc.list_recent_unlinked_documents(db, limit=limit)
    if not is_admin(current_user):
        docs = [d for d in docs if d.uploaded_by_user_id == current_user.id]
    return [_document_to_dict(d) for d in docs]


# ─────────────────────────────────────────────────────────────────────────────
# NOTES ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{client_id}/notes", status_code=201, response_model=None)
def add_client_note(
    client_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    require_client_access(db, current_user, client_id)
    note = svc.add_note(db, client_id, payload)
    return _note_to_dict(note)


# ─────────────────────────────────────────────────────────────────────────────
# INTERACTIONS ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{client_id}/interactions", status_code=201, response_model=None)
def add_client_interaction(
    client_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    require_client_access(db, current_user, client_id)
    interaction = svc.add_interaction(db, client_id, payload)
    return _interaction_to_dict(interaction)
