"""
app/modules/csp/service.py
===========================
CSP Service — orchestrates Claims Settlement Power scoring, fuzzy insurer lookup,
report injection, and full-market rescoring.

Coordinates:
  - WCSScorer (deterministic weighted composite score)
  - CSPXGBoostModel (anomaly detection, optional)
  - CSPNaturalLanguageGenerator (broker-ready summaries)
  - Database persistence via SQLAlchemy Session
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.ai.inference.csp_nlg import CSPNaturalLanguageGenerator, XGBResult
from app.ai.inference.csp_wcs_scorer import WCSScorer
from app.ai.inference.csp_xgboost_model import CSPXGBoostModel
from app.modules.csp.model import CSPScore
from app.modules.insurers.model import Insurer
from app.modules.financials.model import InsurerFinancials

logger = logging.getLogger(__name__)


def _active_insurer_filter():
    return or_(
        Insurer.ipec_registration_status.is_(None),
        Insurer.ipec_registration_status == "active",
    )


def _fuzzy_match(query: str, candidates: list[str], threshold: int = 75) -> str | None:
    """Return best-matching candidate name if above the similarity threshold."""
    try:
        from rapidfuzz import fuzz

        best_score = 0.0
        best_match: str | None = None
        for candidate in candidates:
            score = fuzz.partial_ratio(query.lower(), candidate.lower())
            if score > best_score:
                best_score = score
                best_match = candidate
        if best_score >= threshold:
            return best_match
        return None

    except ImportError:
        logger.warning("rapidfuzz not installed — falling back to substring matching")
        query_lower = query.lower()
        for candidate in candidates:
            if query_lower in candidate.lower() or candidate.lower() in query_lower:
                return candidate
        return None


class CSPService:
    """
    Orchestrates the full Claims Settlement Power pipeline.

    Instantiate once at application startup. The XGBoost model is loaded lazily
    on first use so that missing model files do not prevent the service from starting.
    """

    def __init__(self) -> None:
        self._wcs_scorer = WCSScorer()
        self._nlg = CSPNaturalLanguageGenerator()
        self._xgb: CSPXGBoostModel | None = None

    def _get_xgb(self) -> CSPXGBoostModel:
        if self._xgb is None:
            self._xgb = CSPXGBoostModel()
            self._xgb.load()
        return self._xgb

    # ── Lookup ────────────────────────────────────────────────────────────────

    def get_csp_for_insurer(
        self,
        insurer_name: str,
        db: Session,
    ) -> dict[str, Any] | None:
        try:
            insurers = db.query(Insurer).filter(_active_insurer_filter()).all()
            if not insurers:
                return None

            names = [ins.name for ins in insurers]
            matched_name = _fuzzy_match(insurer_name, names)
            if not matched_name:
                logger.info("No fuzzy match for insurer: %r", insurer_name)
                return None

            insurer = next(i for i in insurers if i.name == matched_name)
            score_row = (
                db.query(CSPScore)
                .filter(CSPScore.insurer_id == insurer.id)
                .order_by(CSPScore.scored_at.desc())
                .first()
            )
            if not score_row:
                return None

            financials = db.query(InsurerFinancials).filter(
                InsurerFinancials.id == score_row.financials_id
            ).first()

            return self._serialize_score(score_row, insurer, financials)

        except Exception as exc:
            logger.error("get_csp_for_insurer failed: %s", exc, exc_info=True)
            return None

    def get_all_csp_scores(self, db: Session) -> list[dict[str, Any]]:
        try:
            latest_scores = (
                db.query(
                    CSPScore.insurer_id.label("insurer_id"),
                    func.max(CSPScore.scored_at).label("max_scored_at"),
                )
                .group_by(CSPScore.insurer_id)
                .subquery()
            )
            rows = (
                db.query(CSPScore, Insurer)
                .join(
                    latest_scores,
                    (CSPScore.insurer_id == latest_scores.c.insurer_id)
                    & (CSPScore.scored_at == latest_scores.c.max_scored_at),
                )
                .join(Insurer, Insurer.id == CSPScore.insurer_id)
                .filter(_active_insurer_filter())
                .all()
            )
            financial_ids = [score.financials_id for score, _ in rows]
            financial_map = {
                row.id: row
                for row in db.query(InsurerFinancials)
                .filter(InsurerFinancials.id.in_(financial_ids))
                .all()
            } if financial_ids else {}

            result = []
            for score_row, insurer in rows:
                result.append(
                    self._serialize_score(score_row, insurer, financial_map.get(score_row.financials_id))
                )
            return result
        except Exception as exc:
            logger.error("get_all_csp_scores failed: %s", exc, exc_info=True)
            return []

    # ── Scoring ───────────────────────────────────────────────────────────────

    def score_insurer(self, insurer_id: int, db: Session) -> dict[str, Any] | None:
        try:
            insurer = db.query(Insurer).filter(Insurer.id == insurer_id).first()
            if not insurer:
                logger.warning("score_insurer: insurer %r not found", insurer_id)
                return None

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
                logger.info("No financials for insurer %r — skipping", insurer.name)
                return None

            component_scores = self._wcs_scorer.score(
                solvency_ratio_pct=float(financials.solvency_ratio_pct),
                liquid_assets_usd=float(financials.liquid_assets_usd),
                gross_claims_paid_usd=float(financials.gross_claims_paid_usd),
                total_claims_reserves_usd=float(financials.total_claims_reserves_usd),
                current_assets_usd=float(financials.current_assets_usd),
                current_liabilities_usd=float(financials.current_liabilities_usd),
            )

            xgb = self._get_xgb()
            xgb_result: XGBResult | None = None
            shap_json: str | None = None

            if xgb.model is not None:
                features = {
                    "solvency_ratio_pct": float(financials.solvency_ratio_pct),
                    "settlement_capacity_months": component_scores.settlement_months,
                    "reserves_to_paid_ratio": component_scores.reserves_ratio,
                    "liquidity_ratio": component_scores.liquidity_ratio,
                    "claims_ratio_pct": float(financials.claims_ratio_pct),
                    "solvency_ratio_yoy_change": 0.0,
                    "claims_reserves_yoy_change": 0.0,
                    "premiums_yoy_change": 0.0,
                }
                prob, flag = xgb.predict_risk(features)
                shap_dict = xgb.get_shap_explanation(features)
                shap_sentence = xgb.shap_to_sentence(shap_dict)
                shap_json = json.dumps(shap_dict)
                xgb_result = XGBResult(
                    at_risk_probability=prob,
                    at_risk_flag=flag,
                    shap_sentence=shap_sentence,
                )

            summary, recommendation = self._nlg.generate(component_scores, xgb_result)

            score_row = CSPScore(
                insurer_id=insurer_id,
                financials_id=financials.id,
                solvency_score=component_scores.solvency_score,
                settlement_capacity_score=component_scores.settlement_capacity_score,
                reserves_adequacy_score=component_scores.reserves_adequacy_score,
                liquidity_score=component_scores.liquidity_score,
                wcs_score=component_scores.wcs_score,
                wcs_band=component_scores.wcs_band,
                xgb_at_risk_probability=xgb_result.at_risk_probability if xgb_result else 0.0,
                xgb_at_risk_flag=xgb_result.at_risk_flag if xgb_result else False,
                shap_values_json=shap_json,
                natural_language_summary=summary,
                broker_recommendation=recommendation,
                scored_at=datetime.now(timezone.utc),
            )
            db.add(score_row)
            db.commit()
            db.refresh(score_row)

            return self._serialize_score(score_row, insurer, financials)

        except Exception as exc:
            logger.error("score_insurer failed for %r: %s", insurer_id, exc, exc_info=True)
            db.rollback()
            return None

    def refresh_all_scores(self, db: Session) -> int:
        insurers = db.query(Insurer).filter(_active_insurer_filter()).all()
        updated = 0
        for insurer in insurers:
            result = self.score_insurer(insurer.id, db)
            if result:
                updated += 1
        logger.info("CSP refresh complete: %d insurers rescored", updated)
        return updated

    def inject_csp_into_report(
        self,
        report_id: str,
        insurer_name: str,
        db: Session,
    ) -> bool:
        try:
            csp = self.get_csp_for_insurer(insurer_name, db)
            if not csp:
                logger.info(
                    "inject_csp_into_report: no CSP data for %r (report %s)",
                    insurer_name,
                    report_id,
                )
                return False
            logger.info(
                "CSP injected into report %s for insurer %r (WCS=%.1f)",
                report_id,
                insurer_name,
                csp["wcs_score"],
            )
            return True

        except Exception as exc:
            logger.error(
                "inject_csp_into_report failed (report=%s, insurer=%r): %s",
                report_id,
                insurer_name,
                exc,
                exc_info=True,
            )
            return False

    # ── Serialization ─────────────────────────────────────────────────────────

    def _serialize_score(
        self,
        score: CSPScore,
        insurer: Insurer,
        financials: InsurerFinancials | None,
    ) -> dict[str, Any]:
        return {
            "insurer_id": insurer.id,
            "insurer_name": insurer.name,
            "insurer_short_name": insurer.short_name,
            "ipec_licence_number": insurer.registration_number,
            "wcs_score": score.wcs_score,
            "wcs_band": score.wcs_band,
            "solvency_score": score.solvency_score,
            "settlement_capacity_score": score.settlement_capacity_score,
            "reserves_adequacy_score": score.reserves_adequacy_score,
            "liquidity_score": score.liquidity_score,
            "xgb_at_risk_probability": score.xgb_at_risk_probability,
            "xgb_at_risk_flag": score.xgb_at_risk_flag,
            "shap_values": json.loads(score.shap_values_json) if score.shap_values_json else None,
            "natural_language_summary": score.natural_language_summary,
            "broker_recommendation": score.broker_recommendation,
            "scored_at": score.scored_at.isoformat() if score.scored_at else None,
            "model_version": score.model_version,
            "data_source": financials.data_source if financials else None,
            "solvency_ratio_pct": float(financials.solvency_ratio_pct) if financials else None,
            "liquid_assets_usd": float(financials.liquid_assets_usd) if financials else None,
            "gross_claims_paid_usd": float(financials.gross_claims_paid_usd) if financials else None,
        }
