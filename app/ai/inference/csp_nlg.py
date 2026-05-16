"""
CSP Natural Language Generator.

Pure rule-based template engine — no API calls, no external dependencies beyond
the WCS scorer.  Deterministic: the same inputs always produce the same output.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.ai.inference.csp_wcs_scorer import CSPComponentScores


@dataclass
class XGBResult:
    """Result from the XGBoost anomaly classifier."""

    at_risk_probability: float
    at_risk_flag: bool
    shap_sentence: str | None


_BAND_OPENERS: dict[str, str] = {
    "Strong": (
        "Claims Settlement Power: {score:.0f}/100 — Strong. "
        "This insurer's capital adequacy and liquidity indicators are within the "
        "upper tier of IPEC-licensed insurers."
    ),
    "Adequate": (
        "Claims Settlement Power: {score:.0f}/100 — Adequate. "
        "This insurer meets IPEC regulatory capital requirements with moderate "
        "liquidity buffers."
    ),
    "Marginal": (
        "Claims Settlement Power: {score:.0f}/100 — Marginal. "
        "This insurer's capital adequacy is within regulatory parameters but "
        "certain indicators warrant monitoring."
    ),
    "Weak": (
        "Claims Settlement Power: {score:.0f}/100 — Weak. "
        "Capital adequacy indicators are below benchmark on multiple dimensions — "
        "enhanced due diligence is recommended."
    ),
    "Critical": (
        "Claims Settlement Power: {score:.0f}/100 — Critical. "
        "Capital adequacy indicators are below IPEC regulatory thresholds — "
        "escalation to a senior broker is warranted before policy placement."
    ),
}

_BAND_CLOSING: dict[str, str] = {
    "Strong": "No enhanced due diligence required at this time.",
    "Adequate": "Recommend monitoring quarterly IPEC filings for this insurer.",
    "Marginal": "Recommend monitoring quarterly IPEC filings for this insurer.",
    "Weak": "Enhanced due diligence recommended before policy placement.",
    "Critical": (
        "Escalate to senior broker — capital adequacy indicators are below "
        "IPEC regulatory threshold."
    ),
}


class CSPNaturalLanguageGenerator:
    """Generates broker-ready natural language summaries from CSP score objects."""

    _FORBIDDEN = frozenset(
        ["risky", "dangerous", "failing", "avoid", "do not use"]
    )

    def generate(
        self,
        scores: CSPComponentScores,
        xgb_result: XGBResult | None,
    ) -> tuple[str, str]:
        from app.ai.inference.csp_wcs_scorer import WCSScorer

        opener = _BAND_OPENERS.get(scores.wcs_band, _BAND_OPENERS["Critical"])
        opening = opener.format(score=scores.wcs_score)

        scorer = WCSScorer()
        component_sentences = scorer.explain_components(scores)
        component_block = " ".join(component_sentences)

        shap_block = ""
        if xgb_result and xgb_result.shap_sentence:
            shap_block = xgb_result.shap_sentence

        closing = self._select_closing(scores.wcs_score, xgb_result)

        parts = [opening]
        if component_block:
            parts.append(component_block)
        if shap_block:
            parts.append(shap_block)
        natural_language_summary = " ".join(parts)

        broker_recommendation = closing

        self._assert_no_forbidden_words(natural_language_summary)
        self._assert_no_forbidden_words(broker_recommendation)

        return natural_language_summary, broker_recommendation

    def _select_closing(
        self,
        wcs_score: float,
        xgb_result: XGBResult | None,
    ) -> str:
        at_risk_prob = xgb_result.at_risk_probability if xgb_result else 0.0
        at_risk_flag = xgb_result.at_risk_flag if xgb_result else False

        if wcs_score < 25:
            return _BAND_CLOSING["Critical"]

        if wcs_score < 50 or at_risk_prob > 0.5:
            return "Enhanced due diligence recommended before policy placement."

        if wcs_score < 75 or (0.3 <= at_risk_prob <= 0.5) or at_risk_flag:
            return "Recommend monitoring quarterly IPEC filings for this insurer."

        return "No enhanced due diligence required at this time."

    def _assert_no_forbidden_words(self, text: str) -> None:
        text_lower = text.lower()
        found = [w for w in self._FORBIDDEN if w in text_lower]
        if found:
            raise ValueError(
                f"Generated NLG text contains forbidden words: {found}. "
                f"Review template set."
            )
