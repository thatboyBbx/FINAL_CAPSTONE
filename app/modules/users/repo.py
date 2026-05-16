from sqlalchemy.orm import Session

from app.modules.users.model import User
from app.modules.users.schemas import UserCreate


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_staff_id(db: Session, staff_id: str) -> User | None:
    return db.query(User).filter(User.staff_id == staff_id).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, payload: UserCreate, password_hash: str) -> User:
    user = User(
        staff_id=payload.staff_id,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=password_hash,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user