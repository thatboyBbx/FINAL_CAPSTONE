"""
PolicyTrackerService — extracts policy periods from documents, tracks expiry dates,
and sends email notifications for upcoming renewals.
"""
from __future__ import annotations

import logging
import os
import re
import smtplib
import ssl
from datetime import date, datetime, timedelta, timezone
from email.mime.text import MIMEText
from typing import Any, Dict, List

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Date formats attempted by dateutil (dayfirst=True for Zimbabwean convention)
_DATE_HINT_PATTERNS = [
    # "1st January 2025", "01 January 2025", "January 2025"
    r"\b(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})\b",
    # "01/01/2025", "2025-01-01"
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
    r"\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b",
]

_DATE_COMBINED = re.compile("|".join(_DATE_HINT_PATTERNS), re.IGNORECASE)


class PolicyTrackerService:
    """Manages the policy_tracker table and expiry notifications."""

    # ------------------------------------------------------------------
    # Sync from a document
    # ------------------------------------------------------------------

    def sync_from_document(
        self, db: Session, document_id: int
    ) -> Dict[str, Any]:
        """
        Parse policy date entities from circular_analyses and upsert
        a policy_tracker row for the given document.
        """
        from app.modules.tracker.model import PolicyTracker
        from app.modules.circulars.model import CircularAnalysis
        from app.modules.documents.model import Document

        # Fetch related data
        doc = db.query(Document).filter(Document.id == document_id).first()
        analysis = (
            db.query(CircularAnalysis)
            .filter(CircularAnalysis.document_id == document_id)
            .first()
        )

        # Parse dates from the pipe-delimited dates_found string
        raw_dates = []
        if analysis and analysis.dates_found:
            raw_dates = [d.strip() for d in analysis.dates_found.split("|") if d.strip()]

        # Also attempt to parse dates from full extracted text
        if analysis and analysis.extracted_text:
            raw_dates += _extract_dates_from_text(analysis.extracted_text)

        parsed_dates = _parse_date_list(raw_dates)
        parsed_dates.sort()

        start_date = parsed_dates[0] if len(parsed_dates) >= 2 else None
        end_date   = parsed_dates[-1] if parsed_dates else None

        # Extract insured name and insurer name from insurer_mentions
        insurer_name = None
        if analysis and analysis.insurer_mentions_found:
            mentions = [m.strip() for m in analysis.insurer_mentions_found.split("|") if m.strip()]
            insurer_name = mentions[0] if mentions else None

        # Compute days until expiry
        days_left = None
        if end_date:
            delta = end_date - date.today()
            days_left = delta.days

        # Determine alert status
        alert_status = "active"
        if end_date:
            if end_date < date.today():
                alert_status = "expired"
            elif days_left is not None and days_left <= 30:
                alert_status = "expiring_soon"

        # Extract premium from monetary values
        premium_usd = None
        if analysis and analysis.monetary_values_found:
            from app.infrastructure.scrapers.scraper_utils import parse_usd_value
            amounts = [v.strip() for v in analysis.monetary_values_found.split("|") if v.strip()]
            for amt in amounts:
                val = parse_usd_value(amt)
                if val and val > 0:
                    premium_usd = val
                    break

        # Upsert the tracker row (one row per document)
        tracker = (
            db.query(PolicyTracker)
            .filter(PolicyTracker.document_id == document_id)
            .first()
        )
        now = datetime.now(timezone.utc)
        if tracker:
            tracker.policy_start_date = start_date
            tracker.expiry_date        = end_date
            tracker.days_until_expiry  = days_left
            tracker.insurer_name       = insurer_name
            tracker.premium_amount_usd = premium_usd
            tracker.alert_status       = alert_status
            tracker.updated_at         = now
            if doc:
                tracker.portfolio_id = getattr(doc, "portfolio_id", None)
        else:
            tracker = PolicyTracker(
                document_id=document_id,
                portfolio_id=getattr(doc, "portfolio_id", None) if doc else None,
                insurer_name=insurer_name,
                policy_start_date=start_date,
                expiry_date=end_date,
                days_until_expiry=days_left,
                premium_amount_usd=premium_usd,
                alert_status=alert_status,
            )
            db.add(tracker)

        try:
            db.commit()
            db.refresh(tracker)
        except Exception as exc:
            logger.error("Failed to upsert PolicyTracker for doc %d: %s", document_id, exc)
            db.rollback()

        return {
            "document_id": document_id,
            "expiry_date": end_date.isoformat() if end_date else None,
            "days_until_expiry": days_left,
            "alert_status": alert_status,
        }

    # ------------------------------------------------------------------
    # Query alerts
    # ------------------------------------------------------------------

    def get_expiry_alerts(
        self,
        db: Session,
        days_ahead: int = 60,
        portfolio_id: str | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Return policies expiring within `days_ahead` days, sorted by expiry_date asc.
        """
        from app.modules.tracker.model import PolicyTracker
        from app.modules.documents.model import Document

        cutoff = date.today() + timedelta(days=days_ahead)
        today  = date.today()

        q = (
            db.query(PolicyTracker, Document)
            .join(Document, PolicyTracker.document_id == Document.id)
            .filter(
                PolicyTracker.expiry_date <= cutoff,
                PolicyTracker.expiry_date >= today,
                PolicyTracker.alert_status != "expired",
            )
        )
        if portfolio_id:
            q = q.filter(PolicyTracker.portfolio_id == portfolio_id)

        rows = q.order_by(PolicyTracker.expiry_date.asc()).all()

        alerts = []
        for tracker, doc in rows:
            days_remaining = (tracker.expiry_date - today).days if tracker.expiry_date else None
            if days_remaining is not None and days_remaining <= 14:
                level = "critical"
            elif days_remaining is not None and days_remaining <= 30:
                level = "warning"
            else:
                level = "info"

            alerts.append({
                "policy_id": tracker.id,
                "document_id": tracker.document_id,
                "filename": doc.original_filename,
                "insured_name": tracker.insured_name,
                "insurer_name": tracker.insurer_name,
                "expiry_date": tracker.expiry_date.isoformat() if tracker.expiry_date else None,
                "days_remaining": days_remaining,
                "alert_level": level,
                "portfolio_id": tracker.portfolio_id,
            })

        return alerts

    # ------------------------------------------------------------------
    # Email notifications
    # ------------------------------------------------------------------

    def send_expiry_notifications(self, db: Session) -> Dict[str, Any]:
        """
        Send email notifications for policies expiring within 60 days.
        Respects a 7-day cooldown per policy to avoid spam.
        """
        alerts = self.get_expiry_alerts(db, days_ahead=60)
        sent = 0
        critical_count = 0
        warning_count = 0

        smtp_host     = os.environ.get("SMTP_HOST", "")
        smtp_port     = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user     = os.environ.get("SMTP_USER", "")
        smtp_password = os.environ.get("SMTP_PASSWORD", "")
        notify_email  = os.environ.get("NOTIFICATION_EMAIL", smtp_user)

        if not smtp_host or not smtp_user:
            logger.warning("SMTP not configured — skipping expiry notification emails.")
            return {"alerts_sent": 0, "critical": 0, "warning": 0}

        from app.modules.tracker.model import PolicyTracker

        cooldown = timedelta(days=7)
        now = datetime.now(timezone.utc)

        for alert in alerts:
            # Check cooldown
            tracker = (
                db.query(PolicyTracker)
                .filter(PolicyTracker.id == alert["policy_id"])
                .first()
            )
            if not tracker:
                continue
            if tracker.last_notified and (now - tracker.last_notified) < cooldown:
                continue  # notified recently, skip

            # Send email
            try:
                _send_alert_email(
                    smtp_host, smtp_port, smtp_user, smtp_password,
                    notify_email, alert,
                )
                tracker.last_notified = now
                db.commit()
                sent += 1
                if alert["alert_level"] == "critical":
                    critical_count += 1
                elif alert["alert_level"] == "warning":
                    warning_count += 1
            except Exception as exc:
                logger.error("Failed to send alert for policy %d: %s", alert["policy_id"], exc)

        logger.info("Expiry notifications sent: %d total.", sent)
        return {"alerts_sent": sent, "critical": critical_count, "warning": warning_count}

    # ------------------------------------------------------------------
    # Mark renewed
    # ------------------------------------------------------------------

    def mark_renewed(
        self, db: Session, policy_id: int, new_document_id: int
    ) -> None:
        """Mark a policy as renewed, linking to the new document."""
        from app.modules.tracker.model import PolicyTracker

        tracker = db.query(PolicyTracker).filter(PolicyTracker.id == policy_id).first()
        if not tracker:
            raise ValueError(f"Policy id={policy_id} not found.")

        tracker.renewal_document_id = new_document_id
        tracker.alert_status        = "renewed"
        tracker.updated_at          = datetime.now(timezone.utc)
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            raise ValueError(f"Failed to mark policy renewed: {exc}") from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_dates_from_text(text: str) -> List[str]:
    """Extract date-like strings from raw text using regex."""
    matches = _DATE_COMBINED.findall(text)
    # findall returns tuples (one group per alternation); flatten
    flat = []
    for m in matches:
        for g in m:
            if g:
                flat.append(g)
    return flat[:20]  # cap to avoid parsing huge lists


def _parse_date_list(raw: List[str]) -> List[date]:
    """Parse a list of raw date strings into date objects, best-effort."""
    try:
        from dateutil import parser as dateutil_parser
        from dateutil.parser import ParserError
    except ImportError:
        return []

    parsed = []
    for s in raw:
        try:
            dt = dateutil_parser.parse(s, dayfirst=True, fuzzy=True)
            parsed.append(dt.date())
        except (ParserError, ValueError, OverflowError):
            continue
    # Deduplicate
    return list(dict.fromkeys(parsed))


def _send_alert_email(
    host: str,
    port: int,
    user: str,
    password: str,
    to_email: str,
    alert: Dict[str, Any],
) -> None:
    """Send a plain-text expiry alert email via SMTP with STARTTLS."""
    days = alert.get("days_remaining", "?")
    insured = alert.get("insured_name") or "Unknown Insured"
    expiry = alert.get("expiry_date") or "Unknown"
    level = alert.get("alert_level", "info").upper()

    subject = f"[{level}] Policy Expiry Alert: {insured} — {days} days"
    body = (
        f"Policy Expiry Alert\n"
        f"-------------------\n"
        f"Insured Party  : {insured}\n"
        f"Insurer        : {alert.get('insurer_name') or 'Unknown'}\n"
        f"Document       : {alert.get('filename', '')}\n"
        f"Expiry Date    : {expiry}\n"
        f"Days Remaining : {days}\n"
        f"Alert Level    : {level}\n\n"
        f"Please arrange renewal before the expiry date.\n"
        f"This is an automated notification from the Insurance Document Intelligence Platform."
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"]    = user
    msg["To"]      = to_email

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=15) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(user, password)
        server.sendmail(user, [to_email], msg.as_string())
