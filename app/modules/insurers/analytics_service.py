"""
InsurerAnalytics — analytics methods for the Insurer Intelligence Module.

All methods take a SQLAlchemy Session and return JSON-serialisable dicts.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.modules.insurers.model import Insurer
from app.modules.financials.model import FinancialSnapshot
from app.modules.insurers.claims_model import ClaimsMetrics
from app.modules.news.model import NewsArticle

logger = logging.getLogger(__name__)


class InsurerAnalytics:
    """Stateless service class — instantiate once and call methods with a db Session."""

    # ── Market Overview ────────────────────────────────────────────────────────

    def get_market_overview(self, db: Session, period_label: str | None = None) -> dict:
        """
        Sector-wide summary for a given period (or latest available if omitted).
        Returns keys: total_sector_revenue_usd, total_sector_assets_usd,
        active_insurer_count, market_leaders, zse_listed_count, category_breakdown.
        """
        # Resolve period_label
        if not period_label:
            row = (
                db.query(FinancialSnapshot.period_label)
                .filter(FinancialSnapshot.period_label.isnot(None))
                .order_by(FinancialSnapshot.period_label.desc())
                .first()
            )
            period_label = row[0] if row else None

        # Single query: active count, ZSE count, and category breakdown
        agg = db.query(
            func.count(Insurer.id).label("total"),
            func.sum(case((Insurer.ipec_registration_status == "active", 1), else_=0)).label("active"),
            func.sum(case((Insurer.zse_listed == True, 1), else_=0)).label("zse"),
        ).first()
        active_count = int(agg.active or 0)
        zse_count    = int(agg.zse or 0)

        cat_rows = (
            db.query(Insurer.category, func.count(Insurer.id))
            .group_by(Insurer.category)
            .all()
        )
        category_breakdown = {str(cat or "unknown"): cnt for cat, cnt in cat_rows}

        # Financial aggregates
        total_revenue = total_assets = None
        market_leaders: list[dict] = []

        if period_label:
            # Aggregate totals in DB; fetch top-5 with JOIN to avoid N+1
            totals = db.query(
                func.sum(FinancialSnapshot.total_revenue_usd).label("rev"),
                func.sum(FinancialSnapshot.total_assets_usd).label("assets"),
            ).filter(FinancialSnapshot.period_label == period_label).first()
            total_revenue = round(float(totals.rev), 2) if totals.rev else None
            total_assets  = round(float(totals.assets), 2) if totals.assets else None

            top5_rows = (
                db.query(FinancialSnapshot, Insurer)
                .join(Insurer, FinancialSnapshot.insurer_id == Insurer.id)
                .filter(
                    FinancialSnapshot.period_label == period_label,
                    FinancialSnapshot.total_revenue_usd.isnot(None),
                )
                .order_by(FinancialSnapshot.total_revenue_usd.desc())
                .limit(5)
                .all()
            )
            for snap, insurer in top5_rows:
                market_leaders.append({
                    "insurer_id":   snap.insurer_id,
                    "name":         insurer.name,
                    "revenue_usd":  float(snap.total_revenue_usd or 0),
                    "market_share": float(snap.market_share_pct or 0),
                })

        return {
            "period_label":            period_label,
            "total_sector_revenue_usd": total_revenue,
            "total_sector_assets_usd":  total_assets,
            "active_insurer_count":     active_count,
            "zse_listed_count":         zse_count,
            "market_leaders":           market_leaders,
            "category_breakdown":       category_breakdown,
        }

    # ── Insurer Profile ────────────────────────────────────────────────────────

    def get_insurer_profile(self, db: Session, insurer_id: int) -> dict:
        """
        Full profile: insurer fields, latest financials, latest claims,
        financial trend, 30-day sentiment summary, risk flags, settlement score.
        """
        insurer = db.query(Insurer).filter(Insurer.id == insurer_id).first()
        if not insurer:
            return {}

        # Latest financials
        latest_fin = (
            db.query(FinancialSnapshot)
            .filter(FinancialSnapshot.insurer_id == insurer_id)
            .order_by(FinancialSnapshot.period_label.desc())
            .first()
        )

        # Latest claims
        latest_claims = (
            db.query(ClaimsMetrics)
            .filter(ClaimsMetrics.insurer_id == insurer_id)
            .order_by(ClaimsMetrics.period_label.desc())
            .first()
        )

        # Financial trend (all periods asc)
        trend = (
            db.query(FinancialSnapshot)
            .filter(FinancialSnapshot.insurer_id == insurer_id)
            .order_by(FinancialSnapshot.period_label.asc())
            .all()
        )

        # 30-day sentiment
        cutoff = datetime.utcnow() - timedelta(days=30)
        recent_articles = (
            db.query(NewsArticle)
            .filter(
                NewsArticle.insurer_id == insurer_id,
                NewsArticle.created_at >= cutoff,
            )
            .order_by(NewsArticle.published_date.desc())
            .limit(10)
            .all()
        )
        sentiment_summary = self._compute_sentiment_summary(recent_articles)

        # Risk flags
        risk_flags = self.compute_risk_flags(
            insurer_id,
            latest_fin,
            latest_claims,
            sentiment_summary.get("label_30d"),
        )

        return {
            "insurer": self._insurer_to_dict(insurer),
            "latest_financials": self._snapshot_to_dict(latest_fin),
            "latest_claims":     self._claims_to_dict(latest_claims),
            "financial_trend":   [self._snapshot_to_dict(s) for s in trend],
            "sentiment_summary": sentiment_summary,
            "risk_flags":        risk_flags,
            "settlement_power_score": latest_claims.settlement_power_score if latest_claims else None,
        }

    # ── Financial Comparison ───────────────────────────────────────────────────

    def get_financial_comparison(
        self, db: Session, insurer_ids: list[int], period_label: str | None = None
    ) -> dict:
        """Keyed by insurer name — financial snapshot for each insurer for the period."""
        result: dict[str, Any] = {}
        for ins_id in insurer_ids:
            insurer = db.query(Insurer).filter(Insurer.id == ins_id).first()
            if not insurer:
                continue
            q = db.query(FinancialSnapshot).filter(FinancialSnapshot.insurer_id == ins_id)
            if period_label:
                q = q.filter(FinancialSnapshot.period_label == period_label)
            snap = q.order_by(FinancialSnapshot.period_label.desc()).first()
            result[insurer.name] = self._snapshot_to_dict(snap)
        return result

    # ── Market Position Chart Data ─────────────────────────────────────────────

    def get_market_position_chart_data(
        self, db: Session, period_label: str | None = None, category: str = "short_term"
    ) -> dict:
        """
        Top 10 insurers by revenue for Plotly horizontal bar chart.
        Returns: labels, revenue_values, market_share_values, colors.
        ZSE-listed → gold (#C9A84C), non-listed → #4a4a4a.
        """
        if not period_label:
            row = (
                db.query(FinancialSnapshot.period_label)
                .filter(FinancialSnapshot.period_label.isnot(None))
                .order_by(FinancialSnapshot.period_label.desc())
                .first()
            )
            period_label = row[0] if row else None

        q = (
            db.query(FinancialSnapshot, Insurer)
            .join(Insurer, FinancialSnapshot.insurer_id == Insurer.id)
            .filter(FinancialSnapshot.total_revenue_usd.isnot(None))
        )
        if period_label:
            q = q.filter(FinancialSnapshot.period_label == period_label)
        if category:
            q = q.filter(Insurer.category == category)

        rows = q.order_by(FinancialSnapshot.total_revenue_usd.desc()).limit(10).all()

        labels, revenues, shares, colors = [], [], [], []
        for snap, ins in rows:
            labels.append(ins.short_name or ins.name)
            revenues.append(float(snap.total_revenue_usd or 0))
            shares.append(float(snap.market_share_pct or 0))
            colors.append("#C9A84C" if ins.zse_listed else "#4a4a4a")

        return {
            "period_label": period_label,
            "category":     category,
            "labels":       labels,
            "revenue_values":      revenues,
            "market_share_values": shares,
            "colors":       colors,
        }

    # ── Claims Power Ranking ───────────────────────────────────────────────────

    def get_claims_power_ranking(self, db: Session, period_label: str | None = None) -> list[dict]:
        """
        List of insurers ranked by settlement_power_score desc.
        Includes 30-day sentiment merged in.
        """
        q = db.query(ClaimsMetrics, Insurer).join(
            Insurer, ClaimsMetrics.insurer_id == Insurer.id
        )
        if period_label:
            q = q.filter(ClaimsMetrics.period_label == period_label)

        rows = q.order_by(
            ClaimsMetrics.settlement_power_score.desc().nullslast()
        ).limit(50).all()

        # Bulk-fetch 30-day avg sentiment for all insurer IDs in one query
        cutoff = datetime.utcnow() - timedelta(days=30)
        ins_ids = [ins.id for _, ins in rows]
        sentiment_rows = (
            db.query(NewsArticle.insurer_id, func.avg(NewsArticle.sentiment_score))
            .filter(
                NewsArticle.insurer_id.in_(ins_ids),
                NewsArticle.created_at >= cutoff,
            )
            .group_by(NewsArticle.insurer_id)
            .all()
        ) if ins_ids else []
        sentiment_map = {ins_id: float(avg) for ins_id, avg in sentiment_rows if avg is not None}

        ranking: list[dict] = []
        for claims, ins in rows:
            score_30d = sentiment_map.get(ins.id)
            ranking.append({
                "rank":                   len(ranking) + 1,
                "insurer_id":             ins.id,
                "name":                   ins.name,
                "category":               ins.category,
                "settlement_power_score": claims.settlement_power_score,
                "complaints_resolution_rate": claims.complaints_resolution_rate,
                "claims_instalment_flag": claims.claims_instalment_flag,
                "avg_sentiment_30d":      round(score_30d, 4) if score_30d is not None else None,
                "period_label":           claims.period_label,
            })
        return ranking

    # ── Sentiment Heatmap ──────────────────────────────────────────────────────

    def get_sentiment_heatmap(self, db: Session, days_back: int = 90) -> list[dict]:
        """
        Per-insurer weekly sentiment scores for heatmap rendering.
        Returns list of: insurer_id, name, weekly_scores [{week_start, avg_score, article_count}].
        """
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        articles = (
            db.query(NewsArticle)
            .filter(
                NewsArticle.created_at >= cutoff,
                NewsArticle.sentiment_score.isnot(None),
            )
            .order_by(NewsArticle.insurer_id, NewsArticle.published_date)
            .all()
        )

        # Group by insurer → weekly buckets
        insurer_articles: dict[int, list] = {}
        for art in articles:
            insurer_articles.setdefault(art.insurer_id, []).append(art)

        # Batch-load all insurers in one query
        insurer_map: dict[int, Any] = {
            i.id: i
            for i in db.query(Insurer).filter(Insurer.id.in_(list(insurer_articles.keys()))).all()
        }

        heatmap: list[dict] = []
        for ins_id, arts in insurer_articles.items():
            insurer = insurer_map.get(ins_id)
            if not insurer:
                continue
            weekly: dict[str, dict] = {}
            for art in arts:
                # ISO week start (Monday)
                if isinstance(art.published_date, date):
                    pub = art.published_date
                else:
                    pub = date.today()
                week_start = (pub - timedelta(days=pub.weekday())).isoformat()
                if week_start not in weekly:
                    weekly[week_start] = {"total": 0.0, "count": 0}
                weekly[week_start]["total"] += float(art.sentiment_score or 0)
                weekly[week_start]["count"] += 1

            weekly_scores = [
                {
                    "week_start":    ws,
                    "avg_score":     round(v["total"] / v["count"], 4) if v["count"] else 0,
                    "article_count": v["count"],
                }
                for ws, v in sorted(weekly.items())
            ]
            heatmap.append({
                "insurer_id":    ins_id,
                "name":          insurer.name,
                "short_name":    insurer.short_name,
                "weekly_scores": weekly_scores,
            })

        return heatmap

    # ── Risk Flags ─────────────────────────────────────────────────────────────

    def compute_risk_flags(
        self,
        insurer_id: int,
        financials,   # FinancialSnapshot | None
        claims,       # ClaimsMetrics | None
        sentiment_label_30d: str | None = None,
    ) -> list[str]:
        """
        8-check risk flag computation per spec.
        Returns list of human-readable warning strings.
        """
        flags: list[str] = []

        if financials:
            cap_ratio = float(financials.capital_adequacy_ratio or 0)
            if cap_ratio and cap_ratio < 1.0:
                flags.append(f"Capital below minimum requirement (CAR={cap_ratio:.2f})")

            cash_pct = float(financials.cash_and_bank_pct or 0)
            if cash_pct and cash_pct < 5.0:
                flags.append(f"Low cash & bank reserves ({cash_pct:.1f}% of assets)")

            reins_pct = float(financials.reinsurance_assets_pct or 0)
            if reins_pct and reins_pct < 10.0:
                flags.append(f"Low reinsurance asset cover ({reins_pct:.1f}%)")

            pres_pct = float(financials.prescribed_assets_pct or 0)
            # IPEC requires >=10% prescribed assets for life; flag if below
            if pres_pct and pres_pct < 10.0:
                flags.append(f"Prescribed assets below regulatory minimum ({pres_pct:.1f}%)")

        if claims:
            if claims.working_capital_negative:
                flags.append("Negative working capital detected")

            if claims.claims_instalment_flag:
                flags.append("Claims being paid in instalments (liquidity concern)")

            res_rate = claims.complaints_resolution_rate
            if res_rate is not None and float(res_rate) < 70.0:
                flags.append(f"Low complaint resolution rate ({float(res_rate):.1f}%)")

        if sentiment_label_30d == "negative":
            flags.append("Negative news sentiment over last 30 days")

        return flags

    # ── Serialisation helpers ──────────────────────────────────────────────────

    def _insurer_to_dict(self, ins) -> dict:
        if not ins:
            return {}
        return {
            "id":                      ins.id,
            "name":                    ins.name,
            "short_name":              ins.short_name,
            "category":                ins.category,
            "zse_listed":              ins.zse_listed,
            "zse_ticker":              ins.zse_ticker,
            "parent_group":            ins.parent_group,
            "head_office_city":        ins.head_office_city,
            "ipec_registration_status": ins.ipec_registration_status,
            "icm_member":              ins.icm_member,
            "website":                 ins.website,
            "date_established":        ins.date_established.isoformat() if ins.date_established else None,
        }

    def _snapshot_to_dict(self, s) -> dict:
        if not s:
            return {}
        return {
            "period_label":             s.period_label,
            "period_type":              s.period_type,
            "total_revenue_usd":        float(s.total_revenue_usd)        if s.total_revenue_usd        else None,
            "insurance_revenue_usd":    float(s.insurance_revenue_usd)    if s.insurance_revenue_usd    else None,
            "total_assets_usd":         float(s.total_assets_usd)         if s.total_assets_usd         else None,
            "total_liabilities_usd":    float(s.total_liabilities_usd)    if s.total_liabilities_usd    else None,
            "capital_position_usd":     float(s.capital_position_usd)     if s.capital_position_usd     else None,
            "minimum_capital_requirement_usd": float(s.minimum_capital_requirement_usd) if s.minimum_capital_requirement_usd else None,
            "capital_adequacy_ratio":   float(s.capital_adequacy_ratio)   if s.capital_adequacy_ratio   else None,
            "market_share_pct":         float(s.market_share_pct)         if s.market_share_pct         else None,
            "profit_after_tax_usd":     float(s.profit_after_tax_usd)     if s.profit_after_tax_usd     else None,
            "cash_and_bank_pct":        float(s.cash_and_bank_pct)        if s.cash_and_bank_pct        else None,
            "prescribed_assets_pct":    float(s.prescribed_assets_pct)    if s.prescribed_assets_pct    else None,
            "reinsurance_assets_pct":   float(s.reinsurance_assets_pct)   if s.reinsurance_assets_pct   else None,
            "data_source":              s.data_source,
        }

    def _claims_to_dict(self, c) -> dict:
        if not c:
            return {}
        return {
            "period_label":              c.period_label,
            "total_policies_count":      c.total_policies_count,
            "complaints_count":          c.complaints_count,
            "complaints_resolved_count": c.complaints_resolved_count,
            "complaints_resolution_rate": c.complaints_resolution_rate,
            "claims_instalment_flag":    c.claims_instalment_flag,
            "working_capital_negative":  c.working_capital_negative,
            "current_ratio":             c.current_ratio,
            "liquidity_score":           c.liquidity_score,
            "settlement_power_score":    c.settlement_power_score,
        }

    def _compute_sentiment_summary(self, articles: list) -> dict:
        if not articles:
            return {"avg_score_30d": None, "label_30d": "neutral", "recent_articles": []}

        scores = [float(a.sentiment_score) for a in articles if a.sentiment_score is not None]
        avg = round(sum(scores) / len(scores), 4) if scores else 0.0

        if avg >= 0.05:
            label = "positive"
        elif avg <= -0.05:
            label = "negative"
        else:
            label = "neutral"

        recent = [
            {
                "title":          a.title,
                "published_date": a.published_date.isoformat() if a.published_date else None,
                "sentiment_label": a.sentiment_label,
                "sentiment_score": float(a.sentiment_score) if a.sentiment_score else None,
                "url":            a.url,
            }
            for a in articles[:5]
        ]

        return {"avg_score_30d": avg, "label_30d": label, "recent_articles": recent}
