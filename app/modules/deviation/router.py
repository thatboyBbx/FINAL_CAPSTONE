"""
Deviation Router — /api/deviation endpoints for clause deviation scoring.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/deviation",
    tags=["deviation"],
    dependencies=[Depends(get_current_user)],
)


class ClauseScoreRequest(BaseModel):
    clause_text: str
    clause_type: str


@router.post("/score-document/{document_id}")
def score_document(
    document_id: int, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Score all clauses in a document against the standard clause library."""
    from app.modules.documents.model import Document
    from app.modules.deviation.clause_scorer import get_clause_scorer

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document id={document_id} not found.",
        )

    try:
        scorer = get_clause_scorer(db)
        return scorer.score_document(document_id, db)
    except Exception as exc:
        logger.error("Deviation scoring failed for doc %d: %s", document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deviation scoring failed: {exc}",
        )


@router.get("/document/{document_id}")
def get_document_scores(
    document_id: int, db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Return stored clause deviation scores for a document."""
    from app.modules.deviation.model import ClauseDeviationScore

    rows = (
        db.query(ClauseDeviationScore)
        .filter(ClauseDeviationScore.document_id == document_id)
        .order_by(ClauseDeviationScore.deviation_score.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "clause_type": r.clause_type,
            "deviation_score": r.deviation_score,
            "deviation_label": r.deviation_label,
            "similarity_to_standard": r.similarity_to_standard,
            "risk_implication": r.risk_implication,
            "clause_text": r.clause_text[:300] if r.clause_text else None,
        }
        for r in rows
    ]


@router.post("/clause")
def score_single_clause(
    payload: ClauseScoreRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Score a single clause text against the standard library (live scoring)."""
    from app.modules.deviation.clause_scorer import get_clause_scorer

    try:
        scorer = get_clause_scorer(db)
        return scorer.score_clause(payload.clause_text, payload.clause_type)
    except Exception as exc:
        logger.error("Single clause scoring failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scoring failed: {exc}",
        )


@router.post("/seed-knowledge-base")
def seed_knowledge_base(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Trigger the knowledge base seeder to populate standard clauses."""
    from app.modules.deviation.knowledge_base_seeder import KnowledgeBaseSeeder
    # Reset the scorer cache so it picks up new clauses
    import app.modules.deviation.clause_scorer as cs_module
    cs_module._cached_scorer = None

    seeder = KnowledgeBaseSeeder()
    return seeder.seed_knowledge_base(db)
