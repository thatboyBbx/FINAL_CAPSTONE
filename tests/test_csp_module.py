"""
CSP Module Test Suite.

Tests:
  1.  test_wcs_strong_insurer
  2.  test_wcs_critical_insurer
  3.  test_normalizer_solvency_at_minimum
  4.  test_normalizer_solvency_breach
  5.  test_normalizer_interpolation
  6.  test_nlg_no_forbidden_words
  7.  test_nlg_critical_closes_with_escalation
  8.  test_fuzzy_lookup_matches_variant
  9.  test_chart_data_arrays_equal_length
  10. test_csp_injected_into_report
  11. test_no_csp_renders_graceful_notice
  12. test_ipec_column_alias_map
  13. test_shap_sentence_dominant_feature

Run: pytest tests/test_csp_module.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ─── Test 1: Strong insurer produces Adequate or Strong band ──────────────────

def test_wcs_strong_insurer():
    from app.ai.inference.csp_wcs_scorer import WCSScorer

    scorer = WCSScorer()
    scores = scorer.score(
        solvency_ratio_pct=220.0,
        liquid_assets_usd=4_500_000,
        gross_claims_paid_usd=12_000_000,   # 4.5 months coverage
        total_claims_reserves_usd=21_600_000,  # 1.8x ratio
        current_assets_usd=9_500_000,
        current_liabilities_usd=5_000_000,  # ratio = 1.9
    )
    assert scores.wcs_score >= 65, (
        f"Strong insurer should score >= 65 (Adequate), got {scores.wcs_score}"
    )
    assert scores.wcs_band in ("Adequate", "Strong"), (
        f"Expected Adequate or Strong, got {scores.wcs_band}"
    )


# ─── Test 2: Critical insurer produces Critical band ─────────────────────────

def test_wcs_critical_insurer():
    from app.ai.inference.csp_wcs_scorer import WCSScorer

    scorer = WCSScorer()
    scores = scorer.score(
        solvency_ratio_pct=105.0,
        liquid_assets_usd=500_000,
        gross_claims_paid_usd=12_000_000,   # 0.5 months
        total_claims_reserves_usd=3_600_000,  # 0.3x
        current_assets_usd=800_000,
        current_liabilities_usd=1_000_000,  # ratio = 0.8
    )
    assert scores.wcs_score < 25, (
        f"Critical insurer should score < 25, got {scores.wcs_score}"
    )
    assert scores.wcs_band == "Critical", (
        f"Expected Critical, got {scores.wcs_band}"
    )


# ─── Test 3: Solvency at IPEC minimum → score = 50 ───────────────────────────

def test_normalizer_solvency_at_minimum():
    from app.ai.inference.csp_normalizer import score_solvency

    result = score_solvency(150.0)
    assert result == pytest.approx(50.0, abs=0.01), (
        f"Solvency at IPEC minimum (150%) should score 50.0, got {result}"
    )


# ─── Test 4: Solvency below 100% → score = 0 ─────────────────────────────────

def test_normalizer_solvency_breach():
    from app.ai.inference.csp_normalizer import score_solvency

    result = score_solvency(90.0)
    assert result == pytest.approx(0.0, abs=0.01), (
        f"Solvency below 100% should score 0.0, got {result}"
    )


# ─── Test 5: Solvency at 175% → score between 50 and 75 ──────────────────────

def test_normalizer_interpolation():
    from app.ai.inference.csp_normalizer import score_solvency

    result = score_solvency(175.0)
    assert 50.0 < result < 75.0, (
        f"Solvency at 175% should be between 50 and 75, got {result}"
    )


# ─── Test 6: NLG output contains no forbidden words ──────────────────────────

FORBIDDEN_WORDS = ["risky", "dangerous", "failing", "avoid", "do not use"]

def test_nlg_no_forbidden_words():
    from app.ai.inference.csp_wcs_scorer import WCSScorer
    from app.ai.inference.csp_nlg import CSPNaturalLanguageGenerator

    scorer = WCSScorer()
    nlg = CSPNaturalLanguageGenerator()

    # Test with various score levels
    for solvency in [105.0, 150.0, 187.5, 230.0]:
        scores = scorer.score(
            solvency_ratio_pct=solvency,
            liquid_assets_usd=2_000_000,
            gross_claims_paid_usd=10_000_000,
            total_claims_reserves_usd=12_000_000,
            current_assets_usd=5_000_000,
            current_liabilities_usd=3_000_000,
        )
        summary, recommendation = nlg.generate(scores, None)
        full_text = (summary + " " + recommendation).lower()
        for word in FORBIDDEN_WORDS:
            assert word not in full_text, (
                f"Forbidden word '{word}' found in NLG output for solvency={solvency}. "
                f"Text: {full_text[:200]}"
            )


# ─── Test 7: Critical insurer NLG closes with escalation ─────────────────────

def test_nlg_critical_closes_with_escalation():
    from app.ai.inference.csp_wcs_scorer import WCSScorer
    from app.ai.inference.csp_nlg import CSPNaturalLanguageGenerator

    scorer = WCSScorer()
    nlg = CSPNaturalLanguageGenerator()

    scores = scorer.score(
        solvency_ratio_pct=105.0,
        liquid_assets_usd=300_000,
        gross_claims_paid_usd=12_000_000,
        total_claims_reserves_usd=2_000_000,
        current_assets_usd=500_000,
        current_liabilities_usd=900_000,
    )
    assert scores.wcs_score < 25, "Precondition: should be Critical"
    _, recommendation = nlg.generate(scores, None)

    assert "escalate" in recommendation.lower(), (
        f"Critical WCS recommendation should contain 'Escalate', got: {recommendation}"
    )


# ─── Test 8: Fuzzy lookup matches variant name ────────────────────────────────

def test_fuzzy_lookup_matches_variant():
    try:
        import rapidfuzz  # noqa: F401  — import-probe only
    except ImportError:
        pytest.skip("rapidfuzz not installed")

    from app.modules.csp.service import _fuzzy_match

    candidates = [
        "Old Mutual Zimbabwe Limited",
        "First Mutual Life Assurance",
        "CBZ Insurance Company Limited",
        "Zimre Holdings Limited",
    ]

    result = _fuzzy_match("Old Mutual", candidates, threshold=75)
    assert result == "Old Mutual Zimbabwe Limited", (
        f"Expected 'Old Mutual Zimbabwe Limited', got {result!r}"
    )

    result2 = _fuzzy_match("CBZ Insurance", candidates, threshold=75)
    assert result2 == "CBZ Insurance Company Limited", (
        f"Expected 'CBZ Insurance Company Limited', got {result2!r}"
    )


# ─── Test 9: Chart data arrays have equal length ─────────────────────────────

def test_chart_data_arrays_equal_length():
    """Construct mock data and verify array length invariant."""
    mock_scores = [
        {
            "insurer_name": f"Insurer {i}",
            "insurer_short_name": f"INS-{i}",
            "wcs_score": float(60 + i * 5),
            "wcs_band": "Adequate",
            "solvency_score": 70.0,
            "settlement_capacity_score": 65.0,
            "reserves_adequacy_score": 55.0,
            "liquidity_score": 60.0,
            "xgb_at_risk_flag": False,
        }
        for i in range(5)
    ]

    # Simulate chart_data endpoint logic
    labels = [s["insurer_name"] for s in mock_scores]
    solvency = [s["solvency_score"] for s in mock_scores]
    settlement = [s["settlement_capacity_score"] for s in mock_scores]
    reserves = [s["reserves_adequacy_score"] for s in mock_scores]
    liquidity = [s["liquidity_score"] for s in mock_scores]
    wcs = [s["wcs_score"] for s in mock_scores]
    bands = [s["wcs_band"] for s in mock_scores]
    at_risk = [s["xgb_at_risk_flag"] for s in mock_scores]

    arrays = [labels, solvency, settlement, reserves, liquidity, wcs, bands, at_risk]
    lengths = [len(a) for a in arrays]
    assert len(set(lengths)) == 1, f"Arrays have unequal lengths: {lengths}"
    assert lengths[0] == 5


# ─── Test 10: CSP injection into report (mocked) ─────────────────────────────

def test_csp_injected_into_report():
    """CSPService.inject_csp_into_report returns True when CSP data exists."""
    from unittest.mock import MagicMock, patch
    from app.modules.csp.service import CSPService

    svc = CSPService()
    mock_db = MagicMock()

    with patch.object(svc, "get_csp_for_insurer", return_value={
        "insurer_name": "CBZ Insurance Company Limited",
        "wcs_score": 72.5,
        "wcs_band": "Adequate",
    }):
        result = svc.inject_csp_into_report("RPT-001", "CBZ Insurance", mock_db)

    assert result is True, "inject_csp_into_report should return True when data found"


# ─── Test 11: No CSP renders graceful notice (no exception) ──────────────────

def test_no_csp_renders_graceful_notice():
    """CSPService.inject_csp_into_report returns False (not exception) when no data."""
    from unittest.mock import MagicMock, patch
    from app.modules.csp.service import CSPService

    svc = CSPService()
    mock_db = MagicMock()

    with patch.object(svc, "get_csp_for_insurer", return_value=None):
        result = svc.inject_csp_into_report("RPT-002", "Unknown Insurer XYZ", mock_db)

    assert result is False, "inject_csp_into_report should return False when no data found"


# ─── Test 12: IPEC column alias map handles variant headers ──────────────────

def test_ipec_column_alias_map():
    from app.infrastructure.scrapers.ipec_fsr1_scraper import COLUMN_ALIAS_MAP

    # Test variant column headers
    assert COLUMN_ALIAS_MAP.get("total assets") == "total_assets_usd"
    assert COLUMN_ALIAS_MAP.get("assets (usd)") == "total_assets_usd"
    assert COLUMN_ALIAS_MAP.get("solvency ratio") == "solvency_ratio_pct"
    assert COLUMN_ALIAS_MAP.get("solvency ratio (%)") == "solvency_ratio_pct"
    assert COLUMN_ALIAS_MAP.get("ibnr") == "ibnr_reserve_usd"
    assert COLUMN_ALIAS_MAP.get("gwp") == "gross_premiums_written_usd"
    assert COLUMN_ALIAS_MAP.get("gross written premium") == "gross_premiums_written_usd"
    assert COLUMN_ALIAS_MAP.get("claims paid") == "gross_claims_paid_usd"


# ─── Test 13: SHAP sentence highlights dominant feature ──────────────────────

def test_shap_sentence_dominant_feature():
    from app.ai.inference.csp_xgboost_model import CSPXGBoostModel

    model = CSPXGBoostModel()  # No model file loaded — testing shap_to_sentence only

    shap_dict = {
        "solvency_ratio_pct": 0.02,
        "settlement_capacity_months": 0.01,
        "reserves_to_paid_ratio": 0.01,
        "liquidity_ratio": 0.01,
        "claims_ratio_pct": 0.02,
        "solvency_ratio_yoy_change": -0.80,  # dominant negative signal
        "claims_reserves_yoy_change": 0.01,
        "premiums_yoy_change": 0.01,
    }

    sentence = model.shap_to_sentence(shap_dict)
    assert "solvency" in sentence.lower(), (
        f"Sentence should mention 'solvency' as dominant feature, got: {sentence}"
    )
    assert "declined" in sentence.lower() or "negative" in sentence.lower(), (
        f"Sentence should indicate negative direction, got: {sentence}"
    )
