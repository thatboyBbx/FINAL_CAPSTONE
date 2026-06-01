"""
AuditLogger — inserts rows into the audit_log table.
Provides helper methods for querying audit history.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Centralized audit logging for all meaningful system actions.
    All event_type values are defined as class-level constants.
    """

    # ------------------------------------------------------------------ #
    # Event type constants
    # ------------------------------------------------------------------ #
    DOCUMENT_UPLOADED      = "DOCUMENT_UPLOADED"
    DOCUMENT_ACCESSED      = "DOCUMENT_ACCESSED"
    DOCUMENT_DELETED       = "DOCUMENT_DELETED"
    ANALYSIS_STARTED       = "ANALYSIS_STARTED"
    ANALYSIS_COMPLETED     = "ANALYSIS_COMPLETED"
    ANALYSIS_EXPORTED      = "ANALYSIS_EXPORTED"
    QA_QUESTION_ASKED      = "QA_QUESTION_ASKED"
    COMPARISON_RUN         = "COMPARISON_RUN"
    FEEDBACK_SUBMITTED     = "FEEDBACK_SUBMITTED"
    BATCH_UPLOADED         = "BATCH_UPLOADED"
    POLICY_ALERT_SENT      = "POLICY_ALERT_SENT"
    REPORT_EXPORTED        = "REPORT_EXPORTED"
    USER_LOGIN             = "USER_LOGIN"
    USER_LOGOUT            = "USER_LOGOUT"
    USER_REGISTERED        = "USER_REGISTERED"
    ADMIN_ACTION           = "ADMIN_ACTION"
    RETRAINING_TRIGGERED   = "RETRAINING_TRIGGERED"
    # Auth security events
    LOGIN_FAILED           = "LOGIN_FAILED"
    TOKEN_REFRESHED        = "TOKEN_REFRESHED"
    TOKEN_REVOKED          = "TOKEN_REVOKED"
    PERMISSION_DENIED      = "PERMISSION_DENIED"

    # ------------------------------------------------------------------ #
    # Write
    # ------------------------------------------------------------------ #

    def log(
        self,
        db: Session,
        event_type: str,
        actor: str,
        document_id: int | None = None,
        analysis_id: int | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> int:
        """
        Insert an audit log row and return its id.
        Silently returns -1 on any DB error to avoid blocking the caller.
        """
        from app.modules.audit.model import AuditLog

        try:
            entry = AuditLog(
                event_type=event_type,
                actor=actor,
                document_id=document_id,
                analysis_id=analysis_id,
                ip_address=ip_address,
                details=details or {},
            )
            db.add(entry)
            db.commit()
            db.refresh(entry)
            return entry.id
        except Exception as exc:
            logger.error("AuditLogger.log failed: %s", exc)
            try:
                db.rollback()
            except Exception:
                pass
            return -1

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #

    def get_document_history(
        self, db: Session, document_id: int
    ) -> list[dict[str, Any]]:
        """Return all audit events for a document, oldest first."""
        from app.modules.audit.model import AuditLog

        try:
            rows = (
                db.query(AuditLog)
                .filter(AuditLog.document_id == document_id)
                .order_by(AuditLog.created_at.asc())
                .all()
            )
            return [_row_to_dict(r) for r in rows]
        except Exception as exc:
            logger.error("get_document_history failed: %s", exc)
            return []

    def get_user_activity(
        self, db: Session, actor: str, days_back: int = 30
    ) -> list[dict[str, Any]]:
        """Return audit events for an actor in the last N days, newest first."""
        from app.modules.audit.model import AuditLog

        since = datetime.now(timezone.utc) - timedelta(days=days_back)
        try:
            rows = (
                db.query(AuditLog)
                .filter(AuditLog.actor == actor, AuditLog.created_at >= since)
                .order_by(AuditLog.created_at.desc())
                .all()
            )
            return [_row_to_dict(r) for r in rows]
        except Exception as exc:
            logger.error("get_user_activity failed: %s", exc)
            return []

    def get_system_activity_summary(
        self, db: Session, days_back: int = 7
    ) -> dict[str, int]:
        """
        Return event counts per event_type for the last N days.
        Used for the admin monitoring dashboard.
        """
        from app.modules.audit.model import AuditLog
        from sqlalchemy import func

        since = datetime.now(timezone.utc) - timedelta(days=days_back)
        try:
            rows = (
                db.query(AuditLog.event_type, func.count(AuditLog.id).label("cnt"))
                .filter(AuditLog.created_at >= since)
                .group_by(AuditLog.event_type)
                .all()
            )
            return {row.event_type: row.cnt for row in rows}
        except Exception as exc:
            logger.error("get_system_activity_summary failed: %s", exc)
            return {}


def _row_to_dict(r) -> Dict[str, Any]:
    """Convert an AuditLog ORM row to a JSON-serialisable dict."""
    return {
        "id": r.id,
        "event_type": r.event_type,
        "actor": r.actor,
        "document_id": r.document_id,
        "analysis_id": r.analysis_id,
        "ip_address": r.ip_address,
        "details": r.details,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_audit_logger_instance: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger_instance
    if _audit_logger_instance is None:
        _audit_logger_instance = AuditLogger()
    return _audit_logger_instance
