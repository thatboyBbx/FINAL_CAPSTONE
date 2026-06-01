"""
build_training_datasets.py
==========================

InsureIntel Zimbabwe — Training Data Builder
============================================

This script produces ALL datasets required by the system's ML models and RAG
pipeline. Run it once from the project root with:

    python build_training_datasets.py

Outputs (all saved under storage/datasets/app/):
  1. ml_training_dataset.csv         — 10-feature labelled set for the settlement-risk GBDT
  2. insurer_financials_full.csv     — Monthly snapshots for all 73 IPEC-regulated entities
  3. news_articles_corpus.json       — Synthetic news articles for news-feature engineering
  4. rag_document_manifest.json      — Catalogue of all regulatory PDFs for RAG ingestion
  5. rag_qa_eval_pairs.json          — Q&A pairs for RAG pipeline evaluation
  6. claims_training_dataset.csv     — Claim-level dataset aligned to real insurer names

Design decisions:
  - All synthesis uses seeded randomness (SEED = 42) for reproducibility.
  - Proxy labels follow the exact same rules as ProxyLabelProvider in labels.py,
    so the training set is consistent with live prediction.
  - Financial figures are calibrated to Zimbabwe USD market scale (ZWL/USD post-2019).
  - 73 real IPEC-regulated entities from insurers.csv are used as the insurer universe.
"""

from __future__ import annotations

import csv
import json
import math
import random
import os
from datetime import date, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SEED: int = 42
random.seed(SEED)

BASE_DIR = Path(__file__).resolve().parent
DATASETS_DIR = BASE_DIR / "storage" / "datasets" / "app"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

SOURCES_DIR = BASE_DIR / "sources" / "downloads"
INSURERS_CSV = BASE_DIR / "insurers.csv"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rand(lo: float, hi: float) -> float:
    """Uniform float in [lo, hi]."""
    return random.uniform(lo, hi)


def _gauss(mu: float, sigma: float, lo: float = 0.0, hi: float = float("inf")) -> float:
    """Gaussian sample clamped to [lo, hi]."""
    return max(lo, min(hi, random.gauss(mu, sigma)))


def _monthly_dates(year: int, months: int = 12) -> list[date]:
    """Return month-end dates for `months` months starting from Jan of `year`."""
    dates: list[date] = []
    for m in range(1, months + 1):
        # last day of month
        if m == 12:
            d = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            d = date(year, m + 1, 1) - timedelta(days=1)
        dates.append(d)
    return dates


# ---------------------------------------------------------------------------
# Step 1: Load real insurer universe
# ---------------------------------------------------------------------------

def load_insurers(path: Path) -> list[dict[str, str]]:
    """Load all 73 IPEC-regulated entities from insurers.csv."""
    entities: list[dict[str, str]] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entities.append({
                "name": row["Entity Name"].strip(),
                "category": row["Insurance Category"].strip(),
                "type": row["Insurance Type"].strip(),
            })
    return entities


# ---------------------------------------------------------------------------
# Step 2: Simulate monthly financial snapshots per insurer
# ---------------------------------------------------------------------------
# Scale ranges (Zimbabwe USD market, post-dollarisation 2019+)
# Short-term / life insurers: larger premium base
# Micro-insurers / funeral assurers: smaller premium base

CATEGORY_SCALES: dict[str, dict[str, tuple[float, float]]] = {
    "Life Assurer": {
        "premium_mu": 4_500_000, "premium_sigma": 1_200_000,
        "claims_reserve_mu": 18_000_000, "claims_reserve_sigma": 4_000_000,
        "liquidity_lo": 1.05, "liquidity_hi": 2.20,
    },
    "Short-Term Insurer": {
        "premium_mu": 3_200_000, "premium_sigma": 900_000,
        "claims_reserve_mu": 12_000_000, "claims_reserve_sigma": 3_000_000,
        "liquidity_lo": 1.0, "liquidity_hi": 2.0,
    },
    "Life Reassurer": {
        "premium_mu": 6_000_000, "premium_sigma": 1_500_000,
        "claims_reserve_mu": 22_000_000, "claims_reserve_sigma": 5_000_000,
        "liquidity_lo": 1.1, "liquidity_hi": 2.5,
    },
    "Short-Term Reinsurer": {
        "premium_mu": 5_500_000, "premium_sigma": 1_400_000,
        "claims_reserve_mu": 20_000_000, "claims_reserve_sigma": 4_500_000,
        "liquidity_lo": 1.05, "liquidity_hi": 2.3,
    },
    "Micro-Insurer": {
        "premium_mu": 280_000, "premium_sigma": 80_000,
        "claims_reserve_mu": 1_200_000, "claims_reserve_sigma": 350_000,
        "liquidity_lo": 0.9, "liquidity_hi": 1.6,
    },
    "Funeral Assurer": {
        "premium_mu": 420_000, "premium_sigma": 110_000,
        "claims_reserve_mu": 1_800_000, "claims_reserve_sigma": 500_000,
        "liquidity_lo": 0.85, "liquidity_hi": 1.7,
    },
}

DEFAULT_SCALE = CATEGORY_SCALES["Short-Term Insurer"]


def _get_scale(category: str) -> dict[str, Any]:
    """Retrieve scale parameters for an insurer category."""
    return CATEGORY_SCALES.get(category, DEFAULT_SCALE)


def _risk_profile_for(insurer_name: str) -> str:
    """
    Deterministically assign a risk profile to each insurer so the dataset
    has realistic label distribution across the 73 entities.

    Roughly 60% low-risk, 25% moderate, 15% high — matching regional norms.
    """
    h = hash(insurer_name) % 100
    if h < 60:
        return "low"
    elif h < 85:
        return "moderate"
    else:
        return "high"


def simulate_snapshots(
    insurer: dict[str, str],
    year: int = 2024,
) -> list[dict[str, Any]]:
    """
    Generate 12 monthly financial snapshots for one insurer.
    The risk profile biases reserve depletion velocity and claims pressure
    so that proxy labels align with the assigned risk tier.
    """
    scale = _get_scale(insurer["category"])
    profile = _risk_profile_for(insurer["name"])

    # Starting reserve — drawn from a Gaussian, adjusted by risk profile
    reserve_start = _gauss(
        scale["claims_reserve_mu"],
        scale["claims_reserve_sigma"],
        lo=scale["claims_reserve_mu"] * 0.3,
    )
    if profile == "high":
        reserve_start *= _rand(0.4, 0.7)   # already depleted
    elif profile == "moderate":
        reserve_start *= _rand(0.7, 0.9)

    # Monthly claims draw rate — higher for high-risk
    claims_draw_factor = {
        "low": _rand(0.05, 0.12),
        "moderate": _rand(0.13, 0.22),
        "high": _rand(0.23, 0.42),
    }[profile]

    # Liquidity ratio — stable but slightly worse for stressed insurers
    if profile == "high":
        liquidity = round(_rand(scale["liquidity_lo"] * 0.7, scale["liquidity_lo"] * 0.95), 4)
    elif profile == "moderate":
        liquidity = round(_rand(scale["liquidity_lo"], scale["liquidity_lo"] * 1.1), 4)
    else:
        liquidity = round(_rand(scale["liquidity_lo"] * 1.05, scale["liquidity_hi"]), 4)

    dates = _monthly_dates(year, months=12)
    snapshots: list[dict[str, Any]] = []
    reserve = reserve_start

    for d in dates:
        premium = _gauss(scale["premium_mu"], scale["premium_sigma"], lo=10_000)
        claims_paid = max(1_000.0, reserve * claims_draw_factor * _rand(0.7, 1.3))
        reserve = max(50_000.0, reserve - claims_paid * _rand(0.3, 0.8))

        snapshots.append({
            "insurer_name": insurer["name"],
            "insurer_category": insurer["category"],
            "insurer_type": insurer["type"],
            "reporting_date": d.isoformat(),
            "claims_reserves": round(reserve, 2),
            "claims_paid": round(claims_paid, 2),
            "premiums_written": round(premium, 2),
            "liquidity_ratio": liquidity,
            # Store the ground-truth profile for reference (NOT a feature)
            "_risk_profile": profile,
        })

    return snapshots


# ---------------------------------------------------------------------------
# Step 3: Feature engineering (mirrors FinancialFeatureEngineer + NewsFeatureEngineer)
# ---------------------------------------------------------------------------

def compute_financial_features(snapshots: list[dict[str, Any]]) -> dict[str, float]:
    """Replicate FinancialFeatureEngineer.compute_feature_vector() over snapshot dicts."""
    reserves = [s["claims_reserves"] for s in snapshots]
    claims = [s["claims_paid"] for s in snapshots if s["claims_paid"] > 0]
    premiums = [s["premiums_written"] for s in snapshots]
    liquidity = [s["liquidity_ratio"] for s in snapshots if s["liquidity_ratio"] > 0]

    reserve_adequacy_index = round(mean(reserves) / mean(claims), 4) if claims else 0.0
    claims_pressure_indicator = round(sum(claims) / sum(premiums), 4) if sum(premiums) > 0 else 0.0
    liquidity_stress_score = round(1.0 / mean(liquidity), 4) if liquidity else 0.0

    first = snapshots[0]
    last = snapshots[-1]
    days = (date.fromisoformat(last["reporting_date"]) - date.fromisoformat(first["reporting_date"])).days
    reserve_depletion_velocity = round(
        (last["claims_reserves"] - first["claims_reserves"]) / days, 4
    ) if days > 0 else 0.0

    return {
        "reserve_adequacy_index": reserve_adequacy_index,
        "claims_pressure_indicator": claims_pressure_indicator,
        "liquidity_stress_score": liquidity_stress_score,
        "reserve_depletion_velocity": reserve_depletion_velocity,
    }


def synthetic_news_features(profile: str) -> dict[str, Any]:
    """
    Synthesise news-derived features that are consistent with the risk profile.
    Mirrors the output of NewsFeatureEngineer.compute().
    """
    if profile == "high":
        settlement = random.randint(1, 4)
        regulatory = random.randint(1, 3)
        lawsuit = random.randint(0, 2)
        catastrophe = random.randint(0, 1)
    elif profile == "moderate":
        settlement = random.randint(0, 2)
        regulatory = random.randint(0, 1)
        lawsuit = random.randint(0, 1)
        catastrophe = random.randint(0, 1)
    else:
        settlement = random.randint(0, 1)
        regulatory = 0
        lawsuit = 0
        catastrophe = random.randint(0, 1)

    adverse = settlement + regulatory + lawsuit + catastrophe
    news_risk_score = round(
        2.0 * settlement + 3.0 * regulatory + 2.5 * lawsuit + 2.0 * catastrophe, 4
    )
    return {
        "adverse_event_count": adverse,
        "settlement_event_count": settlement,
        "regulatory_event_count": regulatory,
        "lawsuit_event_count": lawsuit,
        "catastrophe_event_count": catastrophe,
        "news_risk_score": news_risk_score,
    }


# ---------------------------------------------------------------------------
# Step 4: Proxy label (mirrors ProxyLabelProvider.label())
# ---------------------------------------------------------------------------

def proxy_label(fin: dict[str, float], news: dict[str, Any]) -> int:
    """
    Exact replication of ProxyLabelProvider.label() from labels.py.
    0 = low, 1 = moderate, 2 = high settlement-risk.
    """
    rai = fin["reserve_adequacy_index"]
    cpi = fin["claims_pressure_indicator"]
    lss = fin["liquidity_stress_score"]
    rdv = fin["reserve_depletion_velocity"]
    news_score = news["news_risk_score"]
    reg_events = news["regulatory_event_count"]

    high = 0
    moderate = 0

    if cpi >= 1.0:           high += 1
    if 0 < rai < 2.0:        high += 1
    if lss >= 1.1:           high += 1
    if rdv < -5000:          high += 1
    if news_score >= 5.0 or reg_events >= 1:  high += 1

    if 0.85 <= cpi < 1.0:   moderate += 1
    if 2.0 <= rai < 3.0:    moderate += 1
    if 0.95 <= lss < 1.1:   moderate += 1
    if -5000 <= rdv < 0:    moderate += 1
    if 2.0 <= news_score < 5.0:  moderate += 1

    if high >= 2:
        return 2
    if high == 1 or moderate >= 2:
        return 1
    return 0


# ---------------------------------------------------------------------------
# Step 5: Generate synthetic news articles corpus
# ---------------------------------------------------------------------------

ARTICLE_TEMPLATES: list[dict[str, Any]] = [
    # Settlement events
    {
        "category": "settlement",
        "titles": [
            "{insurer} settles major flood claim payout of USD {amount:,}",
            "Policyholders receive compensation from {insurer} after long dispute",
            "{insurer} claims paid out to cyclone victims in Manicaland",
            "Settlement reached: {insurer} to pay USD {amount:,} to business clients",
        ],
        "body_tmpl": (
            "{insurer} has confirmed a settlement of USD {amount:,} to policyholders "
            "following an extended claims review process. The payout covers {policy_type} "
            "policies impacted by adverse weather events in {province}. "
            "The insurer stated that claims processing was completed within the statutory period."
        ),
    },
    # Regulatory events
    {
        "category": "regulatory",
        "titles": [
            "IPEC issues fine to {insurer} for late return submission",
            "{insurer} receives sanction notice from insurance regulator",
            "Regulator IPEC penalises {insurer} over license compliance breach",
            "{insurer} placed under enhanced supervisory oversight",
        ],
        "body_tmpl": (
            "The Insurance and Pensions Commission (IPEC) has issued a regulatory "
            "penalty to {insurer} following a compliance review. The sanction relates "
            "to delayed submission of quarterly statutory returns. IPEC invoked the "
            "Ladder of Supervisory Intervention under GRS 11. {insurer} has 30 days "
            "to remedy the breach or face licence suspension."
        ),
    },
    # Lawsuit events
    {
        "category": "lawsuit",
        "titles": [
            "{insurer} sued by policyholder over rejected {policy_type} claim",
            "Court case filed against {insurer} for alleged claim bad faith",
            "{insurer} faces litigation from commercial clients",
            "Lawsuit against {insurer} heads to High Court",
        ],
        "body_tmpl": (
            "A class action lawsuit has been filed against {insurer} in the High Court "
            "of Zimbabwe by a group of {policy_type} policyholders alleging wrongful "
            "claim rejection. Plaintiffs seek USD {amount:,} in damages. "
            "Legal proceedings are expected to conclude within {months} months. "
            "{insurer} denies liability and says it will vigorously defend the case."
        ),
    },
    # Catastrophe events
    {
        "category": "catastrophe",
        "titles": [
            "Cyclone damages trigger surge in claims at {insurer}",
            "{insurer} activates catastrophe protocol after Harare floods",
            "Earthquake tremors in Mutare prompt property claims spike at {insurer}",
            "{insurer} responds to storm damage claims across Matabeleland",
        ],
        "body_tmpl": (
            "{insurer} reported a significant spike in property and motor claims "
            "following {event} that struck {province}. The insurer estimates total "
            "insured losses of USD {amount:,}. Catastrophe response teams have been "
            "deployed and claims are being fast-tracked. IPEC has been notified as "
            "per Circular requirements for mass-casualty events."
        ),
    },
    # Neutral / positive
    {
        "category": "neutral",
        "titles": [
            "{insurer} posts strong Q{q} results with improved solvency ratio",
            "{insurer} expands coverage to rural Zimbabwe with new micro-products",
            "{insurer} achieves ZICARP compliance ahead of deadline",
            "{insurer} wins customer service award at Zimbabwe Insurance Awards",
        ],
        "body_tmpl": (
            "{insurer} has announced positive financial results for Q{q} {year}, "
            "with a solvency ratio of {solvency:.2f}, well above the ZICARP minimum "
            "capital requirement. Premium income grew by {growth:.1f}% year-on-year. "
            "Management attributed the performance to disciplined underwriting and "
            "improved claims management processes."
        ),
    },
]

PROVINCES = ["Harare", "Bulawayo", "Manicaland", "Midlands", "Masvingo", "Matabeleland South"]
POLICY_TYPES = ["motor", "property", "health", "business", "life", "funeral"]
EVENTS = ["Cyclone Freddy", "flash floods", "severe storms", "earthquake tremors"]


def _article_id(i: int) -> str:
    return f"ART-{i:04d}"


def generate_news_corpus(insurers: list[dict[str, str]], n_articles: int = 800) -> list[dict[str, Any]]:
    """
    Produce a synthetic news corpus of n_articles articles.
    Each article is associated with a real IPEC-regulated insurer and
    tagged with its event category — ready for NewsFeatureEngineer to consume.
    """
    articles: list[dict[str, Any]] = []
    insurer_names = [i["name"] for i in insurers]

    for idx in range(n_articles):
        template = random.choice(ARTICLE_TEMPLATES)
        insurer_name = random.choice(insurer_names)
        amount = random.randint(50_000, 2_500_000)
        province = random.choice(PROVINCES)
        policy_type = random.choice(POLICY_TYPES)
        event = random.choice(EVENTS)
        q = random.randint(1, 4)
        year = random.randint(2020, 2025)
        months = random.randint(3, 18)
        solvency = _rand(1.05, 2.8)
        growth = _rand(-15.0, 35.0)

        title_tmpl = random.choice(template["titles"])
        title = title_tmpl.format(
            insurer=insurer_name, amount=amount, province=province,
            policy_type=policy_type, q=q, year=year, event=event,
        )
        body = template["body_tmpl"].format(
            insurer=insurer_name, amount=amount, province=province,
            policy_type=policy_type, q=q, year=year, event=event,
            months=months, solvency=solvency, growth=growth,
        )

        pub_date = date(year, random.randint(1, 12), random.randint(1, 28))

        articles.append({
            "article_id": _article_id(idx + 1),
            "insurer_name": insurer_name,
            "title": title,
            "content": body,
            "category": template["category"],
            "published_date": pub_date.isoformat(),
            "source": random.choice(["The Herald", "NewsDay", "Zimbabwe Independent", "IPEC Bulletin"]),
        })

    return articles


# ---------------------------------------------------------------------------
# Step 6: RAG document manifest
# ---------------------------------------------------------------------------

def build_rag_manifest(sources_dir: Path) -> list[dict[str, Any]]:
    """
    Walk the sources directory and catalogue every regulatory PDF.
    Returns a list of document metadata records for RAG ingestion.
    """
    manifest: list[dict[str, Any]] = []
    doc_id = 1

    # Classify by directory
    for pdf_path in sorted(sources_dir.rglob("*.pdf")) + sorted(sources_dir.rglob("*.PDF")):
        rel = pdf_path.relative_to(sources_dir)
        parts = rel.parts

        # Determine category from folder structure
        if "SOURCES" in parts:
            name = pdf_path.stem
            # Sub-classify by filename
            if name.startswith("TS"):
                category = "ZICARP_Technical_Standard"
            elif name.startswith("GRS"):
                category = "ZICARP_Governance_Standard"
            elif name.startswith("DS"):
                category = "ZICARP_Disclosure_Standard"
            elif "Circular 32" in name:
                category = "ZICARP_Framework_Circular"
            elif "Regulatory Sandbox" in name or "REGULATORY-SANDBOX" in name:
                category = "Regulatory_Guideline"
            elif "Insurance Act" in name:
                category = "Primary_Legislation"
            elif "Pensions Commission" in name or "S.I." in name:
                category = "Subsidiary_Legislation"
            elif "BOARD CHARTER" in name:
                category = "Governance_Document"
            else:
                category = "Regulatory_Document"
            year_hint = 2023
        elif "insurance_circulars" in parts:
            # Extract year from folder name
            try:
                year_hint = int([p for p in parts if p.isdigit()][0])
            except (IndexError, ValueError):
                year_hint = 0
            category = f"IPEC_Circular_{year_hint}" if year_hint else "IPEC_Circular"
        else:
            category = "Other"
            year_hint = 0

        manifest.append({
            "doc_id": f"DOC-{doc_id:04d}",
            "title": pdf_path.stem,
            "category": category,
            "year": year_hint,
            "filename": pdf_path.name,
            "relative_path": str(rel).replace("\\", "/"),
            "absolute_path": str(pdf_path),
            "ingestion_status": "pending",
            "chunk_strategy": "page",        # RAG pipeline hint: chunk by page
            "embedding_model": "text-embedding-3-small",  # target model hint
            "tags": _derive_tags(pdf_path.stem, category),
        })
        doc_id += 1

    return manifest


def _derive_tags(stem: str, category: str) -> list[str]:
    """Derive semantic tags from filename for RAG filtering."""
    tags: list[str] = [category.lower().replace("_", "-")]
    stem_lower = stem.lower()
    keyword_map = {
        "solvency": "solvency",
        "capital": "capital-requirement",
        "technical": "technical-standard",
        "valuation": "valuation",
        "liability": "liability",
        "asset": "assets",
        "market risk": "market-risk",
        "life": "life-insurance",
        "non-life": "non-life-insurance",
        "operational": "operational-risk",
        "governance": "governance",
        "orsa": "orsa",
        "disclosure": "disclosure",
        "ladder": "supervisory-intervention",
        "reinsurer": "reinsurance",
        "funeral": "funeral-assurance",
        "regulatory sandbox": "sandbox",
        "pensions": "pensions",
        "board": "board-governance",
        "circular": "circular",
    }
    for kw, tag in keyword_map.items():
        if kw in stem_lower:
            tags.append(tag)
    return list(set(tags))


# ---------------------------------------------------------------------------
# Step 7: RAG Q&A evaluation pairs
# ---------------------------------------------------------------------------

RAG_QA_PAIRS: list[dict[str, str]] = [
    {
        "question": "What is the Minimum Capital Requirement (MCR) for a short-term insurer under ZICARP?",
        "expected_answer": "Under ZICARP Technical Standard 5, the MCR is determined as the higher of the absolute floor (USD 750,000 for short-term insurers) or the formula-based minimum derived from the Solvency Capital Requirement (SCR) using a 25% floor ratio.",
        "source_doc": "TS 5 - Determination of Minimum Capital Requirement",
        "category": "solvency",
        "difficulty": "medium",
    },
    {
        "question": "What triggers a Level 3 supervisory intervention under GRS 11?",
        "expected_answer": "Level 3 intervention is triggered when an insurer's solvency ratio falls between 75% and 100% of the SCR, or when significant governance failures are identified. IPEC may impose enhanced reporting requirements, restrict new business, or require a remediation plan.",
        "source_doc": "GRS 11 Ladder of Supervisory Intervention",
        "category": "supervision",
        "difficulty": "hard",
    },
    {
        "question": "How are technical liabilities valued under ZICARP TS 3?",
        "expected_answer": "Technical liabilities under TS 3 are valued on a market-consistent basis using best estimate assumptions plus a risk margin. The best estimate is the probability-weighted average of future cash flows discounted at the risk-free rate curve published by IPEC.",
        "source_doc": "TS 3 - Valuation of Technical Liabilities",
        "category": "valuation",
        "difficulty": "hard",
    },
    {
        "question": "What is an ORSA and which insurers must conduct it?",
        "expected_answer": "The Own Risk and Solvency Assessment (ORSA) is a self-assessment by an insurer of the adequacy of its risk management and current and prospective solvency positions. Under GRS 5, all licensed insurers and reinsurers with annual gross written premium exceeding the IPEC threshold must conduct and submit an ORSA annually.",
        "source_doc": "GRS 5 ORSA",
        "category": "risk-management",
        "difficulty": "medium",
    },
    {
        "question": "What market risks are captured in the ZICARP market risk capital requirement?",
        "expected_answer": "TS 6.1 covers interest rate risk, equity risk, property risk, currency risk, spread risk, and concentration risk. Each sub-module uses a prescribed stress scenario or factor-based approach to derive a capital charge, and they are aggregated using a correlation matrix.",
        "source_doc": "TS 6.1 -Determination of Market Risk Capital Requirement",
        "category": "market-risk",
        "difficulty": "hard",
    },
    {
        "question": "How is the operational risk capital requirement determined under ZICARP?",
        "expected_answer": "Under TS 6.4, the operational risk capital charge is the higher of 3% of annual gross written premium or 0.3% of technical provisions, subject to a minimum floor. It is applied as a flat add-on to the base SCR modules.",
        "source_doc": "TS 6.4 -Determination of Operational Risk Capital Requirement",
        "category": "operational-risk",
        "difficulty": "medium",
    },
    {
        "question": "What non-life underwriting risk sub-modules are included in ZICARP?",
        "expected_answer": "TS 6.3 includes premium risk (unexpected losses in future premium income), reserve risk (unexpected development in existing claims reserves), and catastrophe risk. Each is computed separately and combined using the IPEC-prescribed correlation matrix.",
        "source_doc": "TS 6.3 -Determination of Non-Life Underwriting Risk Capital Requirement",
        "category": "underwriting-risk",
        "difficulty": "hard",
    },
    {
        "question": "What are Eligible Own Funds and how are they tiered under TS 4?",
        "expected_answer": "Eligible Own Funds represent the financial resources that can absorb losses. TS 4 classifies them into Tier 1 (highest quality — paid-up share capital, retained earnings), Tier 2 (subordinated liabilities, hybrid instruments), and Tier 3 (lower quality). Only Tier 1 can cover the MCR in full; SCR coverage is limited by tier caps.",
        "source_doc": "TS 4 - Determination of Eligible Own Funds",
        "category": "own-funds",
        "difficulty": "hard",
    },
    {
        "question": "What does the Market Disclosure Framework require insurers to publish?",
        "expected_answer": "DS 1 requires licensed insurers to publicly disclose their solvency and financial condition report (SFCR) annually, covering: business and performance summary, governance and risk management framework, risk profile, solvency valuation methods, and capital management. The report must be published on the insurer's website within 4 months of year-end.",
        "source_doc": "DS 1 Market Disclosure Framework",
        "category": "disclosure",
        "difficulty": "medium",
    },
    {
        "question": "Under the Insurance Act, what are the licensing requirements for an insurer in Zimbabwe?",
        "expected_answer": "The Insurance Act requires that every insurer operating in Zimbabwe holds a valid licence issued by IPEC. Applicants must demonstrate paid-up capital meeting the prescribed minimum, fit-and-proper directors, an approved risk management framework, and reinsurance arrangements. Licences are class-specific (life, short-term, reinsurance, microinsurance, funeral).",
        "source_doc": "Insurance Act",
        "category": "legislation",
        "difficulty": "easy",
    },
    {
        "question": "How does ZICARP treat life underwriting risk?",
        "expected_answer": "TS 6.2 addresses life underwriting risk through sub-modules covering mortality risk, longevity risk, disability/morbidity risk, lapse risk, expense risk, revision risk, and catastrophe risk. Each is computed using prescribed stress factors applied to the best-estimate technical provisions, then aggregated with a correlation matrix.",
        "source_doc": "TS 6.2 -Determination of Life Underwriting Risk Capital Requirement",
        "category": "life-underwriting",
        "difficulty": "hard",
    },
    {
        "question": "What is the claims pressure indicator and why does it matter for risk scoring?",
        "expected_answer": "The claims pressure indicator (CPI) is the ratio of total claims paid to total premiums written over a rolling period. A CPI >= 1.0 means the insurer is paying out more in claims than it earns in premiums — a strong indicator of high settlement risk. In the InsureIntel model, CPI >= 1.0 triggers a high-risk flag.",
        "source_doc": "internal_model_docs",
        "category": "ml-model",
        "difficulty": "easy",
    },
    {
        "question": "What is the reserve adequacy index and how is it interpreted?",
        "expected_answer": "The reserve adequacy index (RAI) is the ratio of mean claims reserves to mean claims paid. An RAI < 2.0 suggests reserves may be insufficient relative to claims outflows, flagging potential reserve depletion risk. Values between 2.0 and 3.0 indicate moderate adequacy. Above 3.0 signals comfortable reserve cover.",
        "source_doc": "internal_model_docs",
        "category": "ml-model",
        "difficulty": "easy",
    },
    {
        "question": "What is the reserve depletion velocity and what does a negative value mean?",
        "expected_answer": "The reserve depletion velocity (RDV) measures the change in claims reserves over the observation period divided by the number of days. A negative RDV means reserves are shrinking — the insurer is paying out claims faster than it is rebuilding reserves. A value below -5,000 per day is a high-risk trigger in the InsureIntel model.",
        "source_doc": "internal_model_docs",
        "category": "ml-model",
        "difficulty": "medium",
    },
    {
        "question": "What is the regulatory sandbox for the insurance and pensions industry?",
        "expected_answer": "IPEC's Regulatory Sandbox provides a controlled environment where innovative insurance and pension products or business models can be tested with real customers under relaxed regulatory constraints, subject to safeguards. Participants apply to IPEC and are granted sandbox licences for a limited period (typically 12–24 months) to validate their model before full licensing.",
        "source_doc": "REGULATORY-SANDBOX-GUIDELINES-FOR-THE-INSURANCE-AND-PENSIONS-INDUSTRY-",
        "category": "regulation",
        "difficulty": "easy",
    },
    {
        "question": "How is the Solvency Capital Requirement (SCR) structured under ZICARP TS 6?",
        "expected_answer": "The SCR under TS 6 is a risk-based capital measure derived by combining sub-module capital requirements: market risk (TS 6.1), life underwriting risk (TS 6.2), non-life underwriting risk (TS 6.3), and operational risk (TS 6.4). Sub-modules are aggregated using diversification matrices. The SCR equals the 99.5% Value-at-Risk over a 1-year horizon.",
        "source_doc": "TS 6 -Determination of the Solvency Capital Requirement",
        "category": "solvency",
        "difficulty": "hard",
    },
]


# ---------------------------------------------------------------------------
# Step 8: Claims-level dataset aligned to real insurers
# ---------------------------------------------------------------------------

CLAIM_STATUSES = ["paid", "pending", "rejected"]
CLAIM_TYPES = ["motor", "property", "health", "business", "life", "travel", "funeral"]


def generate_claims_dataset(
    insurers: list[dict[str, str]], n_claims: int = 1000
) -> list[dict[str, Any]]:
    """
    Produce a claims-level dataset aligned to real IPEC-regulated insurer names.
    Each row is one claim with features for a claims-triage or settlement-time model.
    """
    rows: list[dict[str, Any]] = []

    for i in range(n_claims):
        insurer = random.choice(insurers)
        profile = _risk_profile_for(insurer["name"])

        claim_type = random.choice(CLAIM_TYPES)
        premium = round(_rand(100, 3000), 2)
        risk_score = round(_rand(0.1, 0.99), 3)
        claim_amount = round(_rand(500, 40_000), 2)

        # High-risk insurers have more rejections and longer settlement
        if profile == "high":
            status_weights = [0.45, 0.35, 0.20]   # paid, pending, rejected
            settlement_days = random.randint(15, 90)
        elif profile == "moderate":
            status_weights = [0.60, 0.25, 0.15]
            settlement_days = random.randint(7, 60)
        else:
            status_weights = [0.75, 0.15, 0.10]
            settlement_days = random.randint(3, 30)

        status = random.choices(CLAIM_STATUSES, weights=status_weights, k=1)[0]
        vehicle_value = round(_rand(5_000, 60_000), 0) if claim_type == "motor" else 0.0

        rows.append({
            "claim_id": f"CLM-{i + 1:05d}",
            "insurer_name": insurer["name"],
            "insurer_category": insurer["category"],
            "policy_type": claim_type,
            "claim_amount": claim_amount,
            "premium": premium,
            "risk_score": risk_score,
            "claim_status": status,
            "settlement_days": settlement_days,
            "vehicle_value": vehicle_value,
            "_risk_profile": profile,  # reference column, exclude from features
        })

    return rows


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 65)
    print("InsureIntel Zimbabwe — Training Data Builder")
    print("=" * 65)

    # --- Load real insurer universe ---
    print(f"\n[1/6] Loading insurers from {INSURERS_CSV.name}...")
    insurers = load_insurers(INSURERS_CSV)
    print(f"      Loaded {len(insurers)} IPEC-regulated entities.")

    # --- Build financial snapshots for all insurers ---
    print("\n[2/6] Generating financial snapshots (12 months × 73 insurers)...")
    all_snapshots: list[dict[str, Any]] = []
    for insurer in insurers:
        snaps = simulate_snapshots(insurer, year=2024)
        all_snapshots.extend(snaps)

    financials_path = DATASETS_DIR / "insurer_financials_full.csv"
    fieldnames = [
        "insurer_name", "insurer_category", "insurer_type",
        "reporting_date", "claims_reserves", "claims_paid",
        "premiums_written", "liquidity_ratio", "_risk_profile",
    ]
    with open(financials_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_snapshots)
    print(f"      Saved {len(all_snapshots)} rows → {financials_path.name}")

    # --- Build ML training dataset ---
    print("\n[3/6] Engineering features and computing proxy labels...")
    ml_rows: list[dict[str, Any]] = []
    label_counts = {0: 0, 1: 0, 2: 0}

    for insurer in insurers:
        # Group snapshots for this insurer
        snaps = [s for s in all_snapshots if s["insurer_name"] == insurer["name"]]
        profile = snaps[0]["_risk_profile"]

        fin_features = compute_financial_features(snaps)
        news_features = synthetic_news_features(profile)
        label = proxy_label(fin_features, news_features)
        label_counts[label] += 1

        row: dict[str, Any] = {
            "insurer_name": insurer["name"],
            "insurer_category": insurer["category"],
            **fin_features,
            **news_features,
            "settlement_risk_label": label,
        }
        ml_rows.append(row)

    # Also fold in the existing insurance_synthetic.csv rows for volume
    synthetic_csv = BASE_DIR / "app" / "infrastructure" / "storage" / "training_data" / "insurance_synthetic.csv"
    if synthetic_csv.exists():
        with open(synthetic_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Map synthetic columns to our feature schema where possible
                try:
                    # Approximate mapping from synthetic dataset columns
                    approx_rai = float(row.get("reserve_adequacy", 1.0)) * 3.0
                    approx_cpi = float(row.get("claims_ratio", 0.5))
                    approx_lss = 1.0 / max(float(row.get("liquidity_ratio", 1.0)), 0.01)
                    approx_rdv = _rand(-8000, 2000)  # not available, synthesise

                    news_profile = "high" if row.get("risk_label") == "critical" else (
                        "moderate" if row.get("risk_label") in ("watch", "adequate") else "low"
                    )
                    news_f = synthetic_news_features(news_profile)
                    fin_f = {
                        "reserve_adequacy_index": round(approx_rai, 4),
                        "claims_pressure_indicator": round(approx_cpi, 4),
                        "liquidity_stress_score": round(approx_lss, 4),
                        "reserve_depletion_velocity": round(approx_rdv, 4),
                    }
                    lbl = proxy_label(fin_f, news_f)
                    label_counts[lbl] += 1
                    ml_rows.append({
                        "insurer_name": row.get("insurer_name", "Synthetic"),
                        "insurer_category": row.get("insurer_type", "Unknown"),
                        **fin_f,
                        **news_f,
                        "settlement_risk_label": lbl,
                    })
                except (ValueError, KeyError, ZeroDivisionError):
                    continue
        print(f"      Merged {len(ml_rows) - len(insurers)} rows from insurance_synthetic.csv")

    ml_path = DATASETS_DIR / "ml_training_dataset.csv"
    ml_fieldnames = [
        "insurer_name", "insurer_category",
        "reserve_adequacy_index", "claims_pressure_indicator",
        "liquidity_stress_score", "reserve_depletion_velocity",
        "adverse_event_count", "settlement_event_count",
        "regulatory_event_count", "lawsuit_event_count",
        "catastrophe_event_count", "news_risk_score",
        "settlement_risk_label",
    ]
    with open(ml_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ml_fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ml_rows)

    print(f"      Saved {len(ml_rows)} rows → {ml_path.name}")
    print(f"      Label distribution: Low={label_counts[0]}  Moderate={label_counts[1]}  High={label_counts[2]}")

    # --- Generate news corpus ---
    print("\n[4/6] Synthesising news articles corpus (800 articles)...")
    articles = generate_news_corpus(insurers, n_articles=800)
    news_path = DATASETS_DIR / "news_articles_corpus.json"
    with open(news_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
    print(f"      Saved {len(articles)} articles → {news_path.name}")

    # --- Build RAG document manifest ---
    print("\n[5/6] Building RAG document manifest from sources/...")
    if SOURCES_DIR.exists():
        manifest = build_rag_manifest(SOURCES_DIR)
        manifest_path = DATASETS_DIR / "rag_document_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"      Catalogued {len(manifest)} documents → {manifest_path.name}")
    else:
        print(f"      WARNING: sources dir not found at {SOURCES_DIR}. Skipping manifest.")
        manifest = []

    # --- RAG Q&A eval pairs ---
    print("\n[6/6] Writing RAG Q&A evaluation pairs...")
    qa_path = DATASETS_DIR / "rag_qa_eval_pairs.json"
    with open(qa_path, "w", encoding="utf-8") as f:
        json.dump(RAG_QA_PAIRS, f, indent=2, ensure_ascii=False)
    print(f"      Saved {len(RAG_QA_PAIRS)} Q&A pairs → {qa_path.name}")

    # --- Claims dataset ---
    print("\n[+] Generating claims-level dataset (1,000 claims)...")
    claims = generate_claims_dataset(insurers, n_claims=1000)
    claims_path = DATASETS_DIR / "claims_training_dataset.csv"
    claim_fieldnames = [
        "claim_id", "insurer_name", "insurer_category", "policy_type",
        "claim_amount", "premium", "risk_score", "claim_status",
        "settlement_days", "vehicle_value", "_risk_profile",
    ]
    with open(claims_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=claim_fieldnames)
        writer.writeheader()
        writer.writerows(claims)
    print(f"      Saved {len(claims)} rows → {claims_path.name}")

    # --- Summary ---
    print("\n" + "=" * 65)
    print("BUILD COMPLETE — Training datasets ready")
    print("=" * 65)
    print(f"  Output directory : {DATASETS_DIR}")
    print(f"  ML training rows : {len(ml_rows)}")
    print(f"  Financial rows   : {len(all_snapshots)}")
    print(f"  News articles    : {len(articles)}")
    print(f"  RAG documents    : {len(manifest)}")
    print(f"  RAG Q&A pairs    : {len(RAG_QA_PAIRS)}")
    print(f"  Claims rows      : {len(claims)}")
    print(f"  Label dist (ML)  : 0={label_counts[0]} 1={label_counts[1]} 2={label_counts[2]}")
    print("=" * 65)

    # Write a machine-readable build summary for the report generator
    summary = {
        "built_at": date.today().isoformat(),
        "seed": SEED,
        "insurer_count": len(insurers),
        "datasets": {
            "ml_training_dataset": {
                "path": str(ml_path),
                "rows": len(ml_rows),
                "features": [
                    "reserve_adequacy_index", "claims_pressure_indicator",
                    "liquidity_stress_score", "reserve_depletion_velocity",
                    "adverse_event_count", "settlement_event_count",
                    "regulatory_event_count", "lawsuit_event_count",
                    "catastrophe_event_count", "news_risk_score",
                ],
                "target": "settlement_risk_label",
                "label_distribution": {
                    "0_low": label_counts[0],
                    "1_moderate": label_counts[1],
                    "2_high": label_counts[2],
                },
            },
            "insurer_financials_full": {
                "path": str(financials_path),
                "rows": len(all_snapshots),
                "columns": fieldnames,
            },
            "news_articles_corpus": {
                "path": str(news_path),
                "articles": len(articles),
                "categories": ["settlement", "regulatory", "lawsuit", "catastrophe", "neutral"],
            },
            "rag_document_manifest": {
                "path": str(manifest_path) if manifest else None,
                "documents": len(manifest),
            },
            "rag_qa_eval_pairs": {
                "path": str(qa_path),
                "pairs": len(RAG_QA_PAIRS),
                "categories": list({p["category"] for p in RAG_QA_PAIRS}),
            },
            "claims_training_dataset": {
                "path": str(claims_path),
                "rows": len(claims),
            },
        },
    }
    summary_path = DATASETS_DIR / "build_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Build summary written → {summary_path.name}")


if __name__ == "__main__":
    main()
