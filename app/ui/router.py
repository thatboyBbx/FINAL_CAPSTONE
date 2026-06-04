from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import httpx

from collections import Counter

from sqlalchemy import or_

from app.core.config import settings
from app.core.db import SessionLocal
from app.modules.insurers.repo import InsurerRepo
from app.modules.circulars import service as circular_service
from app.modules.ml.visualization_service import get_default_dashboard_visualizations
from app.modules.ml.circular_classifier import get_classifier_status
from app.modules.intel.advisory_service import generate_advisory
from app.modules.auth import service as auth_service
from app.modules.auth.token_store import (
    create_password_reset_token,
    mark_password_reset_token_used,
    set_revocation_fence,
    verify_password_reset_token,
)
from app.modules.auth.ui_dependencies import require_ui_login
from app.modules.users import service as users_service

from app.modules.tracker.service import PolicyTrackerService
from app.modules.feedback.feedback_store import FeedbackStore
from app.modules.audit.audit_logger import AuditLogger
from app.modules.qa.model import QASession
from app.modules.comparison.model import DocumentComparison
from app.modules.batch.model import ProcessingBatch

templates = Jinja2Templates(directory="app/ui/templates")

router = APIRouter(tags=["ui"])


def _auth_headers_from_cookie(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _format_api_error(detail) -> str:
    """Convert an API error detail (string or Pydantic validation list) into a
    clean, human-readable message — never dumps raw Python reprs to the UI."""
    if isinstance(detail, str):
        return detail

    if isinstance(detail, list):
        parts = []
        for item in detail:
            if not isinstance(item, dict):
                continue
            loc = item.get("loc", [])
            msg = item.get("msg", "")
            # Strip generic prefixes ('body', 'query', 'path') from the location
            field_parts = [
                str(l) for l in loc
                if str(l) not in ("body", "query", "path", "header")
            ]
            if field_parts and msg:
                field = " → ".join(field_parts).replace("_", " ").title()
                parts.append(f"{field}: {msg.rstrip('.')}")
            elif msg:
                parts.append(msg.rstrip("."))
        return ".  ".join(parts) if parts else "Please check your input and try again."

    return "An unexpected error occurred. Please try again."


@router.get("/api/global-search", response_class=JSONResponse)
def global_search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=120),
    limit: int = Query(8, ge=1, le=20),
    current_user=Depends(require_ui_login),
):
    if isinstance(current_user, RedirectResponse):
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    query = q.strip()
    if not query:
        return JSONResponse({"query": q, "results": []})

    like = f"%{query}%"
    results: list[dict] = []

    db = SessionLocal()
    try:
        from app.modules.clients.model import Client
        from app.modules.documents.model import Document
        from app.modules.insurers.model import Insurer

        documents = (
            db.query(Document)
            .filter(
                or_(
                    Document.title.ilike(like),
                    Document.original_filename.ilike(like),
                    Document.document_category.ilike(like),
                    Document.folder.ilike(like),
                )
            )
            .order_by(Document.created_at.desc())
            .limit(limit)
            .all()
        )
        for doc in documents:
            results.append(
                {
                    "type": "document",
                    "label": doc.title,
                    "meta": doc.original_filename or doc.document_category or "Document",
                    "href": f"/documents/{doc.id}",
                    "icon": "description",
                }
            )

        insurers = (
            db.query(Insurer)
            .filter(
                or_(
                    Insurer.name.ilike(like),
                    Insurer.short_name.ilike(like),
                    Insurer.category.ilike(like),
                    Insurer.email.ilike(like),
                    Insurer.head_office_city.ilike(like),
                )
            )
            .order_by(Insurer.name.asc())
            .limit(limit)
            .all()
        )
        for insurer in insurers:
            results.append(
                {
                    "type": "insurer",
                    "label": insurer.name,
                    "meta": (insurer.category or "Insurer").replace("_", " ").title(),
                    "href": f"/intelligence/insurers/{insurer.id}",
                    "icon": "domain",
                }
            )

        clients = (
            db.query(Client)
            .filter(
                or_(
                    Client.name.ilike(like),
                    Client.company.ilike(like),
                    Client.email.ilike(like),
                    Client.phone.ilike(like),
                    Client.segment.ilike(like),
                )
            )
            .order_by(Client.name.asc())
            .limit(limit)
            .all()
        )
        for client in clients:
            results.append(
                {
                    "type": "client",
                    "label": client.name,
                    "meta": client.company or client.email or "Client",
                    "href": f"/clients/{client.id}",
                    "icon": "person",
                }
            )
    finally:
        db.close()

    page_catalog = [
        ("Dashboard", "Home dashboard and recent documents", "/home", "dashboard"),
        ("Document Vault", "Browse uploaded documents", "/documents/vault", "folder_open"),
        ("Upload Document", "Add a policy, claim, or report", "/documents/upload", "upload_file"),
        ("Compliance Check", "Run IPEC compliance analysis", "/reports/compliance", "verified_user"),
        ("Settlement Power", "Claims settlement WCS dashboard", "/intelligence/settlement-power", "shield_with_heart"),
        ("Insurer Intel", "Insurer registry and profiles", "/intelligence/insurers", "domain"),
        ("Clients", "Client list and policies", "/clients", "groups"),
        ("Knowledge Base", "Ask policy and regulatory questions", "/knowledge-base", "school"),
        ("Reports", "Generate and export reports", "/reports", "summarize"),
        ("Jobs", "Background job monitoring", "/analytics/jobs", "work_history"),
    ]
    query_lower = query.lower()
    for label, meta, href, icon in page_catalog:
        if query_lower in label.lower() or query_lower in meta.lower():
            results.append(
                {
                    "type": "page",
                    "label": label,
                    "meta": meta,
                    "href": href,
                    "icon": icon,
                }
            )

    return JSONResponse({"query": query, "results": results[:limit]})


@router.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request, "error": None},
    )


@router.get("/login")
def login_page_named(request: Request, next: str = "/home"):
    """Render login page. `next` tells us where to redirect after successful login."""
    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request, "next_url": next, "error": None},
    )


@router.post("/login")
def login_submit(
    request: Request,
    staff_id: str = Form(...),
    password: str = Form(...),
    next_url: str = Form(default="/home"),
):
    """
    Process login form submission.
    On success: set HttpOnly session + refresh cookies, redirect to next_url.
    On failure: re-render login page with error message.
    """
    from urllib.parse import urlparse
    from app.modules.auth.token_store import create_refresh_token

    db = SessionLocal()
    try:
        user = auth_service.authenticate_user(db, staff_id, password)

        if not user:
            return templates.TemplateResponse(
                request,
                "login.html",
                {
                    "request": request,
                    "next_url": next_url,
                    "error": "Invalid Staff ID or password. Please try again.",
                },
                status_code=401,
            )

        token = auth_service.create_access_token(user)
        refresh_raw = create_refresh_token(db, user.id, settings.refresh_token_expire_days)
    finally:
        db.close()

    # Reject protocol-relative URLs (//evil.com passes startswith("/") naively)
    def _safe_redirect(url: str) -> bool:
        if not url or not url.startswith("/") or url.startswith("//"):
            return False
        parsed = urlparse(url)
        return not parsed.netloc and not parsed.scheme

    safe_next = next_url if _safe_redirect(next_url) else "/home"
    if safe_next in ("/login", "/register"):
        safe_next = "/home"

    response = RedirectResponse(url=safe_next, status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.access_token_expire_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_raw,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/auth/refresh",
    )
    return response


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        request,
        "forgot_password.html",
        {"request": request, "message": None, "error": None, "reset_token": None},
    )


@router.post("/forgot-password", response_class=HTMLResponse)
def forgot_password_submit(
    request: Request,
    staff_id: str = Form(default=""),
    email: str = Form(default=""),
):
    detail = (
        "If the account exists, password reset instructions are available. "
        "Please check your email or contact an administrator."
    )
    reset_token = None
    db = SessionLocal()
    try:
        user = users_service.get_user_by_staff_id(db, staff_id) if staff_id.strip() else None
        if user is None and email.strip():
            user = users_service.get_user_by_email(db, email)
        if user and user.is_active:
            reset_token = create_password_reset_token(db, user.id)
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "forgot_password.html",
        {
            "request": request,
            "message": detail,
            "error": None,
            "reset_token": reset_token if settings.env != "production" else None,
        },
    )


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str = ""):
    return templates.TemplateResponse(
        request,
        "reset_password.html",
        {"request": request, "token": token, "message": None, "error": None},
    )


@router.post("/reset-password", response_class=HTMLResponse)
def reset_password_submit(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    if new_password != confirm_password:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {
                "request": request,
                "token": token,
                "message": None,
                "error": "Passwords do not match.",
            },
            status_code=400,
        )

    db = SessionLocal()
    try:
        record = verify_password_reset_token(db, token)
        if not record:
            return templates.TemplateResponse(
                request,
                "reset_password.html",
                {
                    "request": request,
                    "token": token,
                    "message": None,
                    "error": "Password reset link is invalid or has expired.",
                },
                status_code=400,
            )
        user = users_service.get_user_by_id(db, record.user_id)
        if not user or not user.is_active:
            return templates.TemplateResponse(
                request,
                "reset_password.html",
                {
                    "request": request,
                    "token": token,
                    "message": None,
                    "error": "Password reset link is invalid or has expired.",
                },
                status_code=400,
            )
        users_service.update_password_hash(db, user, auth_service.hash_password(new_password))
        mark_password_reset_token_used(db, record)
        set_revocation_fence(db, user.id)
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "reset_password.html",
        {
            "request": request,
            "token": "",
            "message": "Password has been reset. Please log in with your new password.",
            "error": None,
        },
    )


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(
        request,
        "register.html",
        {"request": request, "error": None, "success": None},
    )


@router.post("/register-ui", response_class=HTMLResponse)
async def register_ui(
    request: Request,
    staff_id: str = Form(...),
    email: str | None = Form(None),
    full_name: str = Form(...),
    password: str = Form(...),
    role: str = Form("user"),
):
    payload = {
        "staff_id": staff_id,
        "email": email if email else None,
        "full_name": full_name,
        "password": password,
        "role": role,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{settings.api_base}/auth/register", json=payload)
            if response.status_code == 201:
                return templates.TemplateResponse(
                    request,
                    "register.html",
                    {
                        "request": request,
                        "error": None,
                        "success": "Account created successfully! You can now sign in.",
                    },
                )

            raw_detail = "Registration failed. Please try again."
            try:
                body = response.json()
                raw_detail = body.get("detail", raw_detail)
            except Exception:
                pass

            return templates.TemplateResponse(
                request,
                "register.html",
                {
                    "request": request,
                    "error": _format_api_error(raw_detail),
                    "success": None,
                },
                status_code=response.status_code,
            )
        except Exception:
            return templates.TemplateResponse(
                request,
                "register.html",
                {
                    "request": request,
                    "error": "Unable to reach the server. Please try again shortly.",
                    "success": None,
                },
                status_code=500,
            )


@router.post("/login-ui")
async def login_ui(
    request: Request,
    staff_id: str = Form(...),
    password: str = Form(...),
):
    payload = {
        "staff_id": staff_id,
        "password": password,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{settings.api_base}/auth/login", json=payload)
            if response.status_code != 200:
                # 401 → wrong credentials; anything else → server/validation issue
                if response.status_code == 401:
                    login_error = "Incorrect Staff ID or password. Please try again."
                else:
                    raw_detail = "Sign-in failed. Please try again."
                    try:
                        body = response.json()
                        raw_detail = body.get("detail", raw_detail)
                    except Exception:
                        pass
                    login_error = _format_api_error(raw_detail)

                return templates.TemplateResponse(
                    request,
                    "login.html",
                    {"request": request, "error": login_error},
                    status_code=response.status_code,
                )

            body = response.json()
            access_token = body["access_token"]
            refresh_token = body.get("refresh_token", "")

            redirect = RedirectResponse(url="/home", status_code=303)
            redirect.set_cookie(
                key="access_token", value=access_token,
                httponly=True, samesite="lax", secure=settings.cookie_secure,
                max_age=body.get("expires_in", settings.access_token_expire_minutes * 60),
            )
            if refresh_token:
                redirect.set_cookie(
                    key="refresh_token", value=refresh_token,
                    httponly=True, samesite="lax", secure=settings.cookie_secure,
                    max_age=settings.refresh_token_expire_days * 86400,
                    path="/auth/refresh",
                )
            return redirect

        except Exception:
            return templates.TemplateResponse(
                request,
                "login.html",
                {"request": request, "error": "Unable to reach the server. Please try again shortly."},
                status_code=500,
            )


@router.get("/logout")
def logout(request: Request):
    """
    Revoke the current session (blacklist access token JTI, revoke refresh
    token) then redirect to the login page.
    """
    from datetime import timezone as _tz
    from app.modules.auth.service import decode_access_token
    from app.modules.auth.token_store import blacklist_jti, revoke_refresh_token
    from app.core.db import session_scope

    access_raw = request.cookies.get("access_token")
    refresh_raw = request.cookies.get("refresh_token")

    try:
        with session_scope() as db:
            if access_raw:
                payload = decode_access_token(access_raw)
                if payload:
                    jti = payload.get("jti")
                    user_id = payload.get("user_id")
                    exp_raw = payload.get("exp")
                    if jti and user_id and exp_raw:
                        from datetime import datetime
                        exp_dt = datetime.fromtimestamp(
                            exp_raw if isinstance(exp_raw, (int, float)) else exp_raw.timestamp(),
                            tz=_tz.utc,
                        )
                        blacklist_jti(db, jti, user_id, exp_dt)
            if refresh_raw:
                revoke_refresh_token(db, refresh_raw)
    except Exception:
        pass  # revocation is best-effort; never block logout

    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/auth/refresh")
    return response


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return RedirectResponse(url="/home", status_code=301)


@router.get("/home", response_class=HTMLResponse)
async def home_page(request: Request, current_user=Depends(require_ui_login)):
    """Home / Dashboard landing page — renders the new index.html template."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request":   request,
            "user":      current_user,
            "full_name": current_user.full_name,
            "role":      current_user.role,
        },
    )


@router.get("/documents-ui", response_class=HTMLResponse)
async def documents_page_redirect(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    query = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(url=f"/documents/vault{query}", status_code=301)




@router.get("/documents-ui/{document_id}", response_class=HTMLResponse)
async def document_detail_page(request: Request, document_id: int, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    document = None
    error = None
    document_text = ""
    entities: list = []
    entities_by_type: dict = {}

    headers = _auth_headers_from_cookie(request)
    base = settings.api_base

    async with httpx.AsyncClient(timeout=60.0) as client:
        # ── Fetch document metadata ─────────────────────────────────────────
        try:
            resp = await client.get(
                f"{base}/api/documents/{document_id}", headers=headers
            )
            if resp.status_code == 200:
                document = resp.json()
            else:
                try:
                    error = resp.json().get("detail", "Failed to load document.")
                except Exception:
                    error = "Failed to load document."
        except Exception as exc:
            error = str(exc)

        if document:
            # ── Fetch extracted text (for entity highlighting) ──────────────
            try:
                text_resp = await client.get(
                    f"{base}/api/documents/{document_id}/text", headers=headers
                )
                if text_resp.status_code == 200:
                    document_text = text_resp.json().get("text", "")
            except Exception:
                document_text = ""   # non-fatal; highlight panel just won't render

            # ── Fetch extracted entities ────────────────────────────────────
            try:
                ent_resp = await client.get(
                    f"{base}/api/documents/{document_id}/entities", headers=headers
                )
                if ent_resp.status_code == 200:
                    ent_body = ent_resp.json()
                    entities = ent_body.get("entities", [])
                    entities_by_type = ent_body.get("entities_by_type", {})
            except Exception:
                entities = []   # non-fatal; entity panel will show "Run extraction"

    return templates.TemplateResponse(
        request,
        "documents/detail.html",
        {
            "request":          request,
            "user":             current_user,
            "document":         document,
            "error":            error,
            "document_text":    document_text,
            "entities":         entities,
            "entities_by_type": entities_by_type,
            "full_name":        current_user.full_name,
            "role":             current_user.role,
        },
    )


@router.post("/documents-ui/{document_id}/update", response_class=HTMLResponse)
async def update_document_ui(
    request: Request,
    document_id: int,
    title: str = Form(...),
    status_value: str = Form(...),
    document_category: str | None = Form(None),
    notes: str | None = Form(None),
):
    access_token = request.cookies.get("access_token")
    if not access_token:
        return RedirectResponse(url="/", status_code=303)

    payload = {
        "title": title,
        "status": status_value,
        "document_category": document_category if document_category else None,
        "notes": notes if notes else None,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(
                f"{settings.api_base}/api/documents/{document_id}",
                json=payload,
                headers=_auth_headers_from_cookie(request),
            )
        except Exception:
            response = None

    if response is not None and response.status_code == 200:
        return RedirectResponse(url=f"/documents-ui/{document_id}", status_code=303)

    detail = "Failed to update document."
    if response is not None:
        try:
            body = response.json()
            detail = body.get("detail", detail)
        except Exception:
            pass

    document = None
    async with httpx.AsyncClient() as client:
        try:
            doc_response = await client.get(
                f"{settings.api_base}/api/documents/{document_id}",
                headers=_auth_headers_from_cookie(request),
            )
            if doc_response.status_code == 200:
                document = doc_response.json()
        except Exception:
            document = None

    return templates.TemplateResponse(
        request,
        "documents/detail.html",
        {
            "request": request,
            "document": document,
            "error": detail,
            "full_name": request.cookies.get("full_name"),
            "role": request.cookies.get("role"),
        },
        status_code=400,
    )


@router.post("/documents-ui/{document_id}/archive")
async def archive_document_ui(request: Request, document_id: int):
    access_token = request.cookies.get("access_token")
    if not access_token:
        return RedirectResponse(url="/", status_code=303)

    async with httpx.AsyncClient() as client:
        try:
            await client.put(
                f"{settings.api_base}/api/documents/{document_id}/archive",
                headers=_auth_headers_from_cookie(request),
            )
        except Exception:
            pass

    return RedirectResponse(url=f"/documents-ui/{document_id}", status_code=303)


@router.post("/documents-ui/{document_id}/restore")
async def restore_document_ui(request: Request, document_id: int):
    access_token = request.cookies.get("access_token")
    if not access_token:
        return RedirectResponse(url="/", status_code=303)

    async with httpx.AsyncClient() as client:
        try:
            await client.put(
                f"{settings.api_base}/api/documents/{document_id}/restore",
                headers=_auth_headers_from_cookie(request),
            )
        except Exception:
            pass

    return RedirectResponse(url=f"/documents-ui/{document_id}", status_code=303)


@router.get("/upload-ui", response_class=HTMLResponse)
async def upload_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return RedirectResponse(url="/documents/upload", status_code=301)


@router.post("/upload-ui", response_class=HTMLResponse)
async def upload_ui(
    request: Request,
    title: str = Form(...),
    uploaded_by_user_id: int | None = Form(None),
    document_category: str | None = Form(None),
    notes: str | None = Form(None),
    status_value: str = Form("uploaded"),
    file: UploadFile = File(...),
    current_user=Depends(require_ui_login),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    form_data = {
        "title": title,
        "uploaded_by_user_id": str(uploaded_by_user_id or current_user.id),
        "document_category": document_category or "",
        "notes": notes or "",
        "status_value": status_value,
    }

    files = {
        "file": (
            file.filename or "document",
            await file.read(),
            file.content_type or "application/octet-stream",
        )
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.api_base}/api/documents/upload",
                data=form_data,
                files=files,
                headers=_auth_headers_from_cookie(request),
            )

            if response.status_code == 201:
                return templates.TemplateResponse(
                    request,
                    "upload.html",
                    {
                        "request": request,
                        "error": None,
                        "success": "Document uploaded successfully.",
                        "user_id": current_user.id,
                        "full_name": current_user.full_name,
                    },
                )

            detail = "Upload failed."
            try:
                body = response.json()
                detail = body.get("detail", detail)
            except Exception:
                pass

            return templates.TemplateResponse(
                request,
                "upload.html",
                {
                    "request": request,
                    "error": detail,
                    "success": None,
                    "user_id": current_user.id,
                    "full_name": current_user.full_name,
                },
                status_code=response.status_code,
            )

        except Exception as exc:
            return templates.TemplateResponse(
                request,
                "upload.html",
                {
                    "request": request,
                    "error": str(exc),
                    "success": None,
                    "user_id": current_user.id,
                    "full_name": current_user.full_name,
                },
                status_code=500,
            )


# ---------------------------------------------------------------------------
# Analytics redirect — /analytics → /analysis (301 permanent)
# ---------------------------------------------------------------------------

@router.get("/analytics")
async def analytics_redirect():
    return RedirectResponse(url="/analysis", status_code=301)


# ---------------------------------------------------------------------------
# Financial Position
# ---------------------------------------------------------------------------

@router.get("/financial-position", response_class=HTMLResponse)
async def financial_position_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    insurers = []
    risk_scores = []
    circular_analyses = []

    async with httpx.AsyncClient() as client:
        try:
            ins_resp = await client.get(
                f"{settings.api_base}/insurers",
                headers=_auth_headers_from_cookie(request),
            )
            if ins_resp.status_code == 200:
                insurers = ins_resp.json()
        except Exception:
            insurers = []

    db = SessionLocal()
    try:
        circular_analyses = circular_service.list_analyses(db, skip=0, limit=50)
    except Exception:
        circular_analyses = []
    finally:
        db.close()

    premiums = [
        float(ins.get("gross_written_premium"))
        for ins in insurers
        if isinstance(ins, dict) and ins.get("gross_written_premium") is not None
    ]
    solvencies = [
        float(ins.get("solvency_ratio"))
        for ins in insurers
        if isinstance(ins, dict) and ins.get("solvency_ratio") is not None
    ]
    risk_values = [
        float(ins.get("wcs_score"))
        for ins in insurers
        if isinstance(ins, dict) and ins.get("wcs_score") is not None
    ]
    financial_kpis = {
        "total_market_gwp": sum(premiums) if premiums else None,
        "avg_solvency_ratio": (sum(solvencies) / len(solvencies)) if solvencies else None,
        "avg_risk_score": (sum(risk_values) / len(risk_values)) if risk_values else None,
        "insurers_monitored": len(insurers),
        "has_financial_data": bool(premiums or solvencies or risk_values),
    }

    return templates.TemplateResponse(
        request,
        "intelligence/financial_position.html",
        {
            "request":          request,
            "user":             current_user,
            "full_name":        current_user.full_name,
            "role":             current_user.role,
            "insurers":         insurers,
            "risk_scores":      risk_scores,
            "financial_kpis":    financial_kpis,
            "circular_analyses": circular_analyses,
        },
    )


# ---------------------------------------------------------------------------
# Advisory
# ---------------------------------------------------------------------------

@router.get("/advisory", response_class=HTMLResponse)
async def advisory_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return RedirectResponse(url="/intelligence/advisory", status_code=301)


@router.get("/advisory/api/{insurer_id}", response_class=JSONResponse)
async def advisory_api(request: Request, insurer_id: int):
    access_token = request.cookies.get("access_token")
    if not access_token:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    insurer_name = ""
    async with httpx.AsyncClient() as client:
        try:
            ins_resp = await client.get(
                f"{settings.api_base}/insurers/{insurer_id}",
                headers=_auth_headers_from_cookie(request),
            )
            if ins_resp.status_code == 200:
                ins = ins_resp.json()
                insurer_name = ins.get("name", "")
        except Exception:
            pass

    db = SessionLocal()
    try:
        result = generate_advisory(insurer_id=insurer_id, db=db, insurer_name=insurer_name)
    except Exception as exc:
        result = {"error": str(exc)}
    finally:
        db.close()

    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@router.get("/report", response_class=HTMLResponse)
async def report_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    insurers = []
    risk_scores = []
    circular_analyses = []

    async with httpx.AsyncClient() as client:
        try:
            ins_resp = await client.get(
                f"{settings.api_base}/insurers",
                headers=_auth_headers_from_cookie(request),
            )
            if ins_resp.status_code == 200:
                insurers = ins_resp.json()
        except Exception:
            insurers = []

        risk_scores = [
            {
                "insurer_id": ins.get("id"),
                "name": ins.get("name"),
                "fused_score": ins.get("wcs_score"),
                "fused_label": ins.get("wcs_band"),
                "source": "wcs",
            }
            for ins in insurers
            if isinstance(ins, dict) and ins.get("wcs_score") is not None
        ]

    db = SessionLocal()
    try:
        circular_analyses = circular_service.list_analyses(db, skip=0, limit=50)
    except Exception:
        circular_analyses = []
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "reports/legacy.html",
        {
            "request":           request,
            "user":              current_user,
            "full_name":         current_user.full_name,
            "role":              current_user.role,
            "insurers":          insurers,
            "risk_scores":       risk_scores,
            "circular_analyses": circular_analyses,
        },
    )


# ---------------------------------------------------------------------------
# News UI
# ---------------------------------------------------------------------------

@router.get("/news-ui", response_class=HTMLResponse)
async def news_ui_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return RedirectResponse(url="/reports/news", status_code=301)


# ---------------------------------------------------------------------------
# ML UI (redirect to index / ML dashboard)
# ---------------------------------------------------------------------------

@router.get("/ml-ui", response_class=HTMLResponse)
async def ml_ui_page(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        return RedirectResponse(url="/", status_code=303)
    return RedirectResponse(url="/analytics", status_code=302)



# ---------------------------------------------------------------------------
# Risk Alerts (intel news feed filtered by risk label)
# ---------------------------------------------------------------------------

@router.get("/alerts-ui", response_class=HTMLResponse)
async def alerts_ui_page(request: Request, current_user=Depends(require_ui_login), risk_label: str | None = None):
    if isinstance(current_user, RedirectResponse):
        return current_user

    import json as _json
    from app.modules.intel.repo import query_articles, count_by_risk

    articles   = []
    risk_counts = {}
    db = SessionLocal()
    try:
        articles = query_articles(
            db,
            risk_label=risk_label,
            limit=120,
        )
        if not risk_label:
            # Show only risk-labelled articles (exclude Neutral)
            articles = [
                a for a in query_articles(db, limit=200)
                if a.risk_label in ("Regulatory Risk", "Claims Alert", "Market Risk")
            ]
        risk_counts = count_by_risk(db)
    except Exception:
        articles    = []
        risk_counts = {}
    finally:
        db.close()

    # Convert ORM objects to dicts and decode topics
    article_dicts = []
    for a in articles:
        d = {c.name: getattr(a, c.name) for c in a.__table__.columns}
        try:
            d["topics"] = _json.loads(d.get("topics_json") or "[]")
        except Exception:
            d["topics"] = []
        article_dicts.append(d)

    return templates.TemplateResponse(
        request,
        "intelligence/alerts.html",
        {
            "request":      request,
            "user":         current_user,
            "active_page":  "alerts-ui",
            "full_name":    current_user.full_name,
            "role":         current_user.role,
            "articles":     article_dicts,
            "risk_filter":  risk_label or "",
            "risk_counts":  risk_counts,
        },
    )


# ---------------------------------------------------------------------------
# Insurers Intel (ZIM insurer registry)
# ---------------------------------------------------------------------------

@router.get("/insurers-intel", response_class=HTMLResponse)
async def insurers_intel_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return RedirectResponse(url="/intelligence/insurers", status_code=301)


# ---------------------------------------------------------------------------
# Insurer Intelligence Dashboard
# ---------------------------------------------------------------------------

@router.get("/insurer-intelligence", response_class=HTMLResponse)
async def insurer_intelligence_page(request: Request, current_user=Depends(require_ui_login)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    return RedirectResponse(url="/intelligence/insurers", status_code=301)


@router.get("/insurer-intelligence/{insurer_id}", response_class=HTMLResponse)
async def insurer_profile_partial(request: Request, insurer_id: int, current_user=Depends(require_ui_login)):
    """Returns the insurer profile panel HTML (loaded via AJAX)."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    from app.modules.insurers.analytics_service import InsurerAnalytics
    db = SessionLocal()
    try:
        profile = InsurerAnalytics().get_insurer_profile(db, insurer_id)
    except Exception as exc:
        profile = {}
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "partials/insurer_profile_panel.html",
        {
            "request": request,
            "user": current_user,
            "profile": profile,
        },
    )
