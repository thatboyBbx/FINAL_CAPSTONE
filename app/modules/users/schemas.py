from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """
    Public self-registration schema.  Role is NOT accepted here — callers
    cannot elevate their own privilege.  All self-registered accounts receive
    the default 'user' role assigned by the repository layer.
    Extra fields (e.g. a legacy 'role' field from old form submissions) are
    silently ignored so existing UI forms keep working without changes.
    """
    model_config = ConfigDict(extra="ignore")

    staff_id:  str           = Field(min_length=2, max_length=100)
    email:     EmailStr | None = None
    full_name: str           = Field(min_length=2, max_length=200)
    password:  str           = Field(min_length=8)


class UserAdminCreate(BaseModel):
    """
    Admin-only user creation schema.  Allows specifying role.
    Used only by the POST /auth/admin/users endpoint (requires admin role).
    """
    staff_id:  str           = Field(min_length=2, max_length=100)
    email:     EmailStr | None = None
    full_name: str           = Field(min_length=2, max_length=200)
    password:  str           = Field(min_length=8)
    role:      str           = Field(default="user", min_length=2, max_length=50)


class UserRead(BaseModel):
    id:         int
    staff_id:   str
    email:      EmailStr | None = None
    full_name:  str
    role:       str
    is_active:  bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserPublic(BaseModel):
    id:        int
    staff_id:  str
    email:     EmailStr | None = None
    full_name: str
    role:      str

    model_config = ConfigDict(from_attributes=True)
