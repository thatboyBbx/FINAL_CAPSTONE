from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from datetime import date

from app.modules.news.model import NewsArticle


class NewsRepo:
    def create(self, db: Session, article: NewsArticle) -> NewsArticle:
        db.add(article)
        db.commit()
        db.refresh(article)
        return article

    def list_by_insurer(self, db: Session, insurer_id: int, skip: int = 0, limit: int = 100) -> list[NewsArticle]:
        stmt = (
            select(NewsArticle)
            .where(NewsArticle.insurer_id == insurer_id)
            .order_by(desc(NewsArticle.published_date))
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def list_by_range(self, db: Session, insurer_id: int, start: date, end: date) -> list[NewsArticle]:
        stmt = (
            select(NewsArticle)
            .where(NewsArticle.insurer_id == insurer_id)
            .where(NewsArticle.published_date >= start)
            .where(NewsArticle.published_date <= end)
            .order_by(desc(NewsArticle.published_date))
        )
        return list(db.execute(stmt).scalars().all())

    def list_recent(self, db: Session, skip: int = 0, limit: int = 100) -> list[NewsArticle]:
        stmt = (
            select(NewsArticle)
            .order_by(desc(NewsArticle.published_date), desc(NewsArticle.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())
