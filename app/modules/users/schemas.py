from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    staff_id: str = Field(min_length=2, max_length=100)
    email: EmailStr | None = None
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=8)
    role: str = Field(default="user", min_length=2, max_length=50)


class UserRead(BaseModel):
    id: int
    staff_id: str
    email: EmailStr | None = None
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserPublic(BaseModel):
    id: int
    staff_id: str
    email: EmailStr | None = None
    full_name: str
    role: str

    model_config = {"from_attributes": True}