from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.clients.model import Client
from app.modules.documents.model import Document
from app.modules.users.model import User


def is_admin(user: User) -> bool:
    return user.role == "admin"


def can_access_client(user: User, client: Client | None) -> bool:
    if client is None:
        return False
    if is_admin(user):
        return True
    return client.broker_id == user.id


def can_access_document(db: Session, user: User, document: Document | None) -> bool:
    if document is None:
        return False
    if is_admin(user):
        return True
    if document.uploaded_by_user_id == user.id:
        return True
    if document.client_id is None:
        return False
    client = db.get(Client, document.client_id)
    return can_access_client(user, client)


def require_client_access(db: Session, user: User, client_id: int) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")
    if not can_access_client(user, client):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client access denied.")
    return client


def require_document_access(db: Session, user: User, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if not can_access_document(db, user, document):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Document access denied.")
    return document
