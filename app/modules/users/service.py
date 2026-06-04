from app.modules.users import repo
from app.modules.users.model import User
from app.modules.users.schemas import UserCreate


def create_user(
    db,
    payload: UserCreate,
    password_hash: str,
    role: str = "user",
) -> User:
    normalized_staff_id = payload.staff_id.strip().upper()
    normalized_email = payload.email.strip().lower() if payload.email else None
    normalized_role = role.strip().lower()

    existing_staff_id = repo.get_user_by_staff_id(db, normalized_staff_id)
    if existing_staff_id:
        raise ValueError("A user with this staff ID already exists.")

    if normalized_email:
        existing_email = repo.get_user_by_email(db, normalized_email)
        if existing_email:
            raise ValueError("A user with this email already exists.")

    normalized_payload = UserCreate(
        staff_id=normalized_staff_id,
        email=normalized_email,
        full_name=payload.full_name.strip(),
        password=payload.password,
    )

    return repo.create_user(db, normalized_payload, password_hash=password_hash, role=normalized_role)


def get_user_by_id(db, user_id: int) -> User | None:
    return repo.get_user_by_id(db, user_id)


def get_user_by_staff_id(db, staff_id: str) -> User | None:
    normalized_staff_id = staff_id.strip().upper()
    return repo.get_user_by_staff_id(db, normalized_staff_id)


def get_user_by_email(db, email: str) -> User | None:
    normalized_email = email.strip().lower()
    return repo.get_user_by_email(db, normalized_email)


def update_password_hash(db, user: User, password_hash: str) -> User:
    user.password_hash = password_hash
    db.commit()
    db.refresh(user)
    return user
