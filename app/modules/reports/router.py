"""
Reports router — POST /api/reports/generate

Generates executive, detailed, or compliance PDF reports for a document.
Uses WeasyPrint to render HTML → PDF. Returns application/pdf binary.

WeasyPrint must be installed: pip install weasyprint
"""
from __future__ import annotations

import logging
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

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
    try:
        from weasyprint import HTML  # noqa: PLC0415
        pdf_bytes = HTML(string=html_content).write_pdf()
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WeasyPrint is not installed. Run: pip install weasyprint",
        )
    except Exception as exc:
        logger.exception("PDF generation failed for doc %s: %s", payload.document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {exc}",
        )

    filename = f"insure_intel_{payload.report_type}_{payload.document_id}.pdf"
    return StreamingResponse(
        content=BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
