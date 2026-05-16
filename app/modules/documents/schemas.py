from datetime import datetime

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    original_filename: str = Field(min_length=1, max_length=255)
    stored_filename: str = Field(min_length=1, max_length=255)
    file_path: str = Field(min_length=1, max_length=500)
    mime_type: str = Field(min_length=1, max_length=120)
    file_size: int = Field(gt=0)
    status: str = Field(default="uploaded", min_length=1, max_length=50)
    document_category: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    uploaded_by_user_id: int = Field(gt=0)
    client_id: int | None = None


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, min_length=1, max_length=50)
    document_category: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    client_id: int | None = None


class DocumentRead(BaseModel):
    id: int
    title: str
    original_filename: str
    stored_filename: str
    file_path: str
    mime_type: str
    file_size: int
    status: str
    document_category: str | None = None
    notes: str | None = None
    uploaded_by_user_id: int
    client_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
