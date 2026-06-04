"""
Reports router — POST /api/reports/generate

Generates executive, detailed, or compliance PDF reports for a document.
Uses WeasyPrint to render HTML → PDF. Returns application/pdf binary.

Also provides:
    GET /api/reports/sandbox-quarterly/{broker_id}
        Renders a Sandbox Quarterly Progress Report (Annexure 3).

WeasyPrint must be installed: pip install weasyprint
"""
from __future__ import annotations

import logging
import re
from contextlib import redirect_stderr, redirect_stdout
from html.parser import HTMLParser
from io import BytesIO, StringIO
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from pydantic import BaseModel
from sqlalchemy.orm import Session

WeasyPrintHTML: Any | None = None
_WEASYPRINT_IMPORT_ERROR: Exception | None = None
_WEASYPRINT_IMPORT_ATTEMPTED = False

from app.core.db import get_db
from app.modules.documents import service as doc_service
from app.modules.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/reports",
    tags=["reports"],
    dependencies=[Depends(get_current_user)],
)


# ─── Request / Response schemas ──────────────────────────────────────────────

class _ReportTextParser(HTMLParser):
    """Extract readable text blocks from simple report HTML."""

    _BLOCK_TAGS = {"br", "div", "h1", "h2", "h3", "li", "p", "section", "table", "tr"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._parts.append(text)

    def text(self) -> str:
        raw = " ".join(self._parts)
        raw = re.sub(r"[ \t\r\f\v]+", " ", raw)
        raw = re.sub(r"\n\s+", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _extract_report_text(html_content: str) -> str:
    parser = _ReportTextParser()
    parser.feed(html_content)
    return parser.text() or "No report content was available."


def _html_to_pdf_with_reportlab(html_content: str) -> bytes:
    from reportlab.lib.pagesizes import A4  # noqa: PLC0415
    from reportlab.lib.styles import getSampleStyleSheet  # noqa: PLC0415
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer  # noqa: PLC0415

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=48, rightMargin=48)
    styles = getSampleStyleSheet()
    story = []

    for index, block in enumerate(_extract_report_text(html_content).splitlines()):
        block = block.strip()
        if not block:
            story.append(Spacer(1, 8))
            continue
        style = styles["Title"] if index == 0 else styles["BodyText"]
        story.append(Paragraph(_esc(block), style))
        story.append(Spacer(1, 6))

    doc.build(story)
    return buffer.getvalue()


def _get_weasyprint_html() -> Any | None:
    global WeasyPrintHTML, _WEASYPRINT_IMPORT_ATTEMPTED, _WEASYPRINT_IMPORT_ERROR

    if _WEASYPRINT_IMPORT_ATTEMPTED:
        return WeasyPrintHTML

    _WEASYPRINT_IMPORT_ATTEMPTED = True
    try:
        quiet_output = StringIO()
        with redirect_stdout(quiet_output), redirect_stderr(quiet_output):
            from weasyprint import HTML  # noqa: PLC0415
        WeasyPrintHTML = HTML
        _WEASYPRINT_IMPORT_ERROR = None
    except (ImportError, OSError) as exc:  # pragma: no cover - environment-dependent
        WeasyPrintHTML = None
        _WEASYPRINT_IMPORT_ERROR = exc
    return WeasyPrintHTML


def _html_to_pdf(html_content: str) -> bytes:
    """Render report HTML to PDF with WeasyPrint, falling back on ReportLab."""
    try:
        renderer = _get_weasyprint_html()
        if renderer is not None:
            return renderer(string=html_content).write_pdf()
        logger.warning(
            "Using ReportLab PDF fallback because WeasyPrint is unavailable: %s",
            _WEASYPRINT_IMPORT_ERROR,
        )
        return _html_to_pdf_with_reportlab(html_content)
    except Exception as exc:
        logger.exception("PDF generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {exc}",
        ) from exc


class ReportRequest(BaseModel):
    """Request body for POST /api/reports/generate."""
    document_id: int
    report_type: str = "executive"   # executive | detailed | compliance


# ─── Report renderer ─────────────────────────────────────────────────────────

def _build_html(
    document_id: int,
    report_type: str,
    doc_meta: dict,
    text_content: str,
) -> str:
    """
    Build the HTML source that WeasyPrint will convert to PDF.
    Embedded CSS ensures clean typography even without external fonts.
    """
    type_label = {
        "executive":  "Executive Summary Report",
        "detailed":   "Detailed Policy Analysis Report",
        "compliance": "IPEC Compliance Report",
    }.get(report_type, "Insurance Document Report")

    doc_name = doc_meta.get("title") or doc_meta.get("original_filename") or f"Document #{document_id}"
    category = doc_meta.get("document_category") or "Uncategorised"
    status   = doc_meta.get("status") or "Unknown"

    # Text preview (first 3000 chars for executive; full for detailed)
    preview = text_content[:3000] if report_type == "executive" else text_content[:8000]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Arial, Helvetica, sans-serif; font-size: 12px; color: #111;
         margin: 0; padding: 0; }}
  .page-wrap {{ padding: 40px 50px; }}
  .header {{ border-bottom: 3px solid #d4af37; padding-bottom: 16px; margin-bottom: 24px; }}
  .header h1 {{ font-size: 20px; margin: 0; color: #0f0f0f; }}
  .header p  {{ margin: 4px 0 0; font-size: 11px; color: #555; }}
  .badge {{ display:inline-block; background:#d4af3720; border:1px solid #d4af37;
            border-radius:4px; padding:2px 8px; font-size:10px;
            font-weight:700; text-transform:uppercase; color:#8b7314; }}
  .section {{ margin-bottom:20px; }}
  .section h2 {{ font-size:14px; border-left:4px solid #d4af37;
                 padding-left:8px; margin:0 0 8px; color:#1a1a1a; }}
  table {{ width:100%; border-collapse:collapse; font-size:11px; }}
  th {{ background:#f5f5f5; padding:6px 10px; text-align:left; font-size:10px;
        text-transform:uppercase; letter-spacing:0.06em; }}
  td {{ padding:6px 10px; border-bottom:1px solid #eee; }}
  .text-preview {{ background:#f9f9f9; padding:12px; border-radius:4px;
                   font-size:11px; line-height:1.7; white-space:pre-wrap;
                   max-height:400px; overflow:hidden; border:1px solid #eee; }}
  .footer {{ margin-top:32px; border-top:1px solid #ddd; padding-top:12px;
             font-size:10px; color:#888; text-align:center; }}
  @page {{ margin: 0; }}
</style>
</head>
<body>
<div class="page-wrap">

  <!-- Header -->
  <div class="header">
    <h1>InsureIntel Zimbabwe</h1>
    <p>{type_label}</p>
    <p>Generated: <strong>{_today()}</strong> &nbsp;·&nbsp;
       IPEC-Regulated Brokerage Intelligence Platform</p>
  </div>

  <!-- Document info -->
  <div class="section">
    <h2>Document Information</h2>
    <table>
      <tr><th>Title</th><td>{_esc(doc_name)}</td></tr>
      <tr><th>Document ID</th><td>{document_id}</td></tr>
      <tr><th>Category</th><td>{_esc(category)}</td></tr>
      <tr><th>Processing Status</th><td>{_esc(status)}</td></tr>
      <tr><th>Report Type</th><td>{_esc(report_type.title())}</td></tr>
    </table>
  </div>

  {"<!-- Executive note -->" if report_type == "executive" else ""}
  {f'<div class="section"><h2>Executive Summary</h2><p>This executive summary covers the key findings from document <strong>{_esc(doc_name)}</strong>. The document has been processed and classified as <strong>{_esc(category)}</strong>.</p></div>' if report_type == "executive" else ""}

  <!-- Text content -->
  <div class="section">
    <h2>{"Document Preview" if report_type == "executive" else "Document Content"}</h2>
    <div class="text-preview">{_esc(preview) or "No extracted text available for this document."}</div>
  </div>

  <!-- Compliance note for compliance reports -->
  {f'<div class="section"><h2>IPEC Compliance Note</h2><p>This report was generated for compliance review purposes under the Zimbabwe Insurance Act [Chapter 24:07] and applicable IPEC supervisory directives. Please refer to the full compliance check results in the InsureIntel platform for detailed findings.</p></div>' if report_type == "compliance" else ""}

  <!-- Footer -->
  <div class="footer">
    InsureIntel Zimbabwe &nbsp;·&nbsp; Powered by AI Insurance Intelligence &nbsp;·&nbsp;
    Document ID #{document_id} &nbsp;·&nbsp; {_today()}
  </div>

</div>
</body>
</html>"""


def _today() -> str:
    """Return today's date as DD/MM/YYYY."""
    from datetime import date
    return date.today().strftime("%d/%m/%Y")


def _esc(s: str) -> str:
    """HTML-escape a string for safe injection into report HTML."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ─── Endpoint ────────────────────────────────────────────────────────────────

@router.post("/generate")
async def generate_report(
    payload: ReportRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    Generate a PDF report for a given document.

    Steps:
    1. Validate document exists.
    2. Retrieve extracted text (if processed).
    3. Build HTML template with document metadata + text.
    4. Convert HTML → PDF via WeasyPrint.
    5. Stream the PDF back as application/pdf.

    Args:
        payload: ReportRequest with document_id and report_type.
        db:      SQLAlchemy database session (injected).

    Returns:
        StreamingResponse of application/pdf binary.

    Raises:
        HTTPException 404 if document not found.
        HTTPException 500 if PDF generation fails.
    """
    # ── Validate report type ──────────────────────────────────────────────────
    if payload.report_type not in ("executive", "detailed", "compliance"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="report_type must be one of: executive, detailed, compliance",
        )

    # ── Fetch document ────────────────────────────────────────────────────────
    doc = doc_service.get_document_by_id(db, payload.document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    doc_meta = {
        "title":              doc.title,
        "original_filename":  doc.original_filename,
        "document_category":  doc.document_category,
        "status":             doc.status,
    }

    # ── Fetch extracted text ──────────────────────────────────────────────────
    text_content = ""
    try:
        from app.modules.documents.ingestion import extract_text  # noqa: PLC0415
        text_content = extract_text(doc.file_path) or ""
    except Exception as exc:
        logger.warning("Could not extract text for report (doc %s): %s", payload.document_id, exc)

    # ── Build HTML ────────────────────────────────────────────────────────────
    html_content = _build_html(
        document_id=payload.document_id,
        report_type=payload.report_type,
        doc_meta=doc_meta,
        text_content=text_content,
    )

    # ── Convert to PDF ────────────────────────────────────────────────────────
    pdf_bytes = _html_to_pdf(html_content)

    filename = f"insure_intel_{payload.report_type}_{payload.document_id}.pdf"
    return StreamingResponse(
        content=BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Sandbox Quarterly Report ─────────────────────────────────────────────────

# Locate the templates directory relative to this file so the Jinja env is
# independent of the working directory when the app starts.
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "ui" / "templates"

# Use Starlette's Jinja2Templates — automatically injects `request` into context
_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/sandbox-quarterly/{broker_id}", response_model=None)
async def get_sandbox_quarterly_report(
    request: Request,
    broker_id: int,
    quarter: str = Query(default="Q2-2026", description="Quarter e.g. Q2-2026"),
    format: str = Query(default="html", description="html or pdf"),
    db: Session = Depends(get_db),
):
    """
    Generate a Sandbox Quarterly Progress Report for a broker.

    Query parameters:
        quarter : str — quarter in Q2-2026 format (default Q2-2026)
        format  : str — "html" returns rendered HTML; "pdf" returns PDF bytes

    The report follows IPEC Regulatory Sandbox Guidelines (2025) Annexure 3
    and is rendered from sandbox_quarterly_report.html using Jinja2.

    Dissertation Methodology Note (Chapter 3):
    WeasyPrint is used for PDF generation because it natively supports CSS
    variables and the glassmorphism design tokens used across the InsureIntel
    template system, producing print-quality output without additional tooling.

    References:
        IPEC (2025). Regulatory Sandbox Guidelines for the Insurance and
        Pensions Industry. Insurance and Pensions Commission of Zimbabwe.
        Effective Q4 2025. Retrieved from ipec.co.zw.
    """
    from app.modules.reports.sandbox_report_service import (  # noqa: PLC0415
        generate_sandbox_quarterly_report_context,
    )

    # ── Build template context from DB aggregation ────────────────────────────
    try:
        context = generate_sandbox_quarterly_report_context(
            broker_id=broker_id,
            quarter=quarter,
            db=db,
        )
    except Exception as exc:
        logger.exception("Failed to build sandbox quarterly report context: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {exc}",
        )

    # ── Render HTML from Jinja2 template ─────────────────────────────────────
    # base.html uses `request.url.path` for nav active state — must be in context.
    # Starlette >=0.29 requires request as first positional arg.
    context["request"] = request

    try:
        html_content = _templates.get_template(
            "reports/sandbox_quarterly_report.html"
        ).render(**context)
    except Exception as exc:
        logger.exception("Jinja2 rendering failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template rendering failed: {exc}",
        )

    # ── Return HTML or PDF ────────────────────────────────────────────────────
    if format.lower() == "pdf":
        # Convert rendered HTML → PDF using the same WeasyPrint pattern as /generate
        pdf_bytes = _html_to_pdf(html_content)

        filename = f"sandbox_quarterly_{broker_id}_{quarter}.pdf"
        return StreamingResponse(
            content=BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # Default: return rendered HTML
    return HTMLResponse(content=html_content, status_code=200)
