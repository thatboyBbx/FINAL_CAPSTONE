"""
Audit Trail Router — /api/audit endpoints (admin-only).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.modules.audit.audit_logger import get_audit_logger
from app.core.db import get_db
from app.modules.auth.dependencies import require_role

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/audit",
    tags=["audit"],
    dependencies=[Depends(require_role("admin"))],
)


@router.get("/document/{document_id}")
def get_document_history(
    document_id: int,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return all audit events for a specific document, oldest first."""
    return get_audit_logger().get_document_history(db, document_id)


@router.get("/user/{actor}")
def get_user_activity(
    actor: str,
    days_back: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return audit events for a user in the last N days."""
    return get_audit_logger().get_user_activity(db, actor, days_back)


@router.get("/summary")
def get_system_summary(
    days_back: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, int]:
    """Return event counts per event_type for the last N days."""
    return get_audit_logger().get_system_activity_summary(db, days_back)
