"""
app/modules/clients/repo.py
============================
Database query (repository) layer for the clients module.
All DB queries live here; service.py contains business logic.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.pagination import normalize_pagination
from app.modules.clients.model import Client, ClientAlert, ClientInteraction, ClientNote, ClientPolicy
from app.modules.documents.model import Document


def get_by_id(db: Session, client_id: int) -> Client | None:
    return db.query(Client).filter(Client.id == client_id).first()


def get_all(
    db: Session,
    segment: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Client]:
    offset, limit = normalize_pagination(offset, limit)
    q = db.query(Client)
    if segment:
        q = q.filter(Client.segment == segment)
    if search:
        pattern = f"%{search}%"
        q = q.filter(Client.name.ilike(pattern) | Client.company.ilike(pattern))
    return q.order_by(Client.name).offset(offset).limit(limit).all()


def create(db: Session, data: dict) -> Client:
    client = Client(**{k: v for k, v in data.items() if hasattr(Client, k)})
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def update(db: Session, client_id: int, data: dict) -> Client | None:
    client = get_by_id(db, client_id)
    if not client:
        return None
    for key, val in data.items():
        if hasattr(Client, key):
            setattr(client, key, val)
    db.commit()
    db.refresh(client)
    return client


def delete(db: Session, client_id: int) -> bool:
    client = get_by_id(db, client_id)
    if not client:
        return False
    db.query(ClientAlert).filter(ClientAlert.client_id == client_id).delete()
    db.query(ClientInteraction).filter(ClientInteraction.client_id == client_id).delete()
    db.query(ClientNote).filter(ClientNote.client_id == client_id).delete()
    db.query(ClientPolicy).filter(ClientPolicy.client_id == client_id).delete()
    db.delete(client)
    db.commit()
    return True


def get_policy_counts(db: Session, client_ids: list[int]) -> dict[int, int]:
    return {
        cid: cnt
        for cid, cnt in (
            db.query(ClientPolicy.client_id, func.count(ClientPolicy.id))
            .filter(ClientPolicy.client_id.in_(client_ids))
            .group_by(ClientPolicy.client_id)
            .all()
        )
    }


def get_document_counts(db: Session, client_ids: list[int]) -> dict[int, int]:
    return {
        cid: cnt
        for cid, cnt in (
            db.query(Document.client_id, func.count(Document.id))
            .filter(Document.client_id.in_(client_ids))
            .group_by(Document.client_id)
            .all()
        )
    }


def get_policies(db: Session, client_id: int) -> list[ClientPolicy]:
    return (
        db.query(ClientPolicy)
        .filter(ClientPolicy.client_id == client_id)
        .order_by(ClientPolicy.end_date.is_(None), ClientPolicy.end_date, ClientPolicy.id.desc())
        .all()
    )


def get_policy_by_document(db: Session, document_id: int) -> ClientPolicy | None:
    return db.query(ClientPolicy).filter(ClientPolicy.document_id == document_id).first()


def ensure_policy_for_document(db: Session, document: Document) -> ClientPolicy | None:
    if document.client_id is None:
        return None

    policy = get_policy_by_document(db, document.id)
    if policy:
        policy.client_id = document.client_id
        if not policy.policy_type:
            policy.policy_type = (document.document_category or "policy_document").replace("_", " ")
        if not policy.policy_number:
            policy.policy_number = document.title or document.original_filename or f"Document #{document.id}"
        db.commit()
        db.refresh(policy)
        return policy

    policy = ClientPolicy(
        client_id=document.client_id,
        document_id=document.id,
        policy_number=document.title or document.original_filename or f"Document #{document.id}",
        policy_type=(document.document_category or "policy_document").replace("_", " "),
        insurer_name=None,
        status="active" if document.status != "archived" else "archived",
        auto_renew=False,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def sync_document_policies_for_client(db: Session, client_id: int) -> None:
    documents = (
        db.query(Document)
        .filter(Document.client_id == client_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    for document in documents:
        ensure_policy_for_document(db, document)


def unlink_policy_for_document(db: Session, document_id: int) -> None:
    policy = get_policy_by_document(db, document_id)
    if policy:
        db.delete(policy)
        db.commit()


def add_policy(db: Session, client_id: int, data: dict) -> ClientPolicy:
    policy = ClientPolicy(
        client_id=client_id,
        **{k: v for k, v in data.items() if hasattr(ClientPolicy, k) and k != "client_id"},
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def get_client_documents(
    db: Session,
    client_id: int,
    offset: int = 0,
    limit: int = 100,
) -> list[Document]:
    offset, limit = normalize_pagination(offset, limit)
    return (
        db.query(Document)
        .filter(Document.client_id == client_id)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_unlinked_documents(db: Session, limit: int = 10) -> list[Document]:
    _, limit = normalize_pagination(0, limit, max_limit=50)
    return (
        db.query(Document)
        .filter(Document.client_id.is_(None))
        .order_by(Document.created_at.desc())
        .limit(limit)
        .all()
    )


def get_expiring_policies(db: Session, days_ahead: int = 30) -> list[tuple[ClientPolicy, Client]]:
    today  = date.today()
    cutoff = today + timedelta(days=days_ahead)
    return (
        db.query(ClientPolicy, Client)
        .join(Client, ClientPolicy.client_id == Client.id)
        .filter(
            ClientPolicy.end_date >= today,
            ClientPolicy.end_date <= cutoff,
            ClientPolicy.status == "active",
        )
        .order_by(ClientPolicy.end_date)
        .all()
    )


def get_renewal_pipeline_policies(db: Session) -> list[tuple[ClientPolicy, Client]]:
    today  = date.today()
    cutoff = today + timedelta(days=90)
    return (
        db.query(ClientPolicy, Client)
        .join(Client, ClientPolicy.client_id == Client.id)
        .filter(
            ClientPolicy.status.in_(["active", "renewed"]),
            ClientPolicy.end_date >= today,
            ClientPolicy.end_date <= cutoff,
        )
        .all()
    )


def add_note(db: Session, client_id: int, data: dict) -> ClientNote:
    note = ClientNote(
        client_id=client_id,
        **{k: v for k, v in data.items() if hasattr(ClientNote, k) and k != "client_id"},
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def add_interaction(db: Session, client_id: int, data: dict) -> ClientInteraction:
    interaction = ClientInteraction(
        client_id=client_id,
        **{k: v for k, v in data.items() if hasattr(ClientInteraction, k) and k != "client_id"},
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return interaction
