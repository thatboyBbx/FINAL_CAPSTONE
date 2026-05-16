from pydantic import BaseModel, Field
from datetime import date, datetime


class NewsCreate(BaseModel):
    insurer_id: int
    published_date: date
    title: str = Field(min_length=3, max_length=400)
    source: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=500)
    content: str = Field(min_length=10)


class NewsRead(BaseModel):
    id: int
    insurer_id: int
    published_date: date
    title: str
    source: str | None = None
    url: str | None = None
    content: str
    snippet: str | None = None
    sentiment_score: float | None = None
    sentiment_label: str | None = None
    keywords: list[str] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
