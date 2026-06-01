from sqlalchemy.orm import Session

from app.core.pagination import normalize_pagination
from app.modules.documents.model import Document
from app.modules.documents.schemas import DocumentCreate, DocumentUpdate


def create_document(db: Session, payload: DocumentCreate) -> Document:
    document = Document(
        title=payload.title,
        original_filename=payload.original_filename,
        stored_filename=payload.stored_filename,
        file_path=payload.file_path,
        mime_type=payload.mime_type,
        file_size=payload.file_size,
        status=payload.status,
        document_category=payload.document_category,
        notes=payload.notes,
        uploaded_by_user_id=payload.uploaded_by_user_id,
        client_id=payload.client_id,
        sha256_hash=payload.sha256_hash,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def get_document_by_id(db: Session, document_id: int) -> Document | None:
    return db.query(Document).filter(Document.id == document_id).first()


def get_document_by_stored_filename(db: Session, stored_filename: str) -> Document | None:
    return db.query(Document).filter(Document.stored_filename == stored_filename).first()


def get_document_by_sha256(db: Session, sha256: str) -> Document | None:
    return db.query(Document).filter(Document.sha256_hash == sha256).first()


def list_documents(db: Session, skip: int = 0, limit: int = 100) -> list[Document]:
    skip, limit = normalize_pagination(skip, limit)
    return db.query(Document).order_by(Document.created_at.desc()).offset(skip).limit(limit).all()


def list_documents_by_uploader(
    db: Session,
    uploaded_by_user_id: int,
    skip: int = 0,
    limit: int = 100,
) -> list[Document]:
    skip, limit = normalize_pagination(skip, limit)
    return (
        db.query(Document)
        .filter(Document.uploaded_by_user_id == uploaded_by_user_id)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def list_documents_filtered(
    db: Session,
    status: str | None = None,
    document_category: str | None = None,
    uploaded_by_user_id: int | None = None,
    client_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Document]:
    skip, limit = normalize_pagination(skip, limit)
    query = db.query(Document)

    if status is not None:
        query = query.filter(Document.status == status)

    if document_category is not None:
        query = query.filter(Document.document_category == document_category)

    if uploaded_by_user_id is not None:
        query = query.filter(Document.uploaded_by_user_id == uploaded_by_user_id)

    if client_id is not None:
        query = query.filter(Document.client_id == client_id)

    return query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()


def update_document(db: Session, document: Document, payload: DocumentUpdate) -> Document:
    if payload.title is not None:
        document.title = payload.title

    if payload.status is not None:
        document.status = payload.status

    if payload.document_category is not None:
        document.document_category = payload.document_category

    if payload.notes is not None:
        document.notes = payload.notes

    db.commit()
    db.refresh(document)
    return document


def delete_document(db: Session, document: Document) -> None:
    db.delete(document)
    db.commit()
