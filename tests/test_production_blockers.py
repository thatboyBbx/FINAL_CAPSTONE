import asyncio
import uuid
from datetime import datetime, timezone

from app.modules.auth import service as auth_service
from app.modules.clients.model import Client
from app.modules.documents.model import Document
from app.modules.users import service as users_service
from app.modules.users.schemas import UserCreate


def _user(db, role: str = "user"):
    suffix = uuid.uuid4().hex[:10]
    payload = UserCreate(
        staff_id=f"{role.upper()}_{suffix}",
        email=f"{role}_{suffix}@example.com",
        full_name=f"{role.title()} User",
        password="TestPassword123!",
    )
    return users_service.create_user(
        db,
        payload,
        password_hash=auth_service.hash_password(payload.password),
        role=role,
    )


def _headers(user):
    return {"Authorization": f"Bearer {auth_service.create_access_token(user)}"}


def _document(db, owner_id: int, client_id: int | None = None) -> Document:
    suffix = uuid.uuid4().hex
    doc = Document(
        title=f"Policy {suffix}",
        original_filename=f"policy-{suffix}.pdf",
        stored_filename=f"stored-{suffix}.pdf",
        file_path=f"storage/uploads/stored-{suffix}.pdf",
        mime_type="application/pdf",
        file_size=128,
        status="uploaded",
        uploaded_by_user_id=owner_id,
        client_id=client_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def test_document_object_authorization_denies_other_user(client, db):
    owner = _user(db)
    other = _user(db)
    doc = _document(db, owner.id)

    response = client.get(f"/api/documents/{doc.id}", headers=_headers(other))

    assert response.status_code == 403


def test_admin_can_access_other_users_document(client, db):
    owner = _user(db)
    admin = _user(db, role="admin")
    doc = _document(db, owner.id)

    response = client.get(f"/api/documents/{doc.id}", headers=_headers(admin))

    assert response.status_code == 200
    assert response.json()["id"] == doc.id


def test_unowned_legacy_client_is_admin_only(client, db):
    user = _user(db)
    admin = _user(db, role="admin")
    client_record = Client(name="Legacy Client", broker_id=None)
    db.add(client_record)
    db.commit()
    db.refresh(client_record)

    user_response = client.get(f"/api/clients/{client_record.id}", headers=_headers(user))
    admin_response = client.get(f"/api/clients/{client_record.id}", headers=_headers(admin))

    assert user_response.status_code == 403
    assert admin_response.status_code == 200


def test_create_document_ignores_submitted_owner(client, db):
    user = _user(db)
    other = _user(db)
    suffix = uuid.uuid4().hex

    response = client.post(
        "/api/documents",
        headers=_headers(user),
        json={
            "title": "Submitted Owner Should Be Ignored",
            "original_filename": f"{suffix}.pdf",
            "stored_filename": f"{suffix}.pdf",
            "file_path": f"storage/uploads/{suffix}.pdf",
            "mime_type": "application/pdf",
            "file_size": 128,
            "status": "uploaded",
            "uploaded_by_user_id": other.id,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["uploaded_by_user_id"] == user.id


def test_csp_force_refresh_requires_admin(client, db):
    user = _user(db)

    response = client.post("/internal/csp/force-refresh", headers=_headers(user))

    assert response.status_code == 403


def test_lifespan_skips_create_all_when_disabled(monkeypatch):
    from app import main

    called = False

    def fake_create_all(*args, **kwargs):
        nonlocal called
        called = True

    async def run_lifespan_once():
        monkeypatch.setattr(main.settings, "auto_create_schema", False)
        monkeypatch.setattr(main.settings, "auto_start_workers", False)
        monkeypatch.setattr(main, "validate_db_connection", lambda: None)
        monkeypatch.setattr(main.Base.metadata, "create_all", fake_create_all)
        async with main.lifespan(main.app):
            pass

    asyncio.run(run_lifespan_once())

    assert called is False
