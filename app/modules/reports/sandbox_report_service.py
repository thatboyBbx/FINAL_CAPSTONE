"""
app/modules/reports/sandbox_report_service.py

Service that generates the template context dict for the IPEC Regulatory
Sandbox Quarterly Progress Report (Annexure 3).

Public API:
    generate_sandbox_quarterly_report_context(broker_id, quarter, db) -> dict
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Quarter → (start_month, end_month) mapping for date-range queries
_QUARTER_MONTHS: dict[str, tuple[int, int]] = {
    "Q1": (1, 3),
    "Q2": (4, 6),
    "Q3": (7, 9),
    "Q4": (10, 12),
}


def _parse_quarter(quarter: str) -> tuple[int, int, int]:
    """
    Parse a quarter string like "Q2-2026" into (year, start_month, end_month).

    Dissertation Methodology Note (Chapter 3):
    A simple string-parsing utility is used rather than a date library to
    minimise dependencies and keep the function deterministic for unit tests.

    References:
        IPEC (2025). Regulatory Sandbox Guidelines for the Insurance and
        Pensions Industry. Insurance and Pensions Commission of Zimbabwe.
        Effective Q4 2025. Retrieved from ipec.co.zw.
    """
    try:
        # Expect format "Q2-2026" or "Q2 2026"
        parts = quarter.replace(" ", "-").split("-")
        q_label = parts[0].upper()   # e.g. "Q2"
        year = int(parts[1])         # e.g. 2026
        start_month, end_month = _QUARTER_MONTHS.get(q_label, (1, 3))
        return year, start_month, end_month
    except (IndexError, ValueError):
        # Fallback to Q2 of the current year
        now = datetime.now(timezone.utc)
        return now.year, 4, 6


def _build_kpis_from_results(analysis_results: list[dict]) -> list[dict]:
    """
    Build KPI rows from aggregated analysis result statistics.

    Dissertation Methodology Note (Chapter 3):
    KPIs are constructed from platform metrics (avg risk score, compliance rate)
    using rule-based thresholds rather than ML, because the Annexure 3 template
    requires predetermined targets that must be agreed before the test starts.

    References:
        IPEC (2025). Regulatory Sandbox Guidelines for the Insurance and
        Pensions Industry. Insurance and Pensions Commission of Zimbabwe.
        Effective Q4 2025. Retrieved from ipec.co.zw.
    """
    if not analysis_results:
        return [
            {"name": "Average Risk Score", "target": "< 40", "actual": "N/A",
             "status": "missed"},
            {"name": "Compliance Pass Rate", "target": "> 90%", "actual": "N/A",
             "status": "missed"},
            {"name": "Documents Analysed", "target": "> 0", "actual": "0",
             "status": "missed"},
        ]

    # Average risk score (lower is better — target < 40)
    risk_scores = [
        r["risk_score"] for r in analysis_results if r.get("risk_score") is not None
    ]
    avg_risk = round(sum(risk_scores) / len(risk_scores), 1) if risk_scores else 0.0

    # Compliance pass rate (proportion of results with status "compliant")
    compliant_count = sum(
        1 for r in analysis_results if r.get("compliance_status") == "compliant"
    )
    compliance_rate = (
        round(compliant_count / len(analysis_results) * 100, 1)
        if analysis_results else 0.0
    )

    doc_count = len(analysis_results)

    # Map metrics to KPI status (met / partial / missed)
    risk_status = "met" if avg_risk < 40 else ("partial" if avg_risk < 60 else "missed")
    compliance_status = "met" if compliance_rate >= 90 else (
        "partial" if compliance_rate >= 70 else "missed"
    )
    doc_status = "met" if doc_count > 0 else "missed"

    return [
        {
            "name": "Average Risk Score",
            "target": "< 40",
            "actual": str(avg_risk),
            "status": risk_status,
        },
        {
            "name": "Compliance Pass Rate",
            "target": "> 90%",
            "actual": f"{compliance_rate}%",
            "status": compliance_status,
        },
        {
            "name": "Documents Analysed",
            "target": "> 0",
            "actual": str(doc_count),
            "status": doc_status,
        },
    ]


def generate_sandbox_quarterly_report_context(
    broker_id: int,
    quarter: str,
    db: Session,
) -> dict[str, Any]:
    """
    Build the full Jinja2 template context for the Sandbox Quarterly Report.

    Steps:
    1. Parse the quarter string into a date range (year, start_month, end_month).
    2. Query analysis results (ComplianceCheck) for the broker over that range.
    3. Aggregate KPI metrics: avg risk score, compliance rate, document count.
    4. Fetch risk register entries if the table exists, else return empty list.
    5. Return the full template context dict matching sandbox_quarterly_report.html.

    Dissertation Methodology Note (Chapter 3):
    Aggregation is performed in Python rather than SQL to avoid complex
    database queries that may not be portable across SQLite (test) and
    PostgreSQL (production) environments.  The function is intentionally
    stateless — it returns a dict, not a rendered string — so it can be
    unit-tested without an HTTP client.

    References:
        IPEC (2025). Regulatory Sandbox Guidelines for the Insurance and
        Pensions Industry. Insurance and Pensions Commission of Zimbabwe.
        Effective Q4 2025. Retrieved from ipec.co.zw.
    """
    # ── Step 1: Resolve quarter date range ────────────────────────────────────
    year, start_month, end_month = _parse_quarter(quarter)
    # Last day of end_month (approximate — 28 covers all months safely)
    # We use ≥ start_date and ≤ end_year-end_month for filtering
    logger.info(
        "generate_sandbox_quarterly_report_context: broker=%d quarter=%s "
        "range=%d-M%d to %d-M%d",
        broker_id, quarter, year, start_month, year, end_month,
    )

    # ── Step 2: Query compliance checks for this broker in this quarter ────────
    # Import here to keep startup cost low and avoid circular imports
    from app.modules.compliance.model import ComplianceResult  # noqa: PLC0415
    from app.modules.documents.model import Document  # noqa: PLC0415

    try:
        # Join ComplianceCheck → Document to filter by broker/uploader
        checks = (
            db.query(ComplianceResult)
            .join(Document, Document.id == ComplianceResult.document_id)
            .filter(Document.uploaded_by_user_id == broker_id)
            .filter(
                ComplianceResult.checked_at >= datetime(year, start_month, 1,
                                                        tzinfo=timezone.utc),
                ComplianceResult.checked_at <= datetime(year, end_month, 28,
                                                        tzinfo=timezone.utc),
            )
            .all()
        )
        logger.info(
            "generate_sandbox_quarterly_report_context: found %d checks", len(checks)
        )
    except Exception as exc:
        logger.warning("Could not query compliance checks: %s", exc)
        checks = []

    # ── Step 3: Build analysis_results summary from checks ────────────────────
    analysis_results: list[dict] = [
        {
            "risk_score": c.compliance_score,     # compliance_score serves as risk proxy
            "compliance_status": c.status,
        }
        for c in checks
    ]

    # ── Step 4: Aggregate customer/transaction stats from document metadata ────
    try:
        docs = (
            db.query(Document)
            .filter(Document.uploaded_by_user_id == broker_id)
            .all()
        )
        customer_count = len(docs)
        transaction_volume = len(checks)
        transaction_value = f"USD {len(checks) * 0:,.0f}"  # placeholder aggregation
    except Exception:
        customer_count = 0
        transaction_volume = 0
        transaction_value = "USD 0"

    # ── Step 5: Build KPI rows from aggregated results ────────────────────────
    kpis = _build_kpis_from_results(analysis_results)

    # ── Step 6: Attempt to fetch risk register (table may not exist yet) ─────
    risk_register: list[dict] = []
    try:
        from sqlalchemy import text  # noqa: PLC0415
        result = db.execute(
            text("SELECT risk, trigger_event, treatment, likelihood "
                 "FROM risk_register WHERE broker_id = :bid LIMIT 20"),
            {"bid": broker_id},
        )
        risk_register = [
            {
                "risk": row[0],
                "trigger": row[1],
                "treatment": row[2],
                "likelihood": row[3],
            }
            for row in result
        ]
    except Exception:
        # risk_register table does not exist — return empty list as specified
        risk_register = []

    # ── Step 7: Return full template context dict ─────────────────────────────
    return {
        "participant_name": f"Broker ID {broker_id}",
        "report_quarter": quarter,
        "report_date": date.today().strftime("%d %B %Y"),
        "kpis": kpis,
        "customer_count": customer_count,
        "transaction_volume": transaction_volume,
        "transaction_value": transaction_value,
        "risk_register": risk_register,
        "operational_challenges": [],
        "cybersecurity_incidents": [],
        "audit_details": (
            f"Platform-generated report. {len(checks)} compliance check(s) run "
            f"during {quarter}. See InsureIntel audit log for detail."
        ),
        "customer_complaints": [],
        "generated_by": "InsureIntel Zimbabwe Platform",
        "document_ids_analysed": [str(c.document_id) for c in checks],
    }
