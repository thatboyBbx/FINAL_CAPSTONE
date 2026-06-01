"""
settlement_router.py — Settlement Power (WCS) API endpoints.

Routes:
  GET  /api/settlement-power/all            — WCS for all insurers
  GET  /api/settlement-power/lookup         — autocomplete insurer names
  GET  /api/settlement-power/{insurer_id}   — WCS for a single insurer

WCS formula:
  WCS = (0.35 × solvency_score)
      + (0.30 × settlement_capacity_score)
      + (0.20 × reserves_adequacy_score)
      + (0.15 × liquidity_score)

Scores are normalised 0–100 using the CSP normaliser functions.
The XGBoost anomaly layer adds xgb_at_risk_flag and shap_values_json.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/settlement-power",
    tags=["settlement-power"],
    dependencies=[Depends(get_current_user)],
)


def _score_insurer(insurer_id: int, db: Session) -> dict:
    """
    Compute (or retrieve cached) WCS score for a single insurer.

    Strategy:
    1. Check the csp_scores table for a recent cached score.
    2. If none, compute on-the-fly from the latest financial snapshot
       using the CSP service.
    3. Return a flat dict matching the frontend chart data contract.

    Args:
        insurer_id: Primary key of the Insurer row.
        db:         SQLAlchemy session.

    Returns:
        dict with wcs_score, wcs_band, component scores, anomaly flags etc.

    Raises:
        HTTPException 404 if insurer not found.
    """
    from app.modules.insurers.model import Insurer              # noqa: PLC0415
    from app.modules.csp.model import CSPScore                        # noqa: PLC0415
    from app.modules.financials.model import InsurerFinancials        # noqa: PLC0415

    # Verify insurer exists
    insurer = db.query(Insurer).filter(Insurer.id == insurer_id).first()
    if not insurer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Insurer #{insurer_id} not found.",
        )

    # ── Try cached CSP score ──────────────────────────────────────────────────
    cached = (
        db.query(CSPScore)
        .filter(CSPScore.insurer_id == insurer_id)
        .order_by(CSPScore.scored_at.desc())
        .first()
    )
    if cached:
        return {
            "insurer_id":                 insurer_id,
            "insurer_name":               insurer.name,
            "wcs_score":                  cached.wcs_score,
            "wcs_band":                   cached.wcs_band,
            "solvency_score":             cached.solvency_score,
            "settlement_capacity_score":  cached.settlement_capacity_score,
            "reserves_adequacy_score":    cached.reserves_adequacy_score,
            "liquidity_score":            cached.liquidity_score,
            "xgb_at_risk_flag":           cached.xgb_at_risk_flag,
            "xgb_at_risk_probability":    cached.xgb_at_risk_probability,
            "shap_values_json":           cached.shap_values_json,
            "natural_language_summary":   cached.natural_language_summary,
            "broker_recommendation":      cached.broker_recommendation,
            "source":                     "cached",
        }

    # ── Compute on-the-fly from financials ────────────────────────────────────
    financials = (
        db.query(InsurerFinancials)
        .filter(InsurerFinancials.insurer_id == insurer_id)
        .order_by(
            InsurerFinancials.period_year.desc(),
            InsurerFinancials.period_quarter.desc(),
        )
        .first()
    )
    if not financials:
        # No financial data — return placeholder zeros
        return {
            "insurer_id":                 insurer_id,
            "insurer_name":               insurer.name,
            "wcs_score":                  0.0,
            "wcs_band":                   "No Data",
            "solvency_score":             0.0,
            "settlement_capacity_score":  0.0,
            "reserves_adequacy_score":    0.0,
            "liquidity_score":            0.0,
            "xgb_at_risk_flag":           False,
            "xgb_at_risk_probability":    0.0,
            "shap_values_json":           None,
            "natural_language_summary":   "No financial data available.",
            "broker_recommendation":      "",
            "source":                     "no_data",
        }

    try:
        from app.modules.csp.service import CSPService           # noqa: PLC0415
        svc    = CSPService()
        result = svc.score_insurer(insurer_id=insurer_id, db=db)
        if result is None:
            raise ValueError("CSP score could not be computed")
        return {
            "insurer_id":    insurer_id,
            "insurer_name":  insurer.name,
            "source":        "computed",
            **result,
        }
    except Exception as exc:
        logger.warning("CSP compute failed for insurer %s: %s", insurer_id, exc)
        # Return partial data from financials
        return {
            "insurer_id":                 insurer_id,
            "insurer_name":               insurer.name,
            "wcs_score":                  0.0,
            "wcs_band":                   "Error",
            "solvency_score":             0.0,
            "settlement_capacity_score":  0.0,
            "reserves_adequacy_score":    0.0,
            "liquidity_score":            0.0,
            "xgb_at_risk_flag":           False,
            "xgb_at_risk_probability":    0.0,
            "shap_values_json":           None,
            "natural_language_summary":   f"Score computation error: {exc}",
            "broker_recommendation":      "",
            "source":                     "error",
        }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/lookup")
def settlement_lookup(
    name: str | None = Query(None, description="Partial insurer name for autocomplete"),
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    Autocomplete insurer names matching the given query.

    Returns up to 10 matches as [{id, name}] dicts.

    Args:
        name: Partial name string to match.
        db:   Database session.
    """
    from app.modules.insurers.model import Insurer  # noqa: PLC0415
    q = db.query(Insurer)
    if name:
        q = q.filter(Insurer.name.ilike(f"%{name}%"))
    insurers = q.order_by(Insurer.name).limit(10).all()
    return [{"id": i.id, "name": i.name} for i in insurers]


@router.get("/all")
def settlement_power_all(db: Session = Depends(get_db)) -> dict:
    """
    Return WCS scores for all insurers that have financial data or cached scores.

    Returns:
        {"scores": [...], "count": N}
    """
    from app.modules.insurers.model import Insurer  # noqa: PLC0415
    from app.modules.csp.model import CSPScore            # noqa: PLC0415

    insurer_ids_with_scores: set[int] = {
        row[0]
        for row in db.query(CSPScore.insurer_id).distinct().all()
        if row[0] is not None
    }

    results = []
    for iid in insurer_ids_with_scores:
        try:
            results.append(_score_insurer(iid, db))
        except HTTPException:
            pass
        except Exception as exc:
            logger.warning("WCS all — failed for insurer %s: %s", iid, exc)

    # Sort by WCS score desc
    results.sort(key=lambda r: r.get("wcs_score", 0), reverse=True)
    return {"scores": results, "count": len(results)}


@router.get("/{insurer_id}")
def settlement_power_single(insurer_id: int, db: Session = Depends(get_db)) -> dict:
    """
    Compute WCS for a single insurer.

    Args:
        insurer_id: The Insurer primary key.
        db:         Database session.

    Returns:
        WCS score dict with all component scores and SHAP values.

    Raises:
        HTTPException 404 if insurer not found.
    """
    return _score_insurer(insurer_id, db)
