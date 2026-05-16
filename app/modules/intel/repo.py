"""
Repository layer for IntelArticle — all DB access via SQLAlchemy session.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.modules.intel.model import IntelArticle

logger = logging.getLogger(__name__)


def upsert_article(db: Session, row: dict) -> bool:
    """Insert article. Returns True if inserted, False if already exists."""
    try:
        existing = db.get(IntelArticle, row["id"])
        if existing:
            return False
        article = IntelArticle(
            id=row["id"],
            fetched_at=row["fetched_at"],
            published_at=row.get("published_at"),
            title=row.get("title"),
            url=row["url"],
            domain=row.get("domain"),
            source_country=row.get("source_country"),
            snippet=row.get("snippet"),
            topics_json=json.dumps(row.get("topics", [])),
            raw_json=json.dumps(row.get("raw", {})),
            insurer_name=row.get("insurer_name"),
            insurance_type=row.get("insurance_type"),
        )
        db.add(article)
        db.commit()
        return True
    except Exception as e:
        logger.warning("intel upsert_article error: %s", e)
        db.rollback()
        return False


def update_risk_label(db: Session, article_id: str, label: str, confidence: float) -> None:
    try:
        article = db.get(IntelArticle, article_id)
        if article:
            article.risk_label = label
            article.risk_confidence = confidence
            db.commit()
    except Exception as e:
        logger.warning("intel update_risk_label error: %s", e)
        db.rollback()


def query_articles(
    db: Session,
    q: str | None = None,
    insurer_name: str | None = None,
    insurance_type: str | None = None,
    risk_label: str | None = None,
    limit: int = 60,
) -> list[IntelArticle]:
    try:
        query = db.query(IntelArticle)
        if q:
            pattern = f"%{q}%"
            query = query.filter(
                (IntelArticle.title.ilike(pattern)) | (IntelArticle.snippet.ilike(pattern))
            )
        if insurer_name:
            query = query.filter(IntelArticle.insurer_name == insurer_name)
        if insurance_type:
            query = query.filter(IntelArticle.insurance_type == insurance_type)
        if risk_label:
            query = query.filter(IntelArticle.risk_label == risk_label)
        return (
            query.order_by(
                IntelArticle.published_at.desc().nullslast(),
                IntelArticle.fetched_at.desc(),
            )
            .limit(limit)
            .all()
        )
    except Exception as e:
        logger.warning("intel query_articles error: %s", e)
        return []


def get_all_articles(db: Session) -> List[IntelArticle]:
    """Fetch all articles (used for ML training)."""
    try:
        return db.query(IntelArticle).order_by(IntelArticle.fetched_at.desc()).limit(500).all()
    except Exception as e:
        logger.warning("intel get_all_articles error: %s", e)
        return []


def get_stats(db: Session) -> dict:
    """Return aggregated statistics for the intel news feed."""
    try:
        total = db.query(func.count(IntelArticle.id)).scalar() or 0

        today_str = datetime.now(timezone.utc).date().isoformat()
        today = (
            db.query(func.count(IntelArticle.id))
            .filter(IntelArticle.published_at.like(f"{today_str}%"))
            .scalar()
            or 0
        )

        risk_alerts = (
            db.query(func.count(IntelArticle.id))
            .filter(
                IntelArticle.risk_label.in_(
                    ["Regulatory Risk", "Claims Alert", "Market Risk"]
                )
            )
            .scalar()
            or 0
        )

        # Risk distribution
        risk_rows = (
            db.query(IntelArticle.risk_label, func.count(IntelArticle.id))
            .filter(IntelArticle.risk_label.isnot(None))
            .group_by(IntelArticle.risk_label)
            .all()
        )
        risk_dist = {r[0]: r[1] for r in risk_rows}

        # Top insurer by mention
        ins_rows = (
            db.query(IntelArticle.insurer_name, func.count(IntelArticle.id))
            .filter(IntelArticle.insurer_name.isnot(None))
            .group_by(IntelArticle.insurer_name)
            .order_by(func.count(IntelArticle.id).desc())
            .limit(10)
            .all()
        )
        insurer_counts = [{"insurer_name": r[0], "count": r[1]} for r in ins_rows]

        # Topics — parse from topics_json
        topic_counts: dict = {}
        articles = db.query(IntelArticle.topics_json).filter(IntelArticle.topics_json.isnot(None)).all()
        for (tj,) in articles:
            try:
                for t in json.loads(tj or "[]"):
                    topic_counts[t] = topic_counts.get(t, 0) + 1
            except Exception:
                pass
        top_topic = max(topic_counts, key=topic_counts.get) if topic_counts else "N/A"
        topic_list = sorted(topic_counts.items(), key=lambda x: -x[1])[:10]

        # Daily counts last 30 days
        daily_rows = db.execute(
            text("""
                SELECT date(COALESCE(published_at, fetched_at)) AS d, COUNT(*) AS c
                FROM intel_articles
                WHERE d >= date('now', '-30 days')
                GROUP BY d ORDER BY d
            """)
        ).fetchall()
        daily_counts = [{"date": r[0], "count": r[1]} for r in daily_rows]

        return {
            "total":          total,
            "today":          today,
            "risk_alerts":    risk_alerts,
            "top_topic":      top_topic,
            "risk_dist":      risk_dist,
            "daily_counts":   daily_counts,
            "insurer_counts": insurer_counts,
            "topic_counts":   [{"topic": t, "count": c} for t, c in topic_list],
        }
    except Exception as e:
        logger.warning("intel get_stats error: %s", e)
        return {
            "total": 0, "today": 0, "risk_alerts": 0,
            "top_topic": "N/A", "risk_dist": {}, "daily_counts": [],
            "insurer_counts": [], "topic_counts": [],
        }


def count_by_risk(db: Session) -> dict:
    """Return {label: count} for each risk label."""
    try:
        rows = (
            db.query(IntelArticle.risk_label, func.count(IntelArticle.id))
            .filter(IntelArticle.risk_label.isnot(None))
            .group_by(IntelArticle.risk_label)
            .all()
        )
        return {r[0]: r[1] for r in rows}
    except Exception as e:
        logger.warning("intel count_by_risk error: %s", e)
        return {}
