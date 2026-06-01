"""
Feedback Router — /api/feedback endpoints for active learning corrections.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.audit.audit_logger import AuditLogger, get_audit_logger
from app.modules.feedback.feedback_store import FeedbackStore
from app.modules.auth.dependencies import get_current_user, require_role
from app.modules.users.model import User

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/feedback",
    tags=["feedback"],
    dependencies=[Depends(get_current_user)],
)

_store = FeedbackStore()


class EntityFeedbackRequest(BaseModel):
    document_id: int
    circular_analysis_id: int | None = None
    original_value: str
    original_type: str
    corrected_value: str
    corrected_type: str
    corrected_by: str


class RiskFlagFeedbackRequest(BaseModel):
    circular_analysis_id: int
    flag_text: str
    original_severity: str
    correct_severity: str
    is_false_positive: bool = False
    corrected_by: str


@router.post("/entity")
def submit_entity_feedback(
    payload: EntityFeedbackRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Submit a correction to an NER entity extraction."""
    try:
        fb_id = _store.record_entity_correction(
            db,
            document_id=payload.document_id,
            circular_analysis_id=payload.circular_analysis_id,
            original_value=payload.original_value,
            original_type=payload.original_type,
            corrected_value=payload.corrected_value,
            corrected_type=payload.corrected_type,
            corrected_by=payload.corrected_by,
        )
        return {"feedback_id": fb_id, "status": "recorded"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.post("/risk-flag")
def submit_risk_flag_feedback(
    payload: RiskFlagFeedbackRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Submit a correction to a risk flag classification."""
    try:
        fb_id = _store.record_risk_flag_correction(
            db,
            circular_analysis_id=payload.circular_analysis_id,
            flag_text=payload.flag_text,
            original_severity=payload.original_severity,
            correct_severity=payload.correct_severity,
            is_false_positive=payload.is_false_positive,
            corrected_by=payload.corrected_by,
        )
        return {"feedback_id": fb_id, "status": "recorded"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get("/stats")
def get_feedback_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Return pending feedback counts and retraining readiness status."""
    return _store.get_pending_feedback(db)


@router.post("/trigger-retraining")
def trigger_retraining(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
) -> Dict[str, Any]:
    """Admin-only: trigger model retraining with accumulated feedback."""
    import uuid

    job_id = str(uuid.uuid4())[:8]
    background_tasks.add_task(_run_retraining)
    get_audit_logger().log(
        db,
        event_type=AuditLogger.RETRAINING_TRIGGERED,
        actor=admin.staff_id,
        ip_address=request.client.host if request.client else None,
        details={"job_id": job_id},
    )
    return {"status": "retraining_started", "job_id": job_id}


def _run_retraining() -> None:
    """Background task: run full retraining pipeline with its own DB session."""
    from app.core.db import session_scope
    from app.modules.feedback.retraining_pipeline import RetrainingPipeline

    try:
        with session_scope() as db:
            result = RetrainingPipeline().run_full_retraining(db)
            logger.info("Retraining result: %s", result)
    except Exception as exc:
        logger.error("Retraining pipeline failed: %s", exc)
