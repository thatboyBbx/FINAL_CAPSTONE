"""
FeedbackStore — records and retrieves human corrections to NER and risk outputs.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class FeedbackStore:
    """Manages the entity_feedback and risk_flag_feedback tables."""

    # Minimum number of feedback items required before retraining is triggered
    MIN_RETRAINING_COUNT = 50

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record_entity_correction(
        self,
        db: Session,
        document_id: int,
        circular_analysis_id: int | None,
        original_value: str,
        original_type: str,
        corrected_value: str,
        corrected_type: str,
        corrected_by: str,
    ) -> int:
        """
        Insert an entity correction record.
        Returns the new feedback row id.
        """
        from app.modules.feedback.model import EntityFeedback

        fb = EntityFeedback(
            document_id=document_id,
            circular_analysis_id=circular_analysis_id,
            original_value=original_value,
            original_type=original_type,
            corrected_value=corrected_value,
            corrected_type=corrected_type,
            corrected_by=corrected_by,
        )
        try:
            db.add(fb)
            db.commit()
            db.refresh(fb)
            return fb.id
        except Exception as exc:
            logger.error("record_entity_correction failed: %s", exc)
            db.rollback()
            raise

    def record_risk_flag_correction(
        self,
        db: Session,
        circular_analysis_id: int,
        flag_text: str,
        original_severity: str,
        correct_severity: str,
        is_false_positive: bool,
        corrected_by: str,
    ) -> int:
        """Insert a risk flag correction record. Returns the new feedback id."""
        from app.modules.feedback.model import RiskFlagFeedback

        fb = RiskFlagFeedback(
            circular_analysis_id=circular_analysis_id,
            flag_text=flag_text,
            original_severity=original_severity,
            correct_severity=correct_severity,
            is_false_positive=is_false_positive,
            corrected_by=corrected_by,
        )
        try:
            db.add(fb)
            db.commit()
            db.refresh(fb)
            return fb.id
        except Exception as exc:
            logger.error("record_risk_flag_correction failed: %s", exc)
            db.rollback()
            raise

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_pending_feedback(
        self, db: Session, min_count: int = 50
    ) -> Dict[str, Any]:
        """
        Return unused feedback items and whether enough have accumulated
        to trigger a retraining run.
        """
        from app.modules.feedback.model import EntityFeedback, RiskFlagFeedback

        entity_rows = (
            db.query(EntityFeedback)
            .filter(EntityFeedback.used_in_training == False)  # noqa: E712
            .all()
        )
        risk_rows = (
            db.query(RiskFlagFeedback)
            .filter(RiskFlagFeedback.used_in_training == False)  # noqa: E712
            .all()
        )

        total = len(entity_rows) + len(risk_rows)

        return {
            "entity_corrections": [_entity_to_dict(r) for r in entity_rows],
            "risk_corrections": [_risk_to_dict(r) for r in risk_rows],
            "total_count": total,
            "ready_for_training": total >= min_count,
        }

    def mark_feedback_used(
        self, db: Session, entity_ids: List[int], risk_ids: List[int]
    ) -> None:
        """Mark given feedback records as used in training."""
        from app.modules.feedback.model import EntityFeedback, RiskFlagFeedback

        now = datetime.now(timezone.utc)
        try:
            if entity_ids:
                db.query(EntityFeedback).filter(
                    EntityFeedback.id.in_(entity_ids)
                ).update({"used_in_training": True, "used_at": now}, synchronize_session=False)
            if risk_ids:
                db.query(RiskFlagFeedback).filter(
                    RiskFlagFeedback.id.in_(risk_ids)
                ).update({"used_in_training": True, "used_at": now}, synchronize_session=False)
            db.commit()
        except Exception as exc:
            logger.error("mark_feedback_used failed: %s", exc)
            db.rollback()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entity_to_dict(r) -> Dict[str, Any]:
    return {
        "id": r.id,
        "document_id": r.document_id,
        "circular_analysis_id": r.circular_analysis_id,
        "original_value": r.original_value,
        "original_type": r.original_type,
        "corrected_value": r.corrected_value,
        "corrected_type": r.corrected_type,
        "corrected_by": r.corrected_by,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _risk_to_dict(r) -> Dict[str, Any]:
    return {
        "id": r.id,
        "circular_analysis_id": r.circular_analysis_id,
        "flag_text": r.flag_text,
        "original_severity": r.original_severity,
        "correct_severity": r.correct_severity,
        "is_false_positive": r.is_false_positive,
        "corrected_by": r.corrected_by,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
