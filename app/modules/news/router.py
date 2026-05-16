from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Any

from app.core.db import get_db
from app.modules.news.schemas import NewsCreate, NewsRead
from app.modules.news.repo import NewsRepo
from app.modules.news.service import NewsService
from app.modules.news.features import NewsFeatureEngineer

from app.modules.financials.repo import FinancialRepo  # only to get "latest date" window anchor
from app.modules.auth.dependencies import get_current_user

router = APIRouter(
    prefix="/news",
    tags=["news"],
    dependencies=[Depends(get_current_user)],
)
repo = NewsRepo()
service = NewsService()
financial_repo = FinancialRepo()


@router.post("", response_model=NewsRead)
def create_news(payload: NewsCreate, db: Session = Depends(get_db)):
    return service.create_article(db, payload)


@router.get("/articles", response_model=list[NewsRead])
def list_recent_news(
    limit: int = 30,
    skip: int = 0,
    db: Session = Depends(get_db),
):
    return repo.list_recent(db, skip=skip, limit=limit)


@router.get("/status")
def get_news_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return the current news article count as a proxy for scraper status."""
    from app.modules.news.model import NewsArticle  # noqa: PLC0415

    count = db.query(func.count(NewsArticle.id)).scalar() or 0
    return {
        "completed": True,
        "progress_pct": 100,
        "message": f"Database has {count} articles",
        "article_count": count,
    }


@router.get("/{insurer_id}", response_model=list[NewsRead])
def list_news(insurer_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return repo.list_by_insurer(db, insurer_id, skip=skip, limit=limit)


@router.get("/{insurer_id}/features")
def news_features(insurer_id: int, days: int = 90, db: Session = Depends(get_db)):
    # Anchor the window to latest financial reporting_date (same logic as financial features)
    latest_fin = financial_repo.latest(db, insurer_id)
    if not latest_fin:
        raise HTTPException(status_code=404, detail="No financial data found for this insurer to anchor the window.")

    end = latest_fin.reporting_date
    start = end - timedelta(days=days)

    articles = repo.list_by_range(db, insurer_id, start=start, end=end)

    engineer = NewsFeatureEngineer(articles)
    features = engineer.compute()

    return {
        "insurer_id": insurer_id,
        "window_days": days,
        "articles_used": len(articles),
        "features": features,
    }


@router.post("/scrape", status_code=202)
def trigger_news_scrape(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Trigger a one-off news scrape in the background."""
    from app.infrastructure.scrapers.news_scraper import NewsScraper  # noqa: PLC0415
    scraper = NewsScraper()
    background_tasks.add_task(scraper.run, db)
    return {"message": "News scrape started", "status": "queued"}
