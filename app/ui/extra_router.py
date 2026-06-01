import asyncio
import httpx
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.modules.auth.ui_dependencies import require_ui_login
from app.core.config import settings
from app.core.db import get_db

templates = Jinja2Templates(directory="app/ui/templates")
router = APIRouter(tags=["extra_ui"])

_BASE_URL = "http://127.0.0.1:8000"


def _check_auth(request: Request):
    return request.cookies.get("access_token")


def _auth_headers_from_cookie(request: Request) -> dict:
    token = request.cookies.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


# ─── Shared data-loading helpers ─────────────────────────────────────────────

_AUDIT_PAGE_SIZE = 25
_AUDIT_ERROR_TYPES = {"LOGIN_FAILED", "PERMISSION_DENIED"}


def _load_audit_events(
    db,
    action: str | None = None,
    user_filter: str | None = None,
    current_actor: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
) -> tuple[list, int]:
    from app.modules.audit.model import AuditLog
    from datetime import datetime as _dt

    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.event_type.ilike(f"%{action.upper().replace(' ', '_')}%"))
    if user_filter == "current" and current_actor:
        q = q.filter(AuditLog.actor == current_actor)
    elif user_filter and user_filter != "current":
        q = q.filter(AuditLog.actor.ilike(f"%{user_filter}%"))
    if date_from:
        try:
            q = q.filter(AuditLog.created_at >= _dt.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to:
        try:
            dt_end = _dt.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            q = q.filter(AuditLog.created_at <= dt_end)
        except ValueError:
            pass

    total = q.count()
    rows = (
        q.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * _AUDIT_PAGE_SIZE)
        .limit(_AUDIT_PAGE_SIZE)
        .all()
    )

    events = []
    for r in rows:
        et = r.event_type or ""
        res = "—"
        if r.document_id:
            res = f"doc#{r.document_id}"
        elif r.analysis_id:
            res = f"analysis#{r.analysis_id}"
        elif r.details and isinstance(r.details, dict):
            res = str(r.details.get("resource", "—"))[:60]
        events.append({
            "ts":         r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "—",
            "action":     et.replace("_", " ").title(),
            "event_type": et,
            "user":       r.actor or "System",
            "resource":   res,
            "status":     "error" if et in _AUDIT_ERROR_TYPES else "success",
            "ip":         r.ip_address or "—",
        })
    return events, total


def _load_feedback_context(db) -> dict:
    from app.modules.feedback.model import EntityFeedback, RiskFlagFeedback

    entity_count = db.query(EntityFeedback).count() or 0
    risk_count   = db.query(RiskFlagFeedback).count() or 0
    MIN_RETRAIN  = 50
    pending = db.query(EntityFeedback).filter(EntityFeedback.used_in_training == False).count() or 0  # noqa: E712
    readiness_pct = min(100, round((pending / MIN_RETRAIN) * 100)) if pending else 0

    recent = (
        db.query(EntityFeedback)
        .order_by(EntityFeedback.created_at.desc())
        .limit(20)
        .all()
    )
    feedback_rows = [
        {
            "doc":       f"doc#{f.document_id}",
            "etype":     f.original_type or "—",
            "original":  (f.original_value or "—")[:40],
            "corrected": (f.corrected_value or "—")[:40],
            "reviewer":  f.corrected_by or "—",
            "status":    "used" if f.used_in_training else "pending",
            "date":      f.created_at.strftime("%d %b %Y") if f.created_at else "—",
        }
        for f in recent
    ]
    return {
        "entity_count":    entity_count,
        "risk_count":      risk_count,
        "readiness_pct":   readiness_pct,
        "pending_training": pending,
        "feedback_rows":   feedback_rows,
    }


# ────────────────────────────────────────────────────────────────────────────
# CATEGORY LANDING PAGES  (A1-T6)
# ────────────────────────────────────────────────────────────────────────────

@router.get("/documents", response_class=HTMLResponse)
async def documents_landing(request: Request, current_user=Depends(require_ui_login)):
    """Documents category landing — tile dashboard."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "documents/index.html", {
        "request": request, "active_page": "documents",
        "user": current_user,
    })


@router.get("/analysis", response_class=HTMLResponse)
async def analysis_landing(request: Request, current_user=Depends(require_ui_login)):
    """Analysis category landing — tile dashboard."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "analysis/index.html", {
        "request": request, "active_page": "analysis",
        "user": current_user,
    })


@router.get("/intelligence", response_class=HTMLResponse)
async def intelligence_landing(request: Request, current_user=Depends(require_ui_login)):
    """Intelligence category landing — tile dashboard."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "intelligence/index.html", {
        "request": request, "active_page": "intelligence",
        "user": current_user,
    })


@router.get("/reports", response_class=HTMLResponse)
async def reports_landing(request: Request, current_user=Depends(require_ui_login)):
    """Reports category landing — tile dashboard."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "reports/index.html", {
        "request": request, "active_page": "reports",
        "user": current_user,
    })


@router.get("/clients", response_class=HTMLResponse)
async def clients_landing(request: Request, current_user=Depends(require_ui_login)):
    """Client Management category landing — tile dashboard."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "clients/index.html", {
        "request": request, "active_page": "clients",
        "user": current_user,
    })


@router.get("/system", response_class=HTMLResponse)
async def system_landing(request: Request, current_user=Depends(require_ui_login)):
    """System category landing — tile dashboard."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "system/index.html", {
        "request": request, "active_page": "system",
        "user": current_user,
    })


# ────────────────────────────────────────────────────────────────────────────
# DOCUMENTS SUB-PAGES  (A1-T7)
# ────────────────────────────────────────────────────────────────────────────

@router.get("/documents/vault", response_class=HTMLResponse)
async def documents_vault(request: Request, current_user=Depends(require_ui_login)):
    """Document Vault — searchable table of all uploaded documents."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "documents/vault.html", {
        "request": request, "active_page": "documents-vault",
        "user": current_user,
    })


@router.get("/documents/upload", response_class=HTMLResponse)
async def documents_upload(request: Request, current_user=Depends(require_ui_login)):
    """Document Upload — drag-and-drop upload zone."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "documents/upload.html", {
        "request": request, "active_page": "documents-upload",
        "user": current_user,
    })


@router.post("/documents/upload", response_class=JSONResponse)
async def documents_upload_post(
    request: Request,
    title: str = Form(...),
    uploaded_by_user_id: int | None = Form(None),
    document_category: str | None = Form(None),
    notes: str | None = Form(None),
    client_id: int | None = Form(None),
    file: UploadFile = File(...),
    current_user=Depends(require_ui_login),
):
    """Proxy multipart upload to the API, return JSON for XHR client."""
    if isinstance(current_user, RedirectResponse):
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    token = request.cookies.get("access_token")
    auth_headers = {"Authorization": f"Bearer {token}"} if token else {}

    form_data = {
        "title": title,
        "uploaded_by_user_id": str(uploaded_by_user_id or current_user.id),
        "document_category": document_category or "",
        "notes": notes or "",
        "status_value": "uploaded",
    }
    if client_id:
        form_data["client_id"] = str(client_id)
    file_content = await file.read()
    files = {"file": (file.filename or "document", file_content, file.content_type or "application/octet-stream")}

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(
                f"{settings.api_base}/api/documents/upload",
                data=form_data,
                files=files,
                headers=auth_headers,
            )
            if resp.status_code == 201:
                return JSONResponse(resp.json(), status_code=200)
            detail = "Upload failed."
            try:
                detail = resp.json().get("detail", detail)
            except Exception:
                pass
            return JSONResponse({"detail": detail}, status_code=resp.status_code)
        except Exception as exc:
            return JSONResponse({"detail": str(exc)}, status_code=500)


@router.get("/documents/compare", response_class=HTMLResponse)
async def documents_compare(request: Request, current_user=Depends(require_ui_login)):
    """Document Compare — side-by-side diff view."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "documents/compare.html", {
        "request": request, "active_page": "documents-compare",
        "user": current_user,
    })


# ────────────────────────────────────────────────────────────────────────────
# ANALYSIS SUB-PAGES  (A1-T8)
# ────────────────────────────────────────────────────────────────────────────

@router.get("/analysis/ml", response_class=HTMLResponse)
async def analysis_ml(request: Request, current_user=Depends(require_ui_login)):
    """ML Analytics — multi-doc analysis runner."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "analysis/ml.html", {
        "request": request, "active_page": "analysis-ml",
        "user": current_user,
    })


@router.get("/analysis/deviation", response_class=HTMLResponse)
async def analysis_deviation(request: Request, current_user=Depends(require_ui_login)):
    """Clause Deviation analysis page."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "analysis/deviation.html", {
        "request": request, "active_page": "analysis-deviation",
        "user": current_user,
    })


@router.get("/analysis/ner", response_class=HTMLResponse)
async def analysis_ner(request: Request, current_user=Depends(require_ui_login)):
    """NER Extraction analysis page."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "analysis/ner.html", {
        "request": request, "active_page": "analysis-ner",
        "user": current_user,
    })


@router.get("/analysis/risk", response_class=HTMLResponse)
async def analysis_risk(request: Request, current_user=Depends(require_ui_login)):
    """Risk Analysis page for a selected document."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "analysis/risk.html", {
        "request": request, "active_page": "analysis-risk",
        "user": current_user,
    })


@router.get("/analysis/risk-alert", response_class=HTMLResponse)
async def analysis_risk_alert(request: Request):
    """301 redirect: /analysis/risk-alert → /analysis/risk."""
    return RedirectResponse(url="/analysis/risk", status_code=301)


# ────────────────────────────────────────────────────────────────────────────
# REPORTS SUB-PAGES  (A1-T9)
# ────────────────────────────────────────────────────────────────────────────

@router.get("/reports/compliance", response_class=HTMLResponse)
async def reports_compliance(request: Request, current_user=Depends(require_ui_login)):
    """Compliance check page."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "reports/compliance.html", {
        "request": request, "active_page": "reports-compliance",
        "user": current_user,
    })


@router.get("/reports/generate", response_class=HTMLResponse)
async def reports_generate(request: Request, current_user=Depends(require_ui_login)):
    """PDF report generation page."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "reports/generate.html", {
        "request": request, "active_page": "reports-generate",
        "user": current_user,
    })


@router.get("/reports/news", response_class=HTMLResponse)
async def reports_news(request: Request, current_user=Depends(require_ui_login)):
    """News Feed scraper page."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "reports/news.html", {
        "request": request, "active_page": "reports-news",
        "user": current_user,
    })


# ────────────────────────────────────────────────────────────────────────────
# INTELLIGENCE SUB-PAGES  (A1-T10)
# ────────────────────────────────────────────────────────────────────────────

@router.get("/intelligence/insurers", response_class=HTMLResponse)
async def intelligence_insurers(request: Request, current_user=Depends(require_ui_login)):
    """Insurer Intel — table with CSV import."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "intelligence/insurers/index.html", {
        "request": request, "active_page": "intelligence-insurers",
        "user": current_user,
    })


@router.get("/intelligence/insurers/{insurer_id}", response_class=HTMLResponse)
async def intelligence_insurer_profile(request: Request, insurer_id: int, current_user=Depends(require_ui_login)):
    """Insurer profile — tabs for Overview, Financials, CSP, News."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "intelligence/insurers/profile.html", {
        "request": request, "active_page": "intelligence-insurers",
        "insurer_id": insurer_id,
        "user": current_user,
    })


@router.get("/intelligence/advisory", response_class=HTMLResponse)
async def intelligence_advisory(request: Request, current_user=Depends(require_ui_login)):
    """Advisory Engine — insurer recommendation for a selected policy."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "intelligence/advisory.html", {
        "request": request, "active_page": "intelligence-advisory",
        "user": current_user,
    })


@router.get("/intelligence/settlement-power", response_class=HTMLResponse)
async def intelligence_settlement_power(request: Request, current_user=Depends(require_ui_login)):
    """Settlement Power WCS scoring dashboard."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "intelligence/settlement_power.html", {
        "request": request, "active_page": "intelligence-settlement-power",
        "user": current_user,
    })


# ────────────────────────────────────────────────────────────────────────────
# CLIENT MANAGEMENT SUB-PAGES  (A1-T12)
# ────────────────────────────────────────────────────────────────────────────

@router.get("/clients/list", response_class=HTMLResponse)
async def clients_list(request: Request, current_user=Depends(require_ui_login)):
    """Client list — searchable, filterable table."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "clients/list.html", {
        "request": request, "active_page": "clients-list",
        "user": current_user,
    })


# NOTE: /clients/expiry and /clients/renewals MUST come before /clients/{client_id}
# to prevent FastAPI matching "expiry"/"renewals" as a client_id integer path param.

@router.get("/clients/expiry", response_class=HTMLResponse)
async def clients_expiry(request: Request, current_user=Depends(require_ui_login)):
    """Policy expiry tracker — 30/60/90 day toggle."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "clients/expiry.html", {
        "request": request, "active_page": "clients-expiry",
        "user": current_user,
    })


@router.get("/clients/renewals", response_class=HTMLResponse)
async def clients_renewals(request: Request, current_user=Depends(require_ui_login)):
    """Renewal tracker — kanban board."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "clients/renewals.html", {
        "request": request, "active_page": "clients-renewals",
        "user": current_user,
    })


@router.get("/clients/{client_id}", response_class=HTMLResponse)
async def client_profile(request: Request, client_id: int, current_user=Depends(require_ui_login)):
    """Single client profile — tabs for Policies, Notes, Interactions, Alerts."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "clients/profile.html", {
        "request": request, "active_page": "clients-list",
        "client_id": client_id,
        "user": current_user,
    })


# ────────────────────────────────────────────────────────────────────────────
# SYSTEM SUB-PAGES  (A1-T6 / A1-T14)
# ────────────────────────────────────────────────────────────────────────────

@router.get("/system/settings", response_class=HTMLResponse)
async def system_settings(request: Request, current_user=Depends(require_ui_login)):
    """System settings page."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(request, "system/settings.html", {
        "request": request, "active_page": "settings",
        "user": current_user,
    })


@router.get("/system/audit", response_class=HTMLResponse)
async def system_audit(
    request: Request,
    current_user=Depends(require_ui_login),
    action: str | None = Query(None),
    user: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    """System audit log page — real data from AuditLog table."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    try:
        events, total_count = _load_audit_events(
            db,
            action=action,
            user_filter=user,
            current_actor=current_user.full_name,
            date_from=date_from,
            date_to=date_to,
            page=page,
        )
    except Exception:
        events, total_count = [], 0
    return templates.TemplateResponse(request, "system/audit_trail.html", {
        "request":       request,
        "active_page":   "audit-trail",
        "user":          current_user,
        "full_name":     current_user.full_name,
        "role":          current_user.role,
        "events":        events,
        "total_count":   total_count,
        "page":          page,
        "page_size":     _AUDIT_PAGE_SIZE,
        "action_filter": action or "",
        "user_filter":   user or "",
        "date_from":     date_from or "",
        "date_to":       date_to or "",
    })


@router.get("/system/active-learning", response_class=HTMLResponse)
async def system_active_learning(
    request: Request,
    current_user=Depends(require_ui_login),
    db: Session = Depends(get_db),
):
    """Active learning / feedback panel — real data from EntityFeedback table."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    try:
        ctx = _load_feedback_context(db)
    except Exception:
        ctx = {"entity_count": 0, "risk_count": 0, "readiness_pct": 0, "pending_training": 0, "feedback_rows": []}
    return templates.TemplateResponse(request, "system/feedback_panel.html", {
        "request":     request,
        "active_page": "feedback-panel",
        "user":        current_user,
        "full_name":   current_user.full_name,
        **ctx,
    })


# ────────────────────────────────────────────────────────────────────────────
# LEGACY EXTRA ROUTES (existing below this comment — unchanged)
# ────────────────────────────────────────────────────────────────────────────

@router.get("/audit-trail", response_class=HTMLResponse)
async def audit_trail_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    qs = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(url=f"/system/audit{qs}", status_code=301)

@router.get("/batch-portfolio", response_class=HTMLResponse)
async def batch_portfolio_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(
        request,
        "documents/batch_portfolio.html",
        {
            "request": request,
            "active_page": "batch-portfolio",
            "user": current_user,
        },
    )

@router.get("/clause-deviations", response_class=HTMLResponse)
async def clause_deviations_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(
        request,
        "analysis/clause_deviations.html",
        {
            "request": request,
            "active_page": "clause-deviations",
            "user": current_user,
        },
    )

@router.get("/compliance-center", response_class=HTMLResponse)
async def compliance_center_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    stats = {
        "total_documents_checked": 0,
        "compliant": 0,
        "non_compliant": 0,
        "needs_review": 0,
        "average_compliance_score": 0.0,
        "common_violations": [],
    }
    try:
        async with httpx.AsyncClient(base_url=_BASE_URL) as client:
            resp = await client.get(
                "/api/documents/compliance/statistics",
                headers=_auth_headers_from_cookie(request),
                timeout=10,
            )
            if resp.status_code == 200:
                stats = resp.json()
    except Exception:
        pass

    return templates.TemplateResponse(
        request,
        "analysis/compliance_center.html",
        {
            "request": request,
            "active_page": "compliance-center",
            "user": current_user,
            "avg_compliance_score": stats.get("average_compliance_score", 0.0),
            "compliant_count": stats.get("compliant", 0),
            "non_compliant_count": stats.get("non_compliant", 0),
            "needs_review_count": stats.get("needs_review", 0),
            "total_documents_checked": stats.get("total_documents_checked", 0),
            "common_violations": stats.get("common_violations", []),
        },
    )


@router.get("/documents-ui/{document_id}/compliance", response_class=HTMLResponse)
async def compliance_detail_page(document_id: int, request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    document = None
    compliance = None
    error = None

    try:
        async with httpx.AsyncClient(base_url=_BASE_URL) as client:
            headers = _auth_headers_from_cookie(request)

            doc_resp, comp_resp = await asyncio.gather(
                client.get(f"/api/documents/{document_id}", headers=headers, timeout=10),
                client.get(f"/api/documents/{document_id}/compliance", headers=headers, timeout=10),
            )

            if doc_resp.status_code == 200:
                document = doc_resp.json()
            if comp_resp.status_code == 200:
                compliance = comp_resp.json()
            elif comp_resp.status_code == 404:
                error = "No compliance check found. Process the document first."
            else:
                error = "Could not load compliance data."
    except Exception as exc:
        error = f"Service error: {exc}"

    return templates.TemplateResponse(
        request,
        "analysis/compliance_detail.html",
        {
            "request": request,
            "active_page": "documents",
            "user": current_user,
            "document": document,
            "compliance": compliance,
            "error": error,
            "document_id": document_id,
        },
    )

@router.get("/document-comparison", response_class=HTMLResponse)
async def document_comparison_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return RedirectResponse(url="/documents/compare", status_code=301)

@router.get("/feedback-panel", response_class=HTMLResponse)
async def feedback_panel_page(
    request: Request,
    current_user=Depends(require_ui_login),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    try:
        ctx = _load_feedback_context(db)
    except Exception:
        ctx = {"entity_count": 0, "risk_count": 0, "readiness_pct": 0, "pending_training": 0, "feedback_rows": []}
    return templates.TemplateResponse(
        request,
        "system/feedback_panel.html",
        {
            "request":     request,
            "active_page": "feedback-panel",
            "user":        current_user,
            "full_name":   current_user.full_name,
            **ctx,
        },
    )

@router.get("/knowledge-base", response_class=HTMLResponse)
async def knowledge_base_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(
        request,
        "reports/knowledge_base.html",
        {
            "request": request,
            "active_page": "knowledge-base",
            "user": current_user,
        },
    )

@router.get("/multilingual-analysis", response_class=HTMLResponse)
async def multilingual_analysis_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(
        request,
        "analysis/multilingual.html",
        {
            "request": request,
            "active_page": "multilingual-analysis",
            "user": current_user,
        },
    )

@router.get("/policy-tracker", response_class=HTMLResponse)
async def policy_tracker_page(
    request: Request,
    current_user=Depends(require_ui_login),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    from app.modules.tracker.model import PolicyTracker
    from datetime import date as _date

    today = _date.today()
    try:
        policies_orm = (
            db.query(PolicyTracker)
            .order_by(PolicyTracker.expiry_date.asc())
            .limit(200)
            .all()
        )
    except Exception:
        policies_orm = []

    policies = []
    for p in policies_orm:
        days = p.days_until_expiry
        if days is None and p.expiry_date:
            days = (p.expiry_date - today).days
        policies.append({
            "policy_number": p.policy_number or "—",
            "insured_name":  p.insured_name  or "—",
            "insurer_name":  p.insurer_name  or "—",
            "expiry_date":   p.expiry_date.strftime("%d %b %Y") if p.expiry_date else "—",
            "days":          days,
            "alert_status":  p.alert_status or "active",
            "document_id":   p.document_id,
        })

    active_count    = sum(1 for p in policies if p["alert_status"] == "active")
    expiring_7      = sum(1 for p in policies if isinstance(p["days"], int) and 0 <= p["days"] <= 7)
    expiring_30     = sum(1 for p in policies if isinstance(p["days"], int) and 0 <= p["days"] <= 30)
    pending_renewal = sum(1 for p in policies if p["alert_status"] == "expiring_soon")
    urgent          = [p for p in policies if isinstance(p["days"], int) and 0 <= p["days"] <= 7]

    return templates.TemplateResponse(
        request,
        "clients/policy_tracker.html",
        {
            "request":         request,
            "active_page":     "policy-tracker",
            "user":            current_user,
            "full_name":       current_user.full_name,
            "policies":        policies,
            "expiring_7":      expiring_7,
            "expiring_30":     expiring_30,
            "pending_renewal": pending_renewal,
            "active_count":    active_count,
            "total_policies":  len(policies),
            "urgent_policies": urgent,
        },
    )

@router.get("/scraper-status", response_class=HTMLResponse)
async def scraper_status_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return RedirectResponse(url="/system", status_code=301)

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(
        request,
        "system/settings.html",
        {
            "request": request,
            "active_page": "settings",
            "user": current_user,
        },
    )

@router.get("/document-qa", response_class=HTMLResponse)
async def document_qa_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(
        request,
        "documents/qa.html",
        {
            "request": request,
            "active_page": "document-qa",
            "user": current_user,
        },
    )
