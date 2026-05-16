from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.schemas import LoginRequest, TokenResponse
from app.modules.auth import service as auth_service
from app.modules.users import service as users_service
from app.modules.users.schemas import UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    try:
        password_hash = auth_service.hash_password(payload.password)
        user = users_service.create_user(db, payload, password_hash=password_hash)
        return user
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, payload.staff_id, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid staff ID or password.",
        )

    access_token = auth_service.create_access_token(user)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        staff_id=user.staff_id,
        full_name=user.full_name,
        role=user.role,
    )