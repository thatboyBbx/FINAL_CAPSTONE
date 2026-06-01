"""
app/modules/clients/service.py
================================
Business logic layer for the clients module. Thin wrapper over repo.py.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.pagination import normalize_pagination
from app.modules.clients import repo
from app.modules.clients.model import Client, ClientInteraction, ClientNote, ClientPolicy


def create_client(db: Session, data: dict) -> Client:
    return repo.create(db, data)


def get_client(db: Session, client_id: int) -> Client | None:
    return repo.get_by_id(db, client_id)


def list_clients(
    db: Session,
    segment: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Client]:
    offset, limit = normalize_pagination(offset, limit)
    return repo.get_all(db, segment=segment, search=search, limit=limit, offset=offset)


def list_clients_with_counts(
    db: Session,
    segment: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    offset, limit = normalize_pagination(offset, limit)
    clients = repo.get_all(db, segment=segment, search=search, limit=limit, offset=offset)
    if not clients:
        return []

    client_ids = [c.id for c in clients]
    policy_counts   = repo.get_policy_counts(db, client_ids)
    document_counts = repo.get_document_counts(db, client_ids)

    return [
        {
            "client":         client,
            "policy_count":   policy_counts.get(client.id, 0),
            "document_count": document_counts.get(client.id, 0),
        }
        for client in clients
    ]


def update_client(db: Session, client_id: int, data: dict) -> Client | None:
    return repo.update(db, client_id, data)


def delete_client(db: Session, client_id: int) -> bool:
    return repo.delete(db, client_id)


def add_policy(db: Session, client_id: int, data: dict) -> ClientPolicy:
    return repo.add_policy(db, client_id, data)


def list_policies(db: Session, client_id: int) -> list[ClientPolicy]:
    return repo.get_policies(db, client_id)


def list_client_documents(
    db: Session,
    client_id: int,
    offset: int = 0,
    limit: int = 100,
):
    offset, limit = normalize_pagination(offset, limit)
    return repo.get_client_documents(db, client_id, offset=offset, limit=limit)


def list_recent_unlinked_documents(db: Session, limit: int = 10):
    return repo.get_unlinked_documents(db, limit=limit)


def get_expiring_policies(db: Session, days_ahead: int = 30) -> list[dict[str, Any]]:
    rows = repo.get_expiring_policies(db, days_ahead=days_ahead)
    today = date.today()
    result = []
    for policy, client in rows:
        days_left = (policy.end_date - today).days if policy.end_date else None
        result.append({
            "policy_id":      policy.id,
            "policy_number":  policy.policy_number,
            "policy_type":    policy.policy_type,
            "insurer_name":   policy.insurer_name,
            "end_date":       policy.end_date.isoformat() if policy.end_date else None,
            "days_left":      days_left,
            "premium_usd":    policy.premium_usd,
            "auto_renew":     policy.auto_renew,
            "client_id":      client.id,
            "client_name":    client.name,
            "client_company": client.company,
        })
    return result


def get_renewal_pipeline(db: Session) -> dict[str, list[dict]]:
    rows = repo.get_renewal_pipeline_policies(db)
    pending: list[dict] = []
    in_progress: list[dict] = []
    renewed: list[dict] = []

    for policy, client in rows:
        card = {
            "policy_id":     policy.id,
            "policy_number": policy.policy_number,
            "policy_type":   policy.policy_type,
            "insurer_name":  policy.insurer_name,
            "end_date":      policy.end_date.isoformat() if policy.end_date else None,
            "premium_usd":   policy.premium_usd,
            "client_id":     client.id,
            "client_name":   client.name,
        }
        if policy.status == "renewed":
            renewed.append(card)
        elif policy.auto_renew:
            in_progress.append(card)
        else:
            pending.append(card)

    return {"pending": pending, "in_progress": in_progress, "renewed": renewed}


def add_note(db: Session, client_id: int, data: dict) -> ClientNote:
    return repo.add_note(db, client_id, data)


def add_interaction(db: Session, client_id: int, data: dict) -> ClientInteraction:
    return repo.add_interaction(db, client_id, data)
