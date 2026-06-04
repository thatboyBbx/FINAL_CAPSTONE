from fastapi.testclient import TestClient

from app.modules.auth import service as auth_service
from app.modules.users import service as users_service
from app.modules.users.schemas import UserCreate


def _create_user(db, staff_id: str, email: str, role: str = "user"):
    payload = UserCreate(
        staff_id=staff_id,
        email=email,
        full_name=f"{role.title()} User",
        password="OldPassword123!",
    )
    return users_service.create_user(
        db,
        payload,
        password_hash=auth_service.hash_password(payload.password),
        role=role,
    )


def test_forgot_and_reset_password_flow(client: TestClient, db):
    user = _create_user(db, "RESET_USER", "reset@example.com")

    forgot = client.post("/auth/forgot-password", json={"staff_id": user.staff_id})
    assert forgot.status_code == 200
    reset_token = forgot.json().get("reset_token")
    assert reset_token

    reset = client.post(
        "/auth/reset-password",
        json={"token": reset_token, "new_password": "NewPassword123!"},
    )
    assert reset.status_code == 200

    assert auth_service.authenticate_user(db, user.staff_id, "OldPassword123!") is None
    assert auth_service.authenticate_user(db, user.staff_id, "NewPassword123!") is not None

    reused = client.post(
        "/auth/reset-password",
        json={"token": reset_token, "new_password": "AnotherPassword123!"},
    )
    assert reused.status_code == 400


def test_forgot_password_does_not_enumerate_accounts(client: TestClient):
    response = client.post("/auth/forgot-password", json={"staff_id": "NO_SUCH_USER"})
    assert response.status_code == 200
    assert "reset_token" in response.json()
    assert response.json()["reset_token"] is None


def test_admin_jobs_requires_admin_role(client: TestClient, db):
    user = _create_user(db, "PLAIN_USER", "plain@example.com", role="user")
    token = auth_service.create_access_token(user)

    response = client.get(
        "/api/admin/jobs/stats",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
