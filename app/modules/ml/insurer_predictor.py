"""
InsurerPredictor — XGBoost-based settlement power score and revenue forecaster
for the Insurer Intelligence Module.

Models saved to: storage/models/app/settlement_model.joblib
                 storage/models/app/financial_model.joblib
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_MODEL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "storage", "models", "app"
)
_SETTLEMENT_MODEL_PATH = os.path.join(_MODEL_DIR, "settlement_model.joblib")
_FINANCIAL_MODEL_PATH  = os.path.join(_MODEL_DIR, "financial_model.joblib")
_SETTLEMENT_FEATS_PATH = os.path.join(_MODEL_DIR, "settlement_features.json")


class InsurerPredictor:
    """Stateless predictor — each method opens/closes its own resources."""

    # ── Feature matrix ─────────────────────────────────────────────────────────

    def build_feature_matrix(self, db, insurer_id: int):
        """
        Build a pandas DataFrame of features for insurer_id.
        Returns DataFrame with columns: financial features, claims features,
        sentiment features, and engineered growth features.
        """
        import pandas as pd
        from app.modules.financials.model import FinancialSnapshot
        from app.modules.insurers.claims_model import ClaimsMetrics
        from app.modules.news.model import NewsArticle
        from sqlalchemy import func

        # ── Financial history (cap at 20 periods) ──
        snaps = (
            db.query(FinancialSnapshot)
            .filter(FinancialSnapshot.insurer_id == insurer_id)
            .order_by(FinancialSnapshot.period_label.asc())
            .limit(20)
            .all()
        )

        rows: list[dict] = []
        for i, s in enumerate(snaps):
            prev = snaps[i - 1] if i > 0 else None

            def safe(val):
                return float(val) if val is not None else None

            revenue     = safe(s.total_revenue_usd)
            prev_rev    = safe(prev.total_revenue_usd) if prev else None
            assets      = safe(s.total_assets_usd)
            prev_assets = safe(prev.total_assets_usd) if prev else None
            cap_ratio   = safe(s.capital_adequacy_ratio)
            prev_cap    = safe(prev.capital_adequacy_ratio) if prev else None

            row = {
                "period_label":         s.period_label,
                # Financial
                "revenue":              revenue,
                "assets":               assets,
                "capital_adequacy_ratio": cap_ratio,
                "cash_pct":             safe(s.cash_and_bank_pct),
                "prescribed_pct":       safe(s.prescribed_assets_pct),
                "reinsurance_pct":      safe(s.reinsurance_assets_pct),
                "market_share":         safe(s.market_share_pct),
                "profit":               safe(s.profit_after_tax_usd),
                # Engineered growth features
                "revenue_growth_qoq":   (revenue - prev_rev) / prev_rev if (revenue and prev_rev and prev_rev != 0) else None,
                "asset_growth_qoq":     (assets - prev_assets) / prev_assets if (assets and prev_assets and prev_assets != 0) else None,
                "capital_ratio_trend":  (cap_ratio - prev_cap) if (cap_ratio and prev_cap) else None,
            }
            rows.append(row)

        df_fin = pd.DataFrame(rows) if rows else pd.DataFrame()

        # ── Claims features (cap at 20 periods) ──
        claims_rows = (
            db.query(ClaimsMetrics)
            .filter(ClaimsMetrics.insurer_id == insurer_id)
            .order_by(ClaimsMetrics.period_label.asc())
            .limit(20)
            .all()
        )
        claims_data: list[dict] = []
        for c in claims_rows:
            comp_rate = (c.complaints_count or 0) / max(c.total_policies_count or 1, 1)
            claims_data.append({
                "period_label":          c.period_label,
                "complaints_count":      c.complaints_count,
                "resolution_rate":       c.complaints_resolution_rate,
                "instalment_flag":       int(c.claims_instalment_flag or False),
                "working_capital_neg":   int(c.working_capital_negative or False),
                "current_ratio":         c.current_ratio,
                "total_policies":        c.total_policies_count,
                "complaint_rate":        round(comp_rate, 6),
                "settlement_power_score": c.settlement_power_score,  # target
            })
        df_claims = pd.DataFrame(claims_data) if claims_data else pd.DataFrame()

        # ── Sentiment features (single query with CASE counts) ──
        from sqlalchemy import case as sa_case
        cutoff_30d = datetime.utcnow() - timedelta(days=30)
        sent_agg = db.query(
            func.avg(NewsArticle.sentiment_score).label("avg"),
            func.sum(sa_case((NewsArticle.sentiment_label == "negative", 1), else_=0)).label("neg"),
            func.sum(sa_case((NewsArticle.sentiment_label == "positive", 1), else_=0)).label("pos"),
        ).filter(
            NewsArticle.insurer_id == insurer_id,
            NewsArticle.created_at >= cutoff_30d,
        ).first()
        sentiment_row = {
            "avg_score_30d":      float(sent_agg.avg) if sent_agg and sent_agg.avg else 0.0,
            "negative_count_30d": int(sent_agg.neg or 0) if sent_agg else 0,
            "positive_count_30d": int(sent_agg.pos or 0) if sent_agg else 0,
        }

        # ── Merge ──
        if df_fin.empty and df_claims.empty:
            return pd.DataFrame()

        if not df_fin.empty and not df_claims.empty:
            df = pd.merge(df_fin, df_claims, on="period_label", how="outer")
        elif not df_fin.empty:
            df = df_fin
        else:
            df = df_claims

        for k, v in sentiment_row.items():
            df[k] = v

        return df

    # ── Settlement model training ──────────────────────────────────────────────

    def train_settlement_model(self, db) -> dict:
        """
        Train XGBRegressor to predict settlement_power_score.
        Returns dict with train metrics (rmse, mae per fold).
        Saves model + feature list to storage/models/app/.
        """
        import pandas as pd
        import numpy as np
        from app.modules.insurers.model import Insurer

        insurers = db.query(Insurer).all()
        all_frames: list[pd.DataFrame] = []
        for ins in insurers:
            df = self.build_feature_matrix(db, ins.id)
            if not df.empty and "settlement_power_score" in df.columns:
                all_frames.append(df)

        if not all_frames:
            return {"error": "No training data available"}

        data = pd.concat(all_frames, ignore_index=True)
        feature_cols = [
            "revenue", "assets", "capital_adequacy_ratio", "cash_pct",
            "prescribed_pct", "reinsurance_pct", "market_share", "profit",
            "revenue_growth_qoq", "asset_growth_qoq", "capital_ratio_trend",
            "complaints_count", "resolution_rate", "instalment_flag",
            "working_capital_neg", "current_ratio", "total_policies",
            "complaint_rate", "avg_score_30d", "negative_count_30d", "positive_count_30d",
        ]
        # Only use columns that exist
        feature_cols = [c for c in feature_cols if c in data.columns]
        target = "settlement_power_score"

        df_clean = data[feature_cols + [target]].dropna(subset=[target])
        if len(df_clean) < 5:
            return {"error": f"Insufficient data: {len(df_clean)} rows"}

        X = df_clean[feature_cols].fillna(0).values
        y = df_clean[target].values

        return self._fit_and_save(X, y, feature_cols, _SETTLEMENT_MODEL_PATH, _SETTLEMENT_FEATS_PATH, "settlement")

    # ── Financial forecast training ────────────────────────────────────────────

    def train_financial_forecast_model(self, db) -> dict:
        """
        Train XGBRegressor to predict next-quarter total_revenue_usd.
        Target is revenue shifted by 1 period.
        """
        import pandas as pd
        import numpy as np
        from app.modules.insurers.model import Insurer

        insurers = db.query(Insurer).all()
        all_frames: list[pd.DataFrame] = []
        for ins in insurers:
            df = self.build_feature_matrix(db, ins.id)
            if not df.empty and "revenue" in df.columns:
                df = df.sort_values("period_label")
                df["next_revenue"] = df["revenue"].shift(-1)
                all_frames.append(df)

        if not all_frames:
            return {"error": "No training data available"}

        data = pd.concat(all_frames, ignore_index=True)
        feature_cols = [
            "revenue", "assets", "capital_adequacy_ratio", "cash_pct",
            "reinsurance_pct", "market_share", "profit", "revenue_growth_qoq",
            "avg_score_30d",
        ]
        feature_cols = [c for c in feature_cols if c in data.columns]
        target = "next_revenue"

        df_clean = data[feature_cols + [target]].dropna(subset=[target])
        if len(df_clean) < 5:
            return {"error": f"Insufficient data: {len(df_clean)} rows"}

        X = df_clean[feature_cols].fillna(0).values
        y = df_clean[target].values

        return self._fit_and_save(X, y, feature_cols, _FINANCIAL_MODEL_PATH, None, "financial")

    # ── Predict settlement score ───────────────────────────────────────────────

    def predict_settlement_score(self, db, insurer_id: int) -> float:
        """
        Predict settlement power score. Falls back to rule-based if model
        not available or insufficient history (< 4 periods).
        """
        df = self.build_feature_matrix(db, insurer_id)
        n_periods = len(df) if not df.empty else 0

        if n_periods >= 4 and os.path.exists(_SETTLEMENT_MODEL_PATH):
            try:
                return self._ml_predict_settlement(df)
            except Exception as exc:
                logger.warning("[insurer_predictor] ML settlement predict failed: %s — using rule-based", exc)

        return self._rule_based_settlement(db, insurer_id, df)

    def _ml_predict_settlement(self, df) -> float:
        import joblib
        import pandas as pd
        model = joblib.load(_SETTLEMENT_MODEL_PATH)
        with open(_SETTLEMENT_FEATS_PATH) as f:
            feature_cols = json.load(f)
        latest = df.tail(1).copy()
        X = latest[feature_cols].fillna(0).values
        score = float(model.predict(X)[0])
        return round(max(0.0, min(100.0, score)), 2)

    def _rule_based_settlement(self, db, insurer_id: int, df) -> float:
        """
        Rule-based fallback from spec:
        base=60, adjust for cap_ratio, cash_pct, instalment_flag,
        working_capital_negative, sentiment.
        """
        from app.modules.insurers.claims_model import ClaimsMetrics
        from app.modules.financials.model import FinancialSnapshot

        score = 60.0

        latest_fin = (
            db.query(FinancialSnapshot)
            .filter(FinancialSnapshot.insurer_id == insurer_id)
            .order_by(FinancialSnapshot.period_label.desc())
            .first()
        )
        latest_claims = (
            db.query(ClaimsMetrics)
            .filter(ClaimsMetrics.insurer_id == insurer_id)
            .order_by(ClaimsMetrics.period_label.desc())
            .first()
        )

        if latest_fin:
            cap = float(latest_fin.capital_adequacy_ratio or 0)
            if cap >= 1.5:
                score += 15
            elif cap >= 1.0:
                score += 5
            else:
                score -= 20

            cash = float(latest_fin.cash_and_bank_pct or 0)
            if cash >= 15:
                score += 10
            elif cash >= 8:
                score += 3
            else:
                score -= 10

        if latest_claims:
            if latest_claims.claims_instalment_flag:
                score -= 20
            if latest_claims.working_capital_negative:
                score -= 15
            res_rate = latest_claims.complaints_resolution_rate
            if res_rate is not None:
                score += (float(res_rate) - 70) * 0.3

        # Sentiment boost/penalty
        if not df.empty and "avg_score_30d" in df.columns:
            avg_sent = float(df["avg_score_30d"].iloc[-1] or 0)
            score += avg_sent * 10

        return round(max(0.0, min(100.0, score)), 2)

    # ── Predict next quarter revenue ───────────────────────────────────────────

    def predict_next_quarter_revenue(self, db, insurer_id: int) -> dict:
        """
        Predict next quarter total_revenue_usd for insurer_id.
        Returns: predicted_revenue_usd, ci_lower, ci_upper, current_period,
                 predicted_period, model_used.
        """
        from app.modules.financials.model import FinancialSnapshot

        df = self.build_feature_matrix(db, insurer_id)
        latest_snap = (
            db.query(FinancialSnapshot)
            .filter(FinancialSnapshot.insurer_id == insurer_id)
            .order_by(FinancialSnapshot.period_label.desc())
            .first()
        )
        current_period = latest_snap.period_label if latest_snap else "unknown"
        predicted_period = self._next_period_label(current_period)

        model_used = "rule_based"
        predicted: float | None = None

        if len(df) >= 4 and os.path.exists(_FINANCIAL_MODEL_PATH):
            try:
                import joblib
                model = joblib.load(_FINANCIAL_MODEL_PATH)
                feature_cols = [
                    "revenue", "assets", "capital_adequacy_ratio", "cash_pct",
                    "reinsurance_pct", "market_share", "profit", "revenue_growth_qoq",
                    "avg_score_30d",
                ]
                feature_cols = [c for c in feature_cols if c in df.columns]
                X = df.tail(1)[feature_cols].fillna(0).values
                predicted = round(float(model.predict(X)[0]), 2)
                model_used = "xgboost"
            except Exception as exc:
                logger.warning("[insurer_predictor] ML revenue predict failed: %s", exc)

        # Rule-based fallback: use avg growth rate
        if predicted is None and not df.empty and "revenue" in df.columns:
            revenues = df["revenue"].dropna().tolist()
            if len(revenues) >= 2:
                growth_rates = [
                    (revenues[i] - revenues[i-1]) / revenues[i-1]
                    for i in range(1, len(revenues))
                    if revenues[i-1] != 0
                ]
                avg_growth = sum(growth_rates) / len(growth_rates) if growth_rates else 0.05
                predicted = round(revenues[-1] * (1 + avg_growth), 2)
            elif revenues:
                predicted = revenues[-1]

        if predicted is None:
            predicted = 0.0

        ci_lower = round(predicted * 0.85, 2)
        ci_upper = round(predicted * 1.15, 2)

        return {
            "predicted_revenue_usd": predicted,
            "ci_lower":              ci_lower,
            "ci_upper":              ci_upper,
            "current_period":        current_period,
            "predicted_period":      predicted_period,
            "model_used":            model_used,
        }

    # ── Retrain all ───────────────────────────────────────────────────────────

    def retrain_all_models(self, db) -> dict:
        """Retrain both models. Called by scheduler on 1st of month."""
        logger.info("[insurer_predictor] retraining all models")
        result_s = self.train_settlement_model(db)
        result_f = self.train_financial_forecast_model(db)
        return {"settlement": result_s, "financial_forecast": result_f}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _fit_and_save(
        self,
        X,
        y,
        feature_cols: list[str],
        model_path: str,
        feats_path: str | None,
        label: str,
    ) -> dict:
        import numpy as np
        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.metrics import mean_squared_error, mean_absolute_error

        try:
            from xgboost import XGBRegressor
        except ImportError:
            return {"error": "xgboost not installed"}

        try:
            import joblib
        except ImportError:
            return {"error": "joblib not installed"}

        model = XGBRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbosity=0,
        )

        n_splits = min(3, len(X) - 1)
        if n_splits < 2:
            # Not enough data for cross-val — just fit on all
            model.fit(X, y)
            fold_metrics: list[dict] = []
        else:
            tscv = TimeSeriesSplit(n_splits=n_splits)
            fold_metrics = []
            for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
                model.fit(X[train_idx], y[train_idx])
                preds = model.predict(X[val_idx])
                rmse = float(np.sqrt(mean_squared_error(y[val_idx], preds)))
                mae  = float(mean_absolute_error(y[val_idx], preds))
                fold_metrics.append({"fold": fold + 1, "rmse": round(rmse, 4), "mae": round(mae, 4)})
                logger.info("[insurer_predictor] %s fold %d: RMSE=%.4f MAE=%.4f", label, fold + 1, rmse, mae)
            # Final fit on all data
            model.fit(X, y)

        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(model, model_path)
        logger.info("[insurer_predictor] saved %s model to %s", label, model_path)

        if feats_path:
            with open(feats_path, "w") as f:
                json.dump(feature_cols, f)

        return {"status": "ok", "features": len(feature_cols), "samples": len(X), "folds": fold_metrics}

    def _next_period_label(self, current: str) -> str:
        """Compute next quarter label from current (e.g. 'Q4_2024' → 'Q1_2025')."""
        if not current or "_" not in current:
            return "Q?_next"
        parts = current.split("_")
        if len(parts) != 2:
            return "Q?_next"
        q_str, year_str = parts
        try:
            q = int(q_str.replace("Q", ""))
            year = int(year_str)
        except ValueError:
            return "Q?_next"
        if q == 4:
            return f"Q1_{year + 1}"
        return f"Q{q + 1}_{year}"
