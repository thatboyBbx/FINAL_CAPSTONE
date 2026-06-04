from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    staff_id: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int            # seconds until access token expires
    user_id: int
    staff_id: str
    full_name: str
    role: str


class RefreshRequest(BaseModel):
    """Body-based refresh — cookie-based refresh is preferred for browsers."""
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """Request a password reset without revealing whether the account exists."""
    staff_id: str | None = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None


class ForgotPasswordResponse(BaseModel):
    detail: str
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32)
    new_password: str = Field(min_length=8)


class CurrentUserResponse(BaseModel):
    id: int
    staff_id: str
    email: EmailStr | None = None
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
