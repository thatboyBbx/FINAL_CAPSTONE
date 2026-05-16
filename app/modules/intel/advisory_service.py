"""
app/modules/intel/advisory_service.py
=======================================
Advisory Engine — generates structured AI-style advisories for each insurer by
fusing signals from ML risk scoring, news, circulars, financial features, and
ZSE price data.

Moved from app/services/advisory_service.py.
"""
import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_call(fn, *args, **kwargs):
    """Call fn, return None on any exception."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.debug("Advisory safe_call failed: %s", e)
        return None


def _ml_risk(insurer_id: int, db: Session) -> dict | None:
    from app.modules.ml.predictor import MLPredictor
    try:
        return MLPredictor().predict(db=db, insurer_id=insurer_id, profile="demo")
    except Exception:
        return None


def _fused_risk(insurer_id: int, db: Session) -> dict | None:
    from app.modules.scoring.fusion import compute_fused_risk
    try:
        r = compute_fused_risk(db=db, insurer_id=insurer_id, profile="demo")
        return {
            "fused_score": r.fused_score,
            "fused_label": r.fused_label,
            "ml_score":    r.ml_score,
            "news_score":  r.news_score_normalised,
            "circ_score":  r.circular_score_normalised,
        }
    except Exception:
        return None


def _fin_features(insurer_id: int, db: Session) -> dict | None:
    from app.modules.financials.features import compute_financial_features
    try:
        return compute_financial_features(db=db, insurer_id=insurer_id)
    except Exception:
        return None


def _news_features(insurer_id: int, db: Session) -> dict | None:
    from app.modules.news.features import compute_news_features
    try:
        return compute_news_features(db=db, insurer_id=insurer_id)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Rules engine
# ---------------------------------------------------------------------------

_URGENCY_LEVELS = ["LOW", "MODERATE", "HIGH", "CRITICAL"]


def _build_advisory(
    insurer_id: int,
    insurer_name: str,
    fused: dict | None,
    ml_pred: dict | None,
    fin: dict | None,
    news: dict | None,
    zse: dict | None,
) -> dict[str, Any]:
    """Apply rules across all signals → produce advisory dict."""
    actions: list[str] = []
    flags:   list[str] = []
    urgency_score = 0

    fused_label = (fused or {}).get("fused_label", "unknown")
    fused_score = (fused or {}).get("fused_score", 0.5)
    if fused_label == "high":
        urgency_score += 2
        flags.append("HIGH composite risk score detected")
        actions.append("Schedule immediate supervisory review and request full actuarial report.")
    elif fused_label == "moderate":
        urgency_score += 1
        flags.append("MODERATE composite risk — monitor trajectory closely")
        actions.append("Increase monitoring frequency. Request quarterly risk self-assessment.")

    ml_class = (ml_pred or {}).get("prediction_class", "unknown")
    ml_probs  = (ml_pred or {}).get("probabilities", {})
    high_prob = ml_probs.get("high", 0)
    if ml_class == "high":
        urgency_score += 1
        flags.append("ML model predicts HIGH settlement risk")
        actions.append("Engage insurer on claims reserves adequacy and settlement capacity.")
    if high_prob > 0.7:
        flags.append(f"ML high-risk probability: {high_prob*100:.0f}%")

    if fin:
        rai = fin.get("reserve_adequacy_index", 1.0)
        if rai is not None and rai < 1.0:
            urgency_score += 1
            flags.append(f"Reserve adequacy index below 1.0 ({rai:.2f}) — reserves may be insufficient")
            actions.append("Request independent reserve adequacy study.")
        cpi = fin.get("claims_pressure_indicator", 0.5)
        if cpi is not None and cpi > 0.85:
            urgency_score += 1
            flags.append(f"Claims pressure at {cpi*100:.0f}% of premiums — elevated loss ratio")
            actions.append("Review underwriting practices and pricing models.")
        lss = fin.get("liquidity_stress_score", 1.0)
        if lss is not None and lss > 2.5:
            urgency_score += 1
            flags.append("Liquidity stress elevated — potential short-term liquidity risk")
            actions.append("Assess liquid asset holdings against short-term obligations.")
        rdv = fin.get("reserve_depletion_velocity", 0)
        if rdv is not None and rdv < -1000:
            urgency_score += 1
            flags.append("Reserves declining faster than expected")
            actions.append("Investigate reserve drawdown triggers and adjust contribution rates.")

    if news:
        nr = news.get("news_risk_score", 0)
        if nr > 5:
            urgency_score += 1
            flags.append(f"High adverse news risk score ({nr:.1f})")
            actions.append("Review recent press coverage; engage communications team to assess reputational risk.")
        reg_events = news.get("regulatory_events", 0)
        if reg_events and reg_events > 0:
            urgency_score += 1
            flags.append(f"{reg_events} regulatory news events detected")
            actions.append("Confirm compliance with recent regulatory directives mentioned in news.")

    if zse:
        chg = zse.get("change_30d_pct", 0)
        if chg < -10:
            urgency_score += 1
            flags.append(f"ZSE price down {abs(chg):.1f}% in 30 days — market confidence declining")
            actions.append("Investigate drivers of share price decline. Engage investor relations.")
        elif chg > 15:
            flags.append(f"ZSE price up {chg:.1f}% in 30 days — market confidence positive")

    if not actions:
        actions.append("Continue routine monitoring schedule.")
        actions.append("Ensure next financial submission is on time and complete.")

    urgency_idx = min(urgency_score, len(_URGENCY_LEVELS) - 1)
    urgency     = _URGENCY_LEVELS[urgency_idx]
    summary = _generate_summary(insurer_name, urgency, fused_label, flags, zse)
    radar = _build_radar(fused, ml_pred, fin, news, zse)
    data_points = _build_data_points(insurer_id, fused, ml_pred, fin, news, zse)

    return {
        "insurer_id":    insurer_id,
        "insurer_name":  insurer_name,
        "urgency":       urgency,
        "urgency_score": urgency_score,
        "summary":       summary,
        "flags":         flags,
        "actions":       actions,
        "radar":         radar,
        "data_points":   data_points,
        "signals": {
            "fused_score": round(fused_score, 3) if fused_score else None,
            "fused_label": fused_label,
            "ml_class":    ml_class,
            "zse_change":  zse.get("change_30d_pct") if zse else None,
            "zse_ticker":  zse.get("ticker") if zse else None,
        },
    }


def _generate_summary(
    name: str,
    urgency: str,
    fused_label: str,
    flags: list[str],
    zse: dict | None,
) -> str:
    if urgency == "CRITICAL":
        intro = f"{name} presents a **CRITICAL risk profile** requiring immediate regulatory intervention."
    elif urgency == "HIGH":
        intro = f"{name} exhibits an **elevated risk profile** across multiple indicators, warranting urgent review."
    elif urgency == "MODERATE":
        intro = f"{name} shows **moderate risk signals** that require heightened monitoring and proactive engagement."
    else:
        intro = f"{name} is operating within **normal risk parameters** based on current data signals."

    parts = [intro]
    if flags:
        parts.append(f"Key concerns: {'; '.join(flags[:3])}.")
    if zse:
        chg = zse.get("change_30d_pct", 0)
        if abs(chg) > 5:
            direction = "gained" if chg > 0 else "lost"
            parts.append(f"Market data indicates the company has {direction} {abs(chg):.1f}% on the ZSE over the past 30 days.")
    parts.append("The advisory recommendations below are generated from the fused multi-signal risk engine combining ML predictions, financial stress indicators, news sentiment, and regulatory circular analysis.")
    return " ".join(parts)


def _build_radar(fused, ml_pred, fin, news, zse) -> dict:
    """Return 5-axis radar chart data (values 0–1)."""
    ml_score = 0.5
    if ml_pred:
        probs = ml_pred.get("probabilities", {})
        ml_score = probs.get("high", 0) * 1.0 + probs.get("moderate", 0) * 0.5
        ml_score = min(ml_score, 1.0)

    fused_score = (fused or {}).get("fused_score", 0.5) or 0.5
    news_score  = (fused or {}).get("news_score", 0.3) or 0.3

    fin_stress = 0.3
    if fin:
        vals = []
        rai = fin.get("reserve_adequacy_index")
        if rai is not None:
            vals.append(max(0, min(1, 1 - rai)))
        cpi = fin.get("claims_pressure_indicator")
        if cpi is not None:
            vals.append(max(0, min(1, cpi)))
        if vals:
            fin_stress = sum(vals) / len(vals)

    zse_risk = 0.3
    if zse:
        chg = zse.get("change_30d_pct", 0)
        zse_risk = max(0, min(1, (-chg + 15) / 30.0))

    return {
        "categories": ["ML Risk", "Fused Score", "News Signals", "Financial Stress", "Market Risk"],
        "values": [
            round(ml_score, 3),
            round(fused_score, 3),
            round(min(news_score * 1.5, 1.0), 3),
            round(fin_stress, 3),
            round(zse_risk, 3),
        ],
    }


def _build_data_points(insurer_id, fused, ml_pred, fin, news, zse) -> list[dict]:
    from datetime import date, timedelta
    today = date.today()
    points = []

    if fused:
        label = fused.get("fused_label", "?")
        points.append({
            "date":  today.isoformat(),
            "type":  "risk_score",
            "label": f"Fused Risk: {label.upper()} ({fused.get('fused_score', 0):.2f})",
            "color": "#ff6b6b" if label == "high" else "#ffd36d" if label == "moderate" else "#48f7c2",
        })

    if ml_pred and ml_pred.get("prediction_class"):
        points.append({
            "date":  (today - timedelta(days=3)).isoformat(),
            "type":  "ml_prediction",
            "label": f"ML Prediction: {ml_pred['prediction_class'].upper()}",
            "color": "#8c7bff",
        })

    if zse:
        chg = zse.get("change_30d_pct", 0)
        points.append({
            "date":  (today - timedelta(days=1)).isoformat(),
            "type":  "zse",
            "label": f"ZSE {zse.get('ticker', '')}: {chg:+.1f}%",
            "color": "#48f7c2" if chg > 0 else "#ff6b6b",
        })

    return points


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_advisory(insurer_id: int, db: Session, insurer_name: str = "") -> dict[str, Any]:
    """Generate a full advisory for a single insurer."""
    fused   = _fused_risk(insurer_id, db)
    ml_pred = _ml_risk(insurer_id, db)
    fin     = _fin_features(insurer_id, db)
    news    = _news_features(insurer_id, db)
    zse     = None

    result = _build_advisory(
        insurer_id=insurer_id,
        insurer_name=insurer_name or f"Insurer #{insurer_id}",
        fused=fused,
        ml_pred=ml_pred,
        fin=fin,
        news=news,
        zse=zse,
    )

    try:
        from app.modules.insurers.analytics_service import InsurerAnalytics  # noqa: PLC0415
        from app.modules.ml.insurer_predictor import InsurerPredictor          # noqa: PLC0415
        analytics = InsurerAnalytics()
        profile   = analytics.get_insurer_profile(db, insurer_id)
        sps       = InsurerPredictor().predict_settlement_score(db, insurer_id)

        ranking = analytics.get_claims_power_ranking(db)
        position = "Unranked"
        for r in ranking:
            if r["insurer_id"] == insurer_id:
                position = f"Rank #{r['rank']} by settlement score"
                break

        if sps >= 75:
            rec = "Strong settlement capacity. Recommend routine monitoring."
        elif sps >= 50:
            rec = "Moderate settlement capacity. Increase monitoring frequency."
        else:
            rec = "Settlement stress detected. Immediate supervisory engagement recommended."
        if profile.get("risk_flags"):
            rec += f" Flagged issues: {'; '.join(profile['risk_flags'][:3])}."

        result["insurer_intelligence"] = {
            "profile":                profile.get("insurer", {}),
            "risk_flags":             profile.get("risk_flags", []),
            "settlement_power_score": sps,
            "market_position":        position,
            "recommendation":         rec,
        }
    except Exception as exc:
        logger.debug("insurer_intelligence enrichment failed: %s", exc)
        result["insurer_intelligence"] = None

    return result
