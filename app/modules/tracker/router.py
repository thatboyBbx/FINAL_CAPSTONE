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
from app.modules.auth.access_control import can_access_document, require_document_access
from app.modules.auth.dependencies import get_current_user
from app.modules.users.model import User

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


class RenewPolicyRequest(BaseModel):
    new_document_id: int | None = None


def _tracker_by_ref(db: Session, policy_ref: str):
    from app.modules.tracker.model import PolicyTracker

    query = db.query(PolicyTracker)
    if policy_ref.isdigit():
        tracker = query.filter(PolicyTracker.id == int(policy_ref)).first()
        if tracker:
            return tracker
    return query.filter(PolicyTracker.policy_number == policy_ref).first()


@router.get("/alerts")
def get_alerts(
    days_ahead: int = Query(default=60, ge=1, le=365),
    portfolio_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Return upcoming policy expiry alerts."""
    from app.modules.documents.model import Document

    alerts = _svc.get_expiry_alerts(db, days_ahead=days_ahead, portfolio_id=portfolio_id)
    return [
        alert for alert in alerts
        if can_access_document(db, current_user, db.get(Document, alert["document_id"]))
    ]


@router.get("/policy/{document_id}")
def get_policy(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the policy_tracker row for a document."""
    from app.modules.tracker.model import PolicyTracker

    require_document_access(db, current_user, document_id)
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
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Manually trigger policy date extraction and tracker sync for a document."""
    require_document_access(db, current_user, document_id)
    return _svc.sync_from_document(db, document_id)


@router.post("/mark-renewed")
def mark_renewed(
    payload: MarkRenewedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Mark a policy as renewed, linking to the replacement document."""
    try:
        from app.modules.tracker.model import PolicyTracker
        tracker = db.query(PolicyTracker).filter(PolicyTracker.id == payload.policy_id).first()
        if not tracker:
            raise ValueError(f"Policy id={payload.policy_id} not found.")
        require_document_access(db, current_user, tracker.document_id)
        require_document_access(db, current_user, payload.new_document_id)
        _svc.mark_renewed(db, payload.policy_id, payload.new_document_id)
        return {"status": "renewed"}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/policies/{policy_ref}/renew")
def renew_policy_by_ref(
    policy_ref: str,
    payload: RenewPolicyRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Compatibility endpoint for the policy tracker UI renewal action."""
    tracker = _tracker_by_ref(db, policy_ref)
    if not tracker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found.")
    require_document_access(db, current_user, tracker.document_id)
    new_document_id = payload.new_document_id if payload and payload.new_document_id else tracker.document_id
    require_document_access(db, current_user, new_document_id)
    try:
        _svc.mark_renewed(db, tracker.id, new_document_id)
        return {"status": "renewed"}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
