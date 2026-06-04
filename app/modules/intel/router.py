"""
Intel router — GDELT ingestion, news articles, ML classifier endpoints.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.intel import repo as intel_repo
from app.modules.intel import classifier as intel_clf
from app.modules.intel import gdelt as intel_gdelt
from app.modules.auth.dependencies import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/intel",
    tags=["intel"],
    dependencies=[Depends(get_current_user)],
)


# ── Ingest ────────────────────────────────────────────────────────────────────

@router.post("/ingest")
def ingest_news(
    hours_back:  int = Query(72,  ge=1, le=168),
    max_records: int = Query(100, ge=1, le=250),
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Fetch Zimbabwe insurance news from GDELT and store in DB."""
    try:
        result = intel_gdelt.ingest(db, hours_back=hours_back, max_records=max_records)

        # Auto-apply labels if model is trained
        if intel_clf.is_trained():
            try:
                intel_clf.apply_labels_to_all(db)
            except Exception as e:
                logger.warning("auto-label after ingest failed: %s", e)

        return JSONResponse(result)
    except Exception as e:
        logger.error("intel ingest error: %s", e)
        return JSONResponse({"error": str(e), "inserted": 0, "skipped": 0}, status_code=500)


# ── Articles ──────────────────────────────────────────────────────────────────

@router.get("/articles")
def list_articles(
    q:              str | None = None,
    insurer_name:   str | None = None,
    insurance_type: str | None = None,
    risk_label:     str | None = None,
    limit:          int = Query(60, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List intel articles with optional filters."""
    try:
        rows = intel_repo.query_articles(
            db, q=q, insurer_name=insurer_name,
            insurance_type=insurance_type, risk_label=risk_label, limit=limit,
        )
        items = []
        for r in rows:
            d = {c.name: getattr(r, c.name) for c in r.__table__.columns}
            try:
                d["topics"] = json.loads(d.get("topics_json") or "[]")
            except Exception:
                d["topics"] = []
            items.append(d)
        return {"count": len(items), "items": items}
    except Exception as e:
        logger.error("intel list_articles error: %s", e)
        return {"count": 0, "items": [], "error": str(e)}


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Return aggregated intel news statistics."""
    try:
        return JSONResponse(intel_repo.get_stats(db))
    except Exception as e:
        logger.error("intel stats error: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Train ─────────────────────────────────────────────────────────────────────

@router.post("/train")
def train_classifier(
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Train TF-IDF + LR classifier on stored intel articles."""
    try:
        articles = intel_repo.get_all_articles(db)
        if not articles:
            return JSONResponse({"error": "No articles found. Ingest news first."}, status_code=400)

        raw = [{"title": a.title, "snippet": a.snippet} for a in articles]
        result = intel_clf.train(raw)

        if "error" not in result:
            try:
                intel_clf.apply_labels_to_all(db)
            except Exception as e:
                logger.warning("apply_labels_to_all error: %s", e)

        return JSONResponse(result)
    except Exception as e:
        logger.error("intel train error: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Predict ───────────────────────────────────────────────────────────────────

@router.get("/predict")
def predict_label(text: str = Query(..., min_length=3)):
    """Predict risk label for arbitrary text."""
    try:
        return JSONResponse(intel_clf.predict(text))
    except Exception as e:
        logger.error("intel predict error: %s", e)
        return JSONResponse({"label": "Neutral", "confidence": 0.0, "source": "error"})


# ── Model info ────────────────────────────────────────────────────────────────

@router.get("/model-info")
def model_info():
    """Return classifier metadata."""
    try:
        meta = intel_clf.get_model_meta()
        if meta:
            return JSONResponse({"trained": True, **meta})
        return JSONResponse({"trained": False})
    except Exception as e:
        logger.error("intel model-info error: %s", e)
        return JSONResponse({"trained": False, "error": str(e)})


# ── Risk counts ───────────────────────────────────────────────────────────────

@router.get("/risk-counts")
def risk_counts(db: Session = Depends(get_db)):
    """Return {label: count} for each risk label."""
    try:
        return JSONResponse(intel_repo.count_by_risk(db))
    except Exception as e:
        logger.error("intel risk-counts error: %s", e)
        return JSONResponse({})
