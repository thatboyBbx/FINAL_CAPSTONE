"""
app/ui/analytics_router.py
==========================
Server-rendered analytics and admin UI routes.

All routes load data directly from the DB/service layer (no loopback HTTP calls)
so templates receive fully-populated context on first render.

Routes:
  GET /analytics/claims            — Claims analytics + settlement power rankings
  GET /analytics/insurer-insights  — Market overview + financial positions
  GET /analytics/upload-tracking   — Upload history, OCR/pipeline status per doc
  GET /analytics/jobs              — Job queue monitor + dead-letter management
  GET /analytics/rag-audit         — RAG retrieval audit log + confidence stats
  GET /admin/metrics               — Admin-only system health dashboard
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.ui_dependencies import require_ui_login

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/ui/templates")
router = APIRouter(tags=["analytics_ui"])

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe(fn, default=None):
    """Call fn(), return default on any exception."""
    try:
        return fn()
    except Exception as exc:
        logger.warning("analytics data load error: %s", exc)
        return default


# ─────────────────────────────────────────────────────────────────────────────
# Claims Analytics
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/analytics/claims", response_class=HTMLResponse)
async def analytics_claims(
    request: Request,
    current_user=Depends(require_ui_login),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    from app.modules.insurers.claims_model import ClaimsMetrics
    from app.modules.insurers.model import Insurer

    # Per-insurer latest claims metrics, joined to insurer name
    def _load_claims():
        # Subquery: latest period_label per insurer
        latest_sub = (
            db.query(
                ClaimsMetrics.insurer_id,
                func.max(ClaimsMetrics.period_end_date).label("max_date"),
            )
            .group_by(ClaimsMetrics.insurer_id)
            .subquery()
        )
        rows = (
            db.query(ClaimsMetrics, Insurer.name, Insurer.short_name, Insurer.category)
            .join(Insurer, ClaimsMetrics.insurer_id == Insurer.id)
            .join(
                latest_sub,
                (ClaimsMetrics.insurer_id == latest_sub.c.insurer_id)
                & (ClaimsMetrics.period_end_date == latest_sub.c.max_date),
            )
            .order_by(ClaimsMetrics.settlement_power_score.desc())
            .all()
        )
        return [
            {
                "insurer_id":              r.ClaimsMetrics.insurer_id,
                "insurer_name":            r.name or "—",
                "short_name":              r.short_name or r.name or "—",
                "category":                r.category or "—",
                "period_label":            r.ClaimsMetrics.period_label or "—",
                "settlement_power_score":  round(r.ClaimsMetrics.settlement_power_score or 0, 2),
                "liquidity_score":         round(r.ClaimsMetrics.liquidity_score or 0, 2),
                "current_ratio":           round(r.ClaimsMetrics.current_ratio or 0, 3),
                "complaints_count":        r.ClaimsMetrics.complaints_count or 0,
                "complaints_resolution_rate": round(r.ClaimsMetrics.complaints_resolution_rate or 0, 1),
                "total_policies_count":    r.ClaimsMetrics.total_policies_count or 0,
                "working_capital_negative": r.ClaimsMetrics.working_capital_negative or False,
            }
            for r in rows
        ]

    claims = _safe(_load_claims, [])

    # Summary stats
    scores = [c["settlement_power_score"] for c in claims if c["settlement_power_score"]]
    avg_score = round(sum(scores) / len(scores), 2) if scores else None
    top_performer = claims[0] if claims else None
    weak_performers = [c for c in claims if c["settlement_power_score"] < 40]

    # Category breakdown
    cat_counts: dict[str, int] = {}
    for c in claims:
        cat_counts[c["category"]] = cat_counts.get(c["category"], 0) + 1

    return templates.TemplateResponse(
        request,
        "analytics/claims.html",
        {
            "request": request,
            "user": current_user,
            "active_page": "analytics-claims",
            "claims": claims,
            "avg_score": avg_score,
            "top_performer": top_performer,
            "weak_performer_count": len(weak_performers),
            "total_insurers": len(claims),
            "cat_counts": cat_counts,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Insurer Market Insights
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/analytics/insurer-insights", response_class=HTMLResponse)
async def analytics_insurer_insights(
    request: Request,
    current_user=Depends(require_ui_login),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    from app.modules.insurers.analytics_service import InsurerAnalytics
    from app.modules.insurers.model import Insurer
    from app.modules.financials.model import FinancialSnapshot

    analytics = InsurerAnalytics()
    overview = _safe(lambda: analytics.get_market_overview(db), {})

    # Top 10 by assets (latest snapshot per insurer)
    def _top_insurers():
        latest_sub = (
            db.query(
                FinancialSnapshot.insurer_id,
                func.max(FinancialSnapshot.reporting_date).label("max_date"),
            )
            .group_by(FinancialSnapshot.insurer_id)
            .subquery()
        )
        rows = (
            db.query(FinancialSnapshot, Insurer.name, Insurer.category, Insurer.zse_listed)
            .join(Insurer, FinancialSnapshot.insurer_id == Insurer.id)
            .join(
                latest_sub,
                (FinancialSnapshot.insurer_id == latest_sub.c.insurer_id)
                & (FinancialSnapshot.reporting_date == latest_sub.c.max_date),
            )
            .filter(FinancialSnapshot.total_assets_usd.isnot(None))
            .order_by(FinancialSnapshot.total_assets_usd.desc())
            .limit(15)
            .all()
        )
        return [
            {
                "insurer_id":         r.FinancialSnapshot.insurer_id,
                "insurer_name":       r.name or "—",
                "category":           r.category or "—",
                "zse_listed":         r.zse_listed or False,
                "period_label":       r.FinancialSnapshot.period_label or "—",
                "total_assets_usd":   r.FinancialSnapshot.total_assets_usd,
                "total_revenue_usd":  r.FinancialSnapshot.total_revenue_usd,
                "claims_paid":        r.FinancialSnapshot.claims_paid,
                "market_share_pct":   r.FinancialSnapshot.market_share_pct,
                "liquidity_ratio":    r.FinancialSnapshot.liquidity_ratio,
                "capital_adequacy_ratio": r.FinancialSnapshot.capital_adequacy_ratio,
            }
            for r in rows
        ]

    top_insurers = _safe(_top_insurers, [])

    # Insurer count by category
    cat_rows = _safe(
        lambda: db.query(Insurer.category, func.count(Insurer.id))
                   .group_by(Insurer.category)
                   .all(),
        [],
    )
    category_breakdown = {str(cat or "Other"): cnt for cat, cnt in cat_rows}

    # Total insurer count
    total_insurers = _safe(lambda: db.query(func.count(Insurer.id)).scalar() or 0, 0)

    return templates.TemplateResponse(
        request,
        "analytics/insurer_insights.html",
        {
            "request": request,
            "user": current_user,
            "active_page": "analytics-insurer-insights",
            "overview": overview,
            "top_insurers": top_insurers,
            "category_breakdown": category_breakdown,
            "total_insurers": total_insurers,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Upload & OCR Tracking
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/analytics/upload-tracking", response_class=HTMLResponse)
async def analytics_upload_tracking(
    request: Request,
    current_user=Depends(require_ui_login),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    from app.modules.documents.model import Document
    from app.modules.jobs.model import DocumentJobStep

    # Status distribution
    status_rows = _safe(
        lambda: db.query(Document.status, func.count(Document.id))
                   .group_by(Document.status).all(),
        [],
    )
    status_counts = {s: c for s, c in status_rows}
    total_docs = sum(status_counts.values())

    # Category distribution
    cat_rows = _safe(
        lambda: db.query(Document.document_category, func.count(Document.id))
                   .group_by(Document.document_category).all(),
        [],
    )
    category_counts = {(c or "Uncategorised"): n for c, n in cat_rows}

    # Recent 30 uploads
    recent_docs = _safe(
        lambda: db.query(Document).order_by(Document.created_at.desc()).limit(30).all(),
        [],
    )

    # Per-step pipeline status (step_name × status → count)
    step_rows = _safe(
        lambda: db.query(
            DocumentJobStep.step_name,
            DocumentJobStep.status,
            func.count(DocumentJobStep.id),
        ).group_by(DocumentJobStep.step_name, DocumentJobStep.status).all(),
        [],
    )
    # Build: {step_name: {status: count}}
    pipeline_stats: dict[str, dict[str, int]] = {}
    for step, status, cnt in step_rows:
        pipeline_stats.setdefault(step or "unknown", {})[status] = cnt

    # Embedding coverage
    from app.modules.embeddings.model import DocumentChunk
    indexed_count = _safe(
        lambda: db.query(func.count(func.distinct(DocumentChunk.document_id))).scalar() or 0,
        0,
    )
    total_chunks = _safe(
        lambda: db.query(func.count(DocumentChunk.id)).scalar() or 0,
        0,
    )

    return templates.TemplateResponse(
        request,
        "analytics/upload_tracking.html",
        {
            "request": request,
            "user": current_user,
            "active_page": "analytics-upload-tracking",
            "status_counts": status_counts,
            "total_docs": total_docs,
            "category_counts": category_counts,
            "recent_docs": recent_docs,
            "pipeline_stats": pipeline_stats,
            "indexed_count": indexed_count,
            "total_chunks": total_chunks,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Job Queue Monitor
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/analytics/jobs", response_class=HTMLResponse)
async def analytics_jobs(
    request: Request,
    current_user=Depends(require_ui_login),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    from app.modules.jobs import repo
    from app.modules.jobs.model import DocumentJobStep, QueuedJob

    queue_stats = _safe(lambda: repo.queue_stats(db), {"queues": {}, "dead_letter_total": 0, "dead_letter_pending_redrive": 0})
    dead_letters = _safe(lambda: repo.list_dead_letter(db, limit=25), [])

    # Recent active steps (processing or failed)
    active_steps = _safe(
        lambda: [
            {
                "id":           s.id,
                "document_id":  s.document_id,
                "queue":        s.queue,
                "step_name":    s.step_name,
                "status":       s.status,
                "attempt":      s.attempt,
                "max_attempts": s.max_attempts,
                "error_msg":    (s.error_msg or "")[:200] if s.error_msg else None,
                "queued_at":    s.queued_at.isoformat() if s.queued_at else None,
                "started_at":   s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            }
            for s in (
                db.query(DocumentJobStep)
                .filter(DocumentJobStep.status.in_(["processing", "failed", "queued", "claimed"]))
                .order_by(DocumentJobStep.queued_at.desc())
                .limit(20)
                .all()
            )
        ],
        [],
    )

    # Aggregate totals across all queues for summary cards
    all_counts: dict[str, int] = {}
    for _q, status_map in (queue_stats.get("queues") or {}).items():
        for status, cnt in status_map.items():
            all_counts[status] = all_counts.get(status, 0) + cnt

    return templates.TemplateResponse(
        request,
        "analytics/jobs.html",
        {
            "request": request,
            "user": current_user,
            "active_page": "analytics-jobs",
            "queue_stats": queue_stats,
            "dead_letters": dead_letters,
            "active_steps": active_steps,
            "all_counts": all_counts,
            "is_admin": getattr(current_user, "role", "") == "admin",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# RAG Retrieval Audit
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/analytics/rag-audit", response_class=HTMLResponse)
async def analytics_rag_audit(
    request: Request,
    current_user=Depends(require_ui_login),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    from app.modules.rag_governance.model import RetrievalAuditLog
    from app.core.config import settings

    audit_logs = _safe(
        lambda: db.query(RetrievalAuditLog)
                   .order_by(RetrievalAuditLog.queried_at.desc())
                   .limit(50)
                   .all(),
        [],
    )

    # Summary stats
    total_queries = _safe(lambda: db.query(func.count(RetrievalAuditLog.id)).scalar() or 0, 0)
    avg_confidence = _safe(
        lambda: db.query(func.avg(RetrievalAuditLog.answer_confidence))
                   .filter(RetrievalAuditLog.answer_confidence.isnot(None))
                   .scalar(),
        None,
    )
    answered_count = _safe(
        lambda: db.query(func.count(RetrievalAuditLog.id))
                   .filter(RetrievalAuditLog.answer_returned == True)  # noqa: E712
                   .scalar() or 0,
        0,
    )

    rag_config = {
        "embedding_model":     settings.embedding_model_name,
        "embedding_version":   settings.embedding_version,
        "min_confidence":      float(settings.rag_min_confidence),
        "top_k":               int(settings.rag_top_k),
    }

    # Serialize logs for template (avoid passing ORM objects directly)
    def _ser_log(r: RetrievalAuditLog) -> dict:
        return {
            "id":                     r.id,
            "queried_at":             r.queried_at.strftime("%Y-%m-%d %H:%M") if r.queried_at else "—",
            "document_id":            r.document_id,
            "user_id":                r.user_id,
            "query_text":             (r.query_text or "")[:120],
            "retrieval_method":       r.retrieval_method or "semantic",
            "chunks_retrieved":       r.chunks_retrieved,
            "chunks_above_threshold": r.chunks_above_threshold,
            "top_confidence":         round(r.top_confidence, 3) if r.top_confidence else None,
            "mean_confidence":        round(r.mean_confidence, 3) if r.mean_confidence else None,
            "answer_confidence":      round(r.answer_confidence, 3) if r.answer_confidence else None,
            "answer_returned":        r.answer_returned,
            "embedding_model":        r.embedding_model,
            "embedding_version":      r.embedding_version,
            "hallucination_flags":    r.hallucination_flags_json or "[]",
        }

    logs = [_ser_log(r) for r in audit_logs]

    return templates.TemplateResponse(
        request,
        "analytics/rag_retrieval.html",
        {
            "request": request,
            "user": current_user,
            "active_page": "analytics-rag",
            "logs": logs,
            "total_queries": total_queries,
            "avg_confidence": round(avg_confidence, 3) if avg_confidence else None,
            "answered_count": answered_count,
            "rag_config": rag_config,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Admin System Metrics (admin-only)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/admin/metrics", response_class=HTMLResponse)
async def admin_metrics(
    request: Request,
    current_user=Depends(require_ui_login),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    # RBAC: non-admins see a 403 page
    if getattr(current_user, "role", "") != "admin":
        return templates.TemplateResponse(
            request,
            "errors/403.html",
            {
                "request": request,
                "detail": "Admin metrics requires the admin role.",
                "required_role": "admin",
            },
            status_code=403,
        )

    from app.modules.jobs import repo as jobs_repo
    from app.modules.documents.model import Document
    from app.modules.embeddings.model import DocumentChunk
    from app.modules.rag_governance.model import RetrievalAuditLog
    from app.modules.audit.model import AuditLog
    from app.modules.users.model import User
    from app.core.config import settings

    queue_stats   = _safe(lambda: jobs_repo.queue_stats(db),           {"queues": {}, "dead_letter_total": 0, "dead_letter_pending_redrive": 0})
    dead_letters  = _safe(lambda: jobs_repo.list_dead_letter(db, limit=10), [])

    total_docs    = _safe(lambda: db.query(func.count(Document.id)).scalar() or 0, 0)
    total_chunks  = _safe(lambda: db.query(func.count(DocumentChunk.id)).scalar() or 0, 0)
    indexed_docs  = _safe(lambda: db.query(func.count(func.distinct(DocumentChunk.document_id))).scalar() or 0, 0)
    total_users   = _safe(lambda: db.query(func.count(User.id)).scalar() or 0, 0)
    total_queries = _safe(lambda: db.query(func.count(RetrievalAuditLog.id)).scalar() or 0, 0)

    # Stale embedding count
    stale_count = 0
    try:
        from app.ai.rag.indexing_pipeline import get_stale_document_ids
        stale_count = len(get_stale_document_ids(db, limit=500))
    except Exception:
        pass

    # Document status breakdown
    doc_status_rows = _safe(
        lambda: db.query(Document.status, func.count(Document.id)).group_by(Document.status).all(),
        [],
    )
    doc_status = {s: c for s, c in doc_status_rows}

    # Recent audit events
    recent_events = _safe(
        lambda: [
            {
                "id":         e.id,
                "event_type": e.event_type,
                "actor":      e.actor or "—",
                "ip_address": e.ip_address or "—",
                "timestamp":  e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else "—",
                "details":    str(e.details or "")[:80],
            }
            for e in db.query(AuditLog)
                        .order_by(AuditLog.created_at.desc())
                        .limit(20)
                        .all()
        ],
        [],
    )

    # All queue status totals
    all_counts: dict[str, int] = {}
    for _q, status_map in (queue_stats.get("queues") or {}).items():
        for status, cnt in status_map.items():
            all_counts[status] = all_counts.get(status, 0) + cnt

    sys_config = {
        "env":               settings.env,
        "embedding_model":   settings.embedding_model_name,
        "embedding_version": settings.embedding_version,
        "rag_min_confidence": float(settings.rag_min_confidence),
        "rag_top_k":         int(settings.rag_top_k),
        "queue_backend":     settings.queue_backend,
        "db_pool_size":      settings.db_pool_size,
    }

    return templates.TemplateResponse(
        request,
        "admin/metrics.html",
        {
            "request": request,
            "user": current_user,
            "active_page": "admin-metrics",
            "queue_stats": queue_stats,
            "dead_letters": dead_letters,
            "all_counts": all_counts,
            "total_docs": total_docs,
            "total_chunks": total_chunks,
            "indexed_docs": indexed_docs,
            "total_users": total_users,
            "total_queries": total_queries,
            "stale_count": stale_count,
            "doc_status": doc_status,
            "recent_events": recent_events,
            "sys_config": sys_config,
        },
    )
