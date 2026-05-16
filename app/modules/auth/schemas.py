from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    staff_id: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    staff_id: str
    full_name: str
    role: str


class CurrentUserResponse(BaseModel):
    id: int
    staff_id: str
    email: EmailStr | None = None
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}