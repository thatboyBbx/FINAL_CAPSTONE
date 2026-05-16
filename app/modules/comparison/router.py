"""
Comparison Router — /api/comparison endpoints.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/comparison",
    tags=["comparison"],
    dependencies=[Depends(get_current_user)],
)


class CompareRequest(BaseModel):
    document_a_id: int | None = None
    document_b_id: int | None = None
    doc_a_id: int | None = None
    doc_b_id: int | None = None

    def resolved_ids(self) -> tuple[int, int]:
        doc_a_id = self.document_a_id if self.document_a_id is not None else self.doc_a_id
        doc_b_id = self.document_b_id if self.document_b_id is not None else self.doc_b_id
        if doc_a_id is None or doc_b_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide both document_a_id/document_b_id or doc_a_id/doc_b_id.",
            )
        return doc_a_id, doc_b_id


@router.post("/compare")
def compare_documents(
    payload: CompareRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Trigger a clause-by-clause comparison between two documents.
    Creates a pending comparison record and runs the comparison in background.
    Returns immediately with comparison_id and status='processing'.
    """
    from app.modules.comparison.model import DocumentComparison
    from app.modules.documents.model import Document

    document_a_id, document_b_id = payload.resolved_ids()

    # Validate both documents exist
    for doc_id in (document_a_id, document_b_id):
        if not db.query(Document).filter(Document.id == doc_id).first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document id={doc_id} not found.",
            )

    # Create a pending comparison row
    comp = DocumentComparison(
        document_a_id=document_a_id,
        document_b_id=document_b_id,
        status="processing",
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)
    comp_id = comp.id

    # Run the actual comparison in background
    background_tasks.add_task(_run_comparison, comp_id, document_a_id, document_b_id)

    return {"comparison_id": comp_id, "status": "processing"}


def _run_comparison(comp_id: int, doc_a_id: int, doc_b_id: int) -> None:
    """Background task: run comparison and update the DB row."""
    from app.core.db import SessionLocal
    from app.modules.comparison.service import ComparisonService
    from app.modules.comparison.model import DocumentComparison

    db = SessionLocal()
    try:
        service = ComparisonService()
        report = service.compare(doc_a_id, doc_b_id, db)
        # The report is already saved inside compare(); update status
        comp = db.query(DocumentComparison).filter(DocumentComparison.id == comp_id).first()
        if comp:
            comp.status = "complete"
            db.commit()
    except Exception as exc:
        logger.error("Comparison %d failed: %s", comp_id, exc)
        try:
            comp = db.query(DocumentComparison).filter(DocumentComparison.id == comp_id).first()
            if comp:
                comp.status = "failed"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.get("/{comparison_id}")
def get_comparison(
    comparison_id: int, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Retrieve a stored comparison report by ID."""
    from app.modules.comparison.model import DocumentComparison

    comp = db.query(DocumentComparison).filter(DocumentComparison.id == comparison_id).first()
    if not comp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison id={comparison_id} not found.",
        )
    return {
        "comparison_id": comp.id,
        "document_a_id": comp.document_a_id,
        "document_b_id": comp.document_b_id,
        "status": comp.status,
        "summary": comp.summary,
        "coverage_changes": comp.coverage_changes,
        "exclusion_changes": comp.exclusion_changes,
        "high_risk_changes": comp.high_risk_changes,
        "overall_similarity_score": comp.overall_similarity_score,
        "created_at": comp.created_at.isoformat() if comp.created_at else None,
        "completed_at": comp.completed_at.isoformat() if comp.completed_at else None,
    }


@router.get("/document/{document_id}")
def get_comparisons_for_document(
    document_id: int, db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Return all comparisons where document_id is either document A or B."""
    from app.modules.comparison.model import DocumentComparison

    comps = (
        db.query(DocumentComparison)
        .filter(
            (DocumentComparison.document_a_id == document_id)
            | (DocumentComparison.document_b_id == document_id)
        )
        .order_by(DocumentComparison.created_at.desc())
        .all()
    )
    return [
        {
            "comparison_id": c.id,
            "document_a_id": c.document_a_id,
            "document_b_id": c.document_b_id,
            "status": c.status,
            "overall_similarity_score": c.overall_similarity_score,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in comps
    ]
