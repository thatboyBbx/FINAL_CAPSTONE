"""
CSP API Routes — Claims Settlement Power analytics endpoints.

Endpoints:
  GET  /analytics/settlement-power/
       Renders settlement_power.html with all insurer CSP scores.

  GET  /analytics/settlement-power/lookup?insurer=<name>
       Returns CSP JSON for the matched insurer (fuzzy search).
       404 if no match.

  GET  /analytics/settlement-power/chart-data
       Returns arrays of equal length for Chart.js rendering.

  POST /internal/csp/force-refresh
       ADMIN role: triggers full scrape + rescore pipeline as background task.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["CSP — Claims Settlement Power"],
    dependencies=[Depends(get_current_user)],
)

# Lazy singleton — avoids heavyweight imports at module load time
_csp_service = None


def _get_csp_service():
    global _csp_service
    if _csp_service is None:
        try:
            from app.modules.csp.service import CSPService
            _csp_service = CSPService()
        except Exception as exc:
            logger.error("Failed to initialise CSPService: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=503,
                detail={
                    "error_type": "CSP Service Unavailable",
                    "error_msg": f"Claims Settlement Power service could not initialise: {exc}",
                    "user_action": "Check server logs. Ensure all ML dependencies are installed.",
                },
            )
    return _csp_service


# ── Settlement Power page ─────────────────────────────────────────────────────

@router.get("/analytics/settlement-power/")
def settlement_power_page(
    request: Any,
    db: Session = Depends(get_db),
):
    """Render the Settlement Power analytics sub-tab."""
    try:
        from fastapi.templating import Jinja2Templates
        from pathlib import Path

        templates = Jinja2Templates(
            directory=str(Path(__file__).parent.parent.parent / "ui" / "templates")
        )
        csp_service = _get_csp_service()
        all_scores = csp_service.get_all_csp_scores(db)

        return templates.TemplateResponse(
            request,
            "analytics/settlement_power.html",
            {
                "request": request,
                "all_scores": all_scores,
                "total_insurers": len(all_scores),
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("settlement_power_page failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "Page Load Failed",
                "error_msg": str(exc),
                "user_action": "Refresh the page. If the problem persists, check server logs.",
            },
        )


# ── Lookup endpoint ───────────────────────────────────────────────────────────

@router.get("/analytics/settlement-power/lookup")
def lookup_insurer_csp(
    insurer: Annotated[str, Query(description="Insurer name (partial or full)")],
    db: Session = Depends(get_db),
):
    """
    Fuzzy-match an insurer by name and return its most recent CSP score.

    Returns 404 with a structured error if no match is found.
    """
    try:
        if not insurer or not insurer.strip():
            raise HTTPException(status_code=400, detail={
                "error_type": "Missing Parameter",
                "error_msg": "The 'insurer' query parameter is required.",
                "user_action": "Provide an insurer name to search.",
            })

        csp_service = _get_csp_service()
        result = csp_service.get_csp_for_insurer(insurer.strip(), db)

        if result is None:
            raise HTTPException(status_code=404, detail={
                "error_type": "Insurer Not Found",
                "error_msg": f"No Settlement Power data found for '{insurer}'.",
                "user_action": (
                    "Verify the insurer name or check IPEC FSR-1 filings manually. "
                    "Data is refreshed quarterly."
                ),
            })

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("lookup_insurer_csp failed for %r: %s", insurer, exc, exc_info=True)
        raise HTTPException(status_code=500, detail={
            "error_type": "Lookup Failed",
            "error_msg": str(exc),
            "user_action": "Try again. If the problem persists, contact support.",
        })


# ── Chart data endpoint ───────────────────────────────────────────────────────

@router.get("/analytics/settlement-power/chart-data")
def csp_chart_data(db: Session = Depends(get_db)):
    """
    Return all insurer CSP scores as parallel arrays for Chart.js.

    All arrays have identical length — one entry per active insurer with data.

    Returns:
        {
            "labels":           ["Insurer A", ...],
            "short_names":      ["Short A", ...],
            "solvency":         [float, ...],
            "settlement":       [float, ...],
            "reserves":         [float, ...],
            "liquidity":        [float, ...],
            "wcs":              [float, ...],
            "bands":            ["Strong", ...],
            "at_risk":          [bool, ...],
        }
    """
    try:
        csp_service = _get_csp_service()
        all_scores = csp_service.get_all_csp_scores(db)

        # Sort by WCS descending for the bar chart
        all_scores.sort(key=lambda s: s["wcs_score"], reverse=True)

        return {
            "labels": [s["insurer_name"] for s in all_scores],
            "short_names": [s["insurer_short_name"] for s in all_scores],
            "solvency": [s["solvency_score"] for s in all_scores],
            "settlement": [s["settlement_capacity_score"] for s in all_scores],
            "reserves": [s["reserves_adequacy_score"] for s in all_scores],
            "liquidity": [s["liquidity_score"] for s in all_scores],
            "wcs": [s["wcs_score"] for s in all_scores],
            "bands": [s["wcs_band"] for s in all_scores],
            "at_risk": [s["xgb_at_risk_flag"] for s in all_scores],
        }

    except Exception as exc:
        logger.error("csp_chart_data failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail={
            "error_type": "Chart Data Error",
            "error_msg": str(exc),
            "user_action": "Refresh the page. Data may not yet be available for all insurers.",
        })


# ── Admin: force refresh ──────────────────────────────────────────────────────

@router.post("/internal/csp/force-refresh")
def force_csp_refresh(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Trigger a full IPEC scrape + CSP rescore pipeline as a background task.
    Requires ADMIN role in production — currently unprotected for demo purposes.
    """
    import uuid

    job_id = str(uuid.uuid4())

    def _run_refresh():
        try:
            logger.info("CSP force-refresh started (job_id=%s)", job_id)
            csp_service = _get_csp_service()
            updated = csp_service.refresh_all_scores(db)
            logger.info("CSP force-refresh complete: %d insurers updated (job_id=%s)", updated, job_id)
        except Exception as exc:
            logger.error("CSP force-refresh failed (job_id=%s): %s", job_id, exc, exc_info=True)

    background_tasks.add_task(_run_refresh)

    return {"job_id": job_id, "status": "started"}
