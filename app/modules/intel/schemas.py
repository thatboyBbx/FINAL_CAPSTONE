"""
Pydantic schemas for IntelArticle.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class IntelArticleRead(BaseModel):
    """Read schema for IntelArticle ORM objects."""

    model_config = ConfigDict(from_attributes=True)

    id:              str
    fetched_at:      str
    published_at:    str   | None = None
    title:           str   | None = None
    url:             str
    domain:          str   | None = None
    source_country:  str   | None = None
    snippet:         str   | None = None
    topics_json:     str   | None = None
    insurer_name:    str   | None = None
    insurance_type:  str   | None = None
    risk_label:      str   | None = None
    risk_confidence: float | None = None


class IntelStatsRead(BaseModel):
    """Aggregated statistics for IntelArticles."""

    total:          int
    today:          int
    risk_alerts:    int
    top_topic:      str
    risk_dist:      dict
    daily_counts:   list[dict]
    insurer_counts: list[dict]
    topic_counts:   list[dict]
