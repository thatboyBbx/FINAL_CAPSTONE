from pydantic import BaseModel, Field
from datetime import datetime


class InsurerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    country: str | None = Field(default=None, max_length=80)
    industry_segment: str | None = Field(default=None, max_length=120)


class InsurerRead(BaseModel):
    id: int
    name: str
    country: str | None = None
    industry_segment: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
