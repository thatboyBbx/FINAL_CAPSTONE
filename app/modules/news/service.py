from sqlalchemy.orm import Session

from app.modules.news.model import NewsArticle
from app.modules.news.repo import NewsRepo
from app.modules.news.schemas import NewsCreate


class NewsService:
    def __init__(self) -> None:
        self.repo = NewsRepo()

    def create_article(self, db: Session, payload: NewsCreate) -> NewsArticle:
        article = NewsArticle(
            insurer_id=payload.insurer_id,
            published_date=payload.published_date,
            title=payload.title.strip(),
            source=(payload.source.strip() if payload.source else None),
            url=(payload.url.strip() if payload.url else None),
            content=payload.content.strip(),
        )
        return self.repo.create(db, article)
