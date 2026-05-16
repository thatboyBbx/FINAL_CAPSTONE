"""
Tracker Router — /api/tracker endpoints for policy expiry management.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.tracker.service import PolicyTrackerService
from app.modules.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/tracker",
    tags=["tracker"],
    dependencies=[Depends(get_current_user)],
)

_svc = PolicyTrackerService()


class MarkRenewedRequest(BaseModel):
    policy_id: int
    new_document_id: int


@router.get("/alerts")
def get_alerts(
    days_ahead: int = Query(default=60, ge=1, le=365),
    portfolio_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return upcoming policy expiry alerts."""
    return _svc.get_expiry_alerts(db, days_ahead=days_ahead, portfolio_id=portfolio_id)


@router.get("/policy/{document_id}")
def get_policy(
    document_id: int, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Return the policy_tracker row for a document."""
    from app.modules.tracker.model import PolicyTracker

    tracker = (
        db.query(PolicyTracker)
        .filter(PolicyTracker.document_id == document_id)
        .first()
    )
    if not tracker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No policy tracker entry for document id={document_id}.",
        )
    return {
        "id": tracker.id,
        "document_id": tracker.document_id,
        "portfolio_id": tracker.portfolio_id,
        "policy_number": tracker.policy_number,
        "insured_name": tracker.insured_name,
        "insurer_name": tracker.insurer_name,
        "policy_start_date": tracker.policy_start_date.isoformat() if tracker.policy_start_date else None,
        "expiry_date": tracker.expiry_date.isoformat() if tracker.expiry_date else None,
        "days_until_expiry": tracker.days_until_expiry,
        "premium_amount_usd": tracker.premium_amount_usd,
        "alert_status": tracker.alert_status,
        "last_notified": tracker.last_notified.isoformat() if tracker.last_notified else None,
    }


@router.post("/sync/{document_id}")
def sync_document(
    document_id: int, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Manually trigger policy date extraction and tracker sync for a document."""
    return _svc.sync_from_document(db, document_id)


@router.post("/mark-renewed")
def mark_renewed(
    payload: MarkRenewedRequest, db: Session = Depends(get_db)
) -> dict[str, str]:
    """Mark a policy as renewed, linking to the replacement document."""
    try:
        _svc.mark_renewed(db, payload.policy_id, payload.new_document_id)
        return {"status": "renewed"}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
