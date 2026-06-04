from __future__ import annotations

import csv
import io
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.insurers.schemas import InsurerCreate, InsurerRead
from app.modules.insurers.service import InsurerService
from app.modules.insurers.dev_seed import seed_insurers
from app.modules.auth.dependencies import get_current_user, require_role

logger = logging.getLogger(__name__)


router    = APIRouter(
    prefix="/insurers",
    tags=["insurers"],
    dependencies=[Depends(get_current_user)],
)
service   = InsurerService()

_analytics_instance = None


def _get_analytics():
    global _analytics_instance
    if _analytics_instance is None:
        from app.modules.insurers.analytics_service import InsurerAnalytics
        _analytics_instance = InsurerAnalytics()
    return _analytics_instance

# ── Existing CRUD ─────────────────────────────────────────────────────────────

@router.post("", response_model=InsurerRead)
def create_insurer(
    payload: InsurerCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    try:
        insurer = service.create_insurer(db, payload)
        return insurer
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/dev/seed")
def dev_seed_insurers(
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Seed all 70+ IPEC-licensed insurers."""
    return seed_insurers(db)


# ── Intelligence endpoints (must be declared before /{insurer_id}) ────────────

@router.get("/market-overview")
def market_overview(
    period_label: str | None = Query(None, description="e.g. Q4_2024"),
    db: Session = Depends(get_db),
):
    """Sector-wide summary for a given period."""
    return _get_analytics().get_market_overview(db, period_label=period_label)


@router.get("/market-position-chart")
def market_position_chart(
    period_label: str | None = Query(None),
    category: str = Query("short_term", description="Insurer category filter"),
    db: Session = Depends(get_db),
):
    """Plotly-ready chart data: top 10 insurers by revenue."""
    return _get_analytics().get_market_position_chart_data(db, period_label=period_label, category=category)


@router.get("/claims-ranking")
def claims_ranking(
    period_label: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Insurers ranked by settlement power score."""
    return _get_analytics().get_claims_power_ranking(db, period_label=period_label)


@router.get("/sentiment-heatmap")
def sentiment_heatmap(
    days_back: int = Query(90, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Per-insurer weekly sentiment scores for heatmap rendering."""
    return _get_analytics().get_sentiment_heatmap(db, days_back=days_back)


@router.get("/scrape/runs")
def list_scrape_runs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Last N ScrapeRun rows ordered by started_at desc."""
    from app.modules.insurers.scrape_model import ScrapeRun
    runs = (
        db.query(ScrapeRun)
        .order_by(ScrapeRun.run_started_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id":                run.id,
            "scraper_name":      run.scraper_name,
            "run_started_at":    run.run_started_at.isoformat() if run.run_started_at else None,
            "run_completed_at":  run.run_completed_at.isoformat() if run.run_completed_at else None,
            "status":            run.status,
            "records_inserted":  run.records_inserted,
            "records_updated":   run.records_updated,
            "error_message":     run.error_message,
        }
        for run in runs
    ]


@router.post("/import-csv")
async def import_insurers_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
) -> dict:
    """
    Import or upsert insurers from a CSV file.

    Expected CSV columns (from the IPEC regulated-entities export):
        Entity Name, Insurance Category, Insurance Type,
        Physical Address, Email, Telephone, Source

    Upsert strategy: match on ``name`` (exact, case-insensitive).
    Returns: {"imported": N, "updated": M, "errors": [...]}

    Args:
        file: Uploaded CSV file (multipart/form-data).
        db:   SQLAlchemy session.

    Raises:
        HTTPException 400 if the file cannot be parsed.
    """
    from app.modules.insurers.model import Insurer as _Insurer  # noqa: PLC0415

    # ── Read CSV content ──────────────────────────────────────────────────────
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig", errors="replace")  # strip BOM if present
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read CSV file: {exc}")

    reader = csv.DictReader(io.StringIO(text))

    # Column aliases — tolerate minor header variations
    _COL_ALIASES: dict[str, list[str]] = {
        "name":     ["Entity Name", "entity_name", "Name", "name"],
        "category": ["Insurance Category", "insurance_category", "Category"],
        "type":     ["Insurance Type", "insurance_type", "Type"],
        "address":  ["Physical Address", "physical_address", "Address"],
        "email":    ["Email", "email"],
        "phone":    ["Telephone", "telephone", "Phone"],
    }

    def _get(row: dict, field: str) -> str:
        """Extract a field from a row using known column aliases."""
        for alias in _COL_ALIASES.get(field, [field]):
            if alias in row:
                return (row[alias] or "").strip()
        return ""

    # Map Insurance Category strings → SQLAlchemy enum values
    _CAT_MAP: dict[str, str] = {
        "life assurer":         "life_assurance",
        "life assurance":       "life_assurance",
        "short-term insurer":   "short_term",
        "short term insurer":   "short_term",
        "reinsurer":            "reinsurer",
        "life reassurer":       "reinsurer",
        "funeral assurer":      "funeral_assurer",
        "funeral":              "funeral_assurer",
        "micro-insurer":        "microinsurer",
        "microinsurer":         "microinsurer",
        "broker":               "broker",
        "multiple agent":       "multiple_agent",
        "underwriting agent":   "underwriting_agent",
    }

    imported = 0
    updated  = 0
    errors: list[str] = []

    for row_num, row in enumerate(reader, start=2):  # start=2: row 1 is header
        name = _get(row, "name")
        if not name:
            errors.append(f"Row {row_num}: missing Entity Name — skipped")
            continue

        # Map category
        raw_cat = _get(row, "category").lower().strip()
        category = _CAT_MAP.get(raw_cat)  # None if not found — nullable column

        # Upsert by name (case-insensitive)
        try:
            existing = (
                db.query(_Insurer)
                .filter(_Insurer.name.ilike(name))
                .first()
            )
            if existing:
                # Update mutable fields
                if category:              existing.category            = category
                if _get(row, "address"): existing.head_office_address = _get(row, "address")
                if _get(row, "email"):   existing.email               = _get(row, "email")
                if _get(row, "phone"):   existing.phone               = _get(row, "phone")
                updated += 1
            else:
                new_insurer = _Insurer(
                    name                = name,
                    category            = category,
                    industry_segment    = _get(row, "type"),
                    head_office_address = _get(row, "address"),
                    email               = _get(row, "email"),
                    phone               = _get(row, "phone"),
                )
                db.add(new_insurer)
                imported += 1
        except Exception as exc:
            errors.append(f"Row {row_num} ({name!r}): {exc}")
            db.rollback()
            continue

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database commit failed: {exc}")

    logger.info("CSV import complete: imported=%d updated=%d errors=%d", imported, updated, len(errors))
    return {"imported": imported, "updated": updated, "errors": errors}


@router.post("/scrape/trigger")
def trigger_scrape(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """
    Trigger a named scraper in the background.
    Body: {"scraper": "ipec" | "zse" | "news"}
    Returns: {"run_id": int, "message": str}
    """
    scraper_name = payload.get("scraper", "").strip().lower()
    if scraper_name not in ("ipec", "zse", "news"):
        raise HTTPException(status_code=400, detail="scraper must be one of: ipec, zse, news")

    def _run():
        from app.infrastructure.scrapers.scraper_scheduler import run_scraper_now
        try:
            run_scraper_now(scraper_name)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Background scrape failed: %s", exc)

    background_tasks.add_task(_run)
    return {"message": f"{scraper_name} scraper triggered in background", "scraper": scraper_name}


# ── Per-insurer endpoints ─────────────────────────────────────────────────────

@router.get("")
def list_insurers(
    skip: int = 0,
    limit: int = 50,
    category: str | None = Query(None, description="Filter by category (e.g. short_term, life_assurance)"),
    zse_listed: bool | None = Query(None),
    search: str | None = Query(None, description="Fuzzy name search"),
    db: Session = Depends(get_db),
):
    """List insurers with optional category/ZSE/fuzzy-name filters."""
    from app.modules.insurers.model import Insurer
    from app.modules.financials.model import FinancialSnapshot, InsurerFinancials
    from app.modules.csp.model import CSPScore

    q = db.query(Insurer)
    if category:
        q = q.filter(Insurer.category == category)
    if zse_listed is not None:
        q = q.filter(Insurer.zse_listed == zse_listed)
    insurers = q.offset(skip).limit(limit).all()

    if search:
        try:
            from rapidfuzz import process, fuzz
            names = [i.name for i in insurers]
            results = process.extract(search, names, scorer=fuzz.partial_ratio, limit=limit)
            matched_names = {r[0] for r in results if r[1] >= 60}
            insurers = [i for i in insurers if i.name in matched_names]
        except ImportError:
            insurers = [i for i in insurers if search.lower() in i.name.lower()]

    insurer_ids = [i.id for i in insurers]

    latest_financials = {}
    latest_snapshots = {}
    if insurer_ids:
        latest_financial_keys = (
            db.query(
                InsurerFinancials.insurer_id.label("insurer_id"),
                func.max(
                    InsurerFinancials.period_year * 10
                    + func.coalesce(InsurerFinancials.period_quarter, 0)
                ).label("period_key"),
            )
            .filter(InsurerFinancials.insurer_id.in_(insurer_ids))
            .group_by(InsurerFinancials.insurer_id)
            .subquery()
        )
        latest_financials = {
            row.insurer_id: row
            for row in (
                db.query(InsurerFinancials)
                .join(
                    latest_financial_keys,
                    (InsurerFinancials.insurer_id == latest_financial_keys.c.insurer_id)
                    & (
                        (InsurerFinancials.period_year * 10 + func.coalesce(InsurerFinancials.period_quarter, 0))
                        == latest_financial_keys.c.period_key
                    ),
                )
                .all()
            )
        }
        latest_snapshot_keys = (
            db.query(
                FinancialSnapshot.insurer_id.label("insurer_id"),
                func.max(FinancialSnapshot.reporting_date).label("reporting_date"),
            )
            .filter(FinancialSnapshot.insurer_id.in_(insurer_ids))
            .group_by(FinancialSnapshot.insurer_id)
            .subquery()
        )
        latest_snapshots = {
            row.insurer_id: row
            for row in (
                db.query(FinancialSnapshot)
                .join(
                    latest_snapshot_keys,
                    (FinancialSnapshot.insurer_id == latest_snapshot_keys.c.insurer_id)
                    & (FinancialSnapshot.reporting_date == latest_snapshot_keys.c.reporting_date),
                )
                .all()
            )
        }

    latest_scores = {}
    if insurer_ids:
        latest_score_keys = (
            db.query(
                CSPScore.insurer_id.label("insurer_id"),
                func.max(CSPScore.scored_at).label("scored_at"),
            )
            .filter(CSPScore.insurer_id.in_(insurer_ids))
            .group_by(CSPScore.insurer_id)
            .subquery()
        )
        latest_scores = {
            row.insurer_id: row
            for row in (
                db.query(CSPScore)
                .join(
                    latest_score_keys,
                    (CSPScore.insurer_id == latest_score_keys.c.insurer_id)
                    & (CSPScore.scored_at == latest_score_keys.c.scored_at),
                )
                .all()
            )
        }

    return [
        _insurer_summary(
            i,
            latest_financials.get(i.id),
            latest_snapshots.get(i.id),
            latest_scores.get(i.id),
        )
        for i in insurers
    ]


@router.get("/{insurer_id}")
def get_insurer_profile(insurer_id: int, db: Session = Depends(get_db)):
    """Full insurer intelligence profile."""
    from app.modules.insurers.analytics_service import InsurerAnalytics
    profile = InsurerAnalytics().get_insurer_profile(db, insurer_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Insurer not found.")
    return profile


@router.get("/{insurer_id}/predict")
def predict_insurer(insurer_id: int, db: Session = Depends(get_db)):
    """Settlement power score + next-quarter revenue prediction."""
    from app.modules.insurers.model import Insurer
    insurer = db.query(Insurer).filter(Insurer.id == insurer_id).first()
    if not insurer:
        raise HTTPException(status_code=404, detail="Insurer not found.")
    from app.modules.ml.insurer_predictor import InsurerPredictor
    predictor = InsurerPredictor()
    return {
        "insurer_id":            insurer_id,
        "insurer_name":          insurer.name,
        "settlement_power_score": predictor.predict_settlement_score(db, insurer_id),
        "revenue_forecast":      predictor.predict_next_quarter_revenue(db, insurer_id),
    }


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_float(value) -> float | None:
    return float(value) if value is not None else None


def _snapshot_solvency_pct(snapshot) -> float | None:
    if not snapshot or snapshot.capital_adequacy_ratio is None:
        return None
    value = float(snapshot.capital_adequacy_ratio)
    return value * 100 if value <= 10 else value


def _insurer_summary(ins, financials=None, snapshot=None, csp_score=None) -> dict:
    solvency_ratio = (
        _to_float(financials.solvency_ratio_pct)
        if financials
        else _snapshot_solvency_pct(snapshot)
    )
    liquidity_ratio = (
        _to_float(financials.liquidity_ratio)
        if financials
        else _to_float(snapshot.liquidity_ratio) if snapshot else None
    )
    gross_claims_paid = (
        _to_float(financials.gross_claims_paid_usd)
        if financials
        else _to_float(snapshot.claims_paid) if snapshot else None
    )
    total_claims_reserves = (
        _to_float(financials.total_claims_reserves_usd)
        if financials
        else _to_float(snapshot.claims_reserves) if snapshot else None
    )
    gross_written_premium = (
        _to_float(financials.gross_premiums_written_usd)
        if financials
        else _to_float(snapshot.premiums_written) if snapshot else None
    )
    return {
        "id":                       ins.id,
        "name":                     ins.name,
        "short_name":               ins.short_name,
        "category":                 ins.category,
        "zse_listed":               ins.zse_listed,
        "zse_ticker":               ins.zse_ticker,
        "ipec_registration_status": ins.ipec_registration_status,
        "head_office_city":         ins.head_office_city,
        "icm_member":               ins.icm_member,
        "website":                  ins.website,
        "email":                    ins.email,
        "phone":                    ins.phone,
        "solvency_ratio":           solvency_ratio,
        "liquidity_ratio":          liquidity_ratio,
        "gross_claims_paid_usd":    gross_claims_paid,
        "total_claims_reserves_usd": total_claims_reserves,
        "gross_written_premium":    gross_written_premium,
        "latest_period_year":       financials.period_year if financials else None,
        "latest_period_quarter":    financials.period_quarter if financials else None,
        "latest_reporting_date":    snapshot.reporting_date.isoformat() if snapshot and snapshot.reporting_date else None,
        "financial_data_source":    financials.data_source if financials else snapshot.data_source if snapshot else None,
        "wcs_score":                _to_float(csp_score.wcs_score) if csp_score else None,
        "wcs_band":                 csp_score.wcs_band if csp_score else None,
        "wcs_scored_at":            csp_score.scored_at.isoformat() if csp_score and csp_score.scored_at else None,
    }
