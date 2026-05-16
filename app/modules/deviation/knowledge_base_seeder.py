"""
KnowledgeBaseSeeder — fetches standard insurance clauses from public sources
and inserts them into the standard_clauses table.

Sources used:
  1. IAIS (International Association of Insurance Supervisors) — https://www.iaisweb.org/
     Public standard insurance principles and clause guidance scraped via requests + BeautifulSoup.
  2. Kaggle (optional) — requires KAGGLE_USERNAME and KAGGLE_KEY environment variables.
     Searches for "insurance clause dataset" and downloads the most relevant result.
  3. Built-in Zimbabwe Insurance Act [Chapter 24:07] standard clauses (hardcoded subset).
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Dict, List

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in standard clauses — a representative set from Zimbabwean and
# international insurance standard wording used when scrapers are unavailable.
# ---------------------------------------------------------------------------
_BUILTIN_CLAUSES = [
    # Coverage clauses
    {
        "text": (
            "This policy covers loss or damage to the insured property caused by fire, "
            "lightning, and explosion originating from gas used for domestic purposes, "
            "provided such loss or damage occurs within the territorial limits specified herein."
        ),
        "clause_type": "coverage",
        "source": "Zimbabwe Standard Fire Policy",
        "jurisdiction": "ZW",
    },
    {
        "text": (
            "The Insurer agrees to indemnify the Insured against loss of or damage to the "
            "insured vehicle caused by accidental collision, overturning, fire, external "
            "explosion, self-ignition, lightning, burglary, housebreaking or theft."
        ),
        "clause_type": "coverage",
        "source": "Zimbabwe Motor Vehicle Standard Policy",
        "jurisdiction": "ZW",
    },
    {
        "text": (
            "The Insurer will pay the Insured the sum insured stated in the Schedule in the "
            "event of the death of the life assured from any cause whatsoever during the "
            "term of this policy."
        ),
        "clause_type": "coverage",
        "source": "Zimbabwe Life Assurance Standard Wording",
        "jurisdiction": "ZW",
    },
    # Exclusion clauses
    {
        "text": (
            "This policy does not cover loss, damage, liability or expense directly or "
            "indirectly caused by or contributed to by or arising from ionising radiation "
            "or contamination by radioactivity from any nuclear fuel or from any nuclear waste."
        ),
        "clause_type": "exclusion",
        "source": "IAIS Standard Exclusion Wording",
        "jurisdiction": "international",
    },
    {
        "text": (
            "This policy shall not apply to any liability arising directly or indirectly "
            "out of war, invasion, act of foreign enemies, hostilities (whether war be "
            "declared or not), civil war, rebellion, revolution, insurrection or military "
            "or usurped power."
        ),
        "clause_type": "exclusion",
        "source": "IAIS Standard Exclusion Wording",
        "jurisdiction": "international",
    },
    {
        "text": (
            "This policy excludes any loss, damage or liability arising from or attributable "
            "to wilful misconduct, intentional acts, or deliberate disregard of known risk "
            "by the Insured or any person acting with the knowledge and consent of the Insured."
        ),
        "clause_type": "exclusion",
        "source": "Zimbabwe Standard Policy Exclusion",
        "jurisdiction": "ZW",
    },
    # Condition clauses
    {
        "text": (
            "The Insured shall take all reasonable precautions to prevent loss, damage or "
            "liability. The Insured shall comply with all statutory requirements and "
            "manufacturers' recommendations in respect of the property insured."
        ),
        "clause_type": "condition",
        "source": "IAIS Standard Conditions",
        "jurisdiction": "international",
    },
    {
        "text": (
            "It is a condition of this policy that the Insured shall immediately notify the "
            "Insurer in writing upon becoming aware of any fact, circumstance or occurrence "
            "which may give rise to a claim under this policy."
        ),
        "clause_type": "condition",
        "source": "Zimbabwe General Condition Standard",
        "jurisdiction": "ZW",
    },
    # Claims procedure
    {
        "text": (
            "Upon the occurrence of any event giving rise or likely to give rise to a claim "
            "under this policy, the Insured shall: (a) give immediate notice to the Insurer; "
            "(b) take all practicable steps to prevent further loss or damage; "
            "(c) preserve all property involved for inspection by the Insurer's representative."
        ),
        "clause_type": "claims_procedure",
        "source": "IAIS Claims Notification Standard",
        "jurisdiction": "international",
    },
    {
        "text": (
            "All claims must be submitted in writing within thirty (30) days of the date of "
            "loss or the date on which the Insured became aware of the loss, whichever is "
            "the earlier. Claims submitted after this period may be rejected at the Insurer's "
            "discretion unless the Insured can demonstrate good cause for the delay."
        ),
        "clause_type": "claims_procedure",
        "source": "Zimbabwe Standard Claims Wording",
        "jurisdiction": "ZW",
    },
    # Cancellation
    {
        "text": (
            "This policy may be cancelled at any time by the Insured by giving written notice "
            "to the Insurer, in which case the Insurer shall retain the customary short period "
            "rate for the time this policy has been in force. The Insurer may cancel this "
            "policy by giving thirty (30) days written notice to the Insured."
        ),
        "clause_type": "cancellation",
        "source": "Zimbabwe Standard Cancellation Clause",
        "jurisdiction": "ZW",
    },
    {
        "text": (
            "Either party may terminate this policy by giving not less than thirty (30) days "
            "written notice to the other party. Upon cancellation by the Insurer, the Insured "
            "shall be entitled to a pro-rata refund of the unearned premium."
        ),
        "clause_type": "cancellation",
        "source": "IAIS Standard Cancellation Wording",
        "jurisdiction": "international",
    },
]


class KnowledgeBaseSeeder:
    """Fetches and inserts standard clause data into the standard_clauses table."""

    def fetch_iais_clauses(self) -> List[Dict[str, Any]]:
        """
        Attempt to scrape IAIS public insurance principles from https://www.iaisweb.org/
        Returns clause dicts or empty list on failure.
        """
        try:
            import requests
            from bs4 import BeautifulSoup

            headers = {"User-Agent": "Mozilla/5.0 (compatible; InsuranceIntelligence/1.0)"}
            resp = requests.get(
                "https://www.iaisweb.org/page/supervisory-material",
                headers=headers,
                timeout=20,
            )
            if resp.status_code != 200:
                logger.warning("IAIS page returned %d — skipping.", resp.status_code)
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            clauses = []
            # Extract paragraph-level text blocks that look like standard wording
            for p in soup.find_all("p"):
                text = p.get_text(strip=True)
                if len(text) < 80 or len(text) > 3000:
                    continue
                ctype = _classify_clause_type(text)
                clauses.append({
                    "text": text,
                    "clause_type": ctype,
                    "source": "IAIS",
                    "jurisdiction": "international",
                })
            logger.info("IAIS scraper fetched %d clause candidates.", len(clauses))
            return clauses[:50]  # cap to avoid noise
        except Exception as exc:
            logger.warning("IAIS scraper failed: %s — using built-in clauses only.", exc)
            return []

    def fetch_kaggle_clause_dataset(self) -> List[Dict[str, Any]]:
        """
        Fetch an insurance clause dataset from Kaggle (if credentials set).
        Requires KAGGLE_USERNAME and KAGGLE_KEY env vars.
        """
        kaggle_user = os.environ.get("KAGGLE_USERNAME", "")
        kaggle_key  = os.environ.get("KAGGLE_KEY", "")
        if not kaggle_user or not kaggle_key:
            logger.info("KAGGLE credentials not set — skipping Kaggle fetch.")
            return []

        try:
            import kaggle  # type: ignore
            import pandas as pd
            import tempfile, zipfile, json

            # Search for an insurance clause dataset
            datasets = kaggle.api.dataset_list(search="insurance clause policy")
            if not datasets:
                logger.info("No Kaggle datasets found for 'insurance clause policy'.")
                return []

            # Use the first result
            dataset = datasets[0]
            logger.info("Downloading Kaggle dataset: %s", dataset.ref)

            with tempfile.TemporaryDirectory() as tmpdir:
                kaggle.api.dataset_download_files(dataset.ref, path=tmpdir, unzip=True)

                clauses = []
                # Look for CSV or JSON files in the download
                for root, _, files in os.walk(tmpdir):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        if fname.endswith(".csv"):
                            df = pd.read_csv(fpath, on_bad_lines="skip")
                            for col in df.columns:
                                if "clause" in col.lower() or "text" in col.lower():
                                    for val in df[col].dropna():
                                        text = str(val).strip()
                                        if 50 < len(text) < 3000:
                                            clauses.append({
                                                "text": text,
                                                "clause_type": _classify_clause_type(text),
                                                "source": f"Kaggle:{dataset.ref}",
                                                "jurisdiction": "international",
                                            })
                        elif fname.endswith(".json"):
                            with open(fpath, encoding="utf-8") as f:
                                data = json.load(f)
                            if isinstance(data, list):
                                for item in data:
                                    text = item.get("text") or item.get("clause") or ""
                                    text = str(text).strip()
                                    if 50 < len(text) < 3000:
                                        clauses.append({
                                            "text": text,
                                            "clause_type": item.get("type") or _classify_clause_type(text),
                                            "source": f"Kaggle:{dataset.ref}",
                                            "jurisdiction": "international",
                                        })

            logger.info("Kaggle dataset fetched %d clause candidates.", len(clauses))
            return clauses[:200]
        except Exception as exc:
            logger.warning("Kaggle fetch failed: %s — skipping.", exc)
            return []

    def seed_knowledge_base(self, db: Session) -> Dict[str, int]:
        """
        Orchestrate all fetchers and insert unique clauses into standard_clauses.
        Uses text hash to prevent duplicates.
        """
        from app.modules.deviation.model import StandardClause

        all_clauses = list(_BUILTIN_CLAUSES)  # start with built-ins
        all_clauses += self.fetch_iais_clauses()
        all_clauses += self.fetch_kaggle_clause_dataset()

        iais_count = 0
        kaggle_count = 0
        inserted = 0

        for clause in all_clauses:
            text = clause.get("text", "").strip()
            if not text:
                continue

            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

            # Skip if already in DB
            existing = (
                db.query(StandardClause)
                .filter(StandardClause.text_hash == text_hash)
                .first()
            )
            if existing:
                continue

            try:
                sc = StandardClause(
                    text=text,
                    clause_type=clause.get("clause_type", "general"),
                    source=clause.get("source", "unknown"),
                    jurisdiction=clause.get("jurisdiction", "international"),
                    text_hash=text_hash,
                )
                db.add(sc)
                db.commit()
                inserted += 1
                src = clause.get("source", "")
                if "IAIS" in src:
                    iais_count += 1
                elif "Kaggle" in src:
                    kaggle_count += 1
            except Exception as exc:
                logger.warning("Failed to insert standard clause: %s", exc)
                db.rollback()

        logger.info("Knowledge base seeded: %d new clauses inserted.", inserted)
        return {
            "iais_clauses": iais_count,
            "kaggle_clauses": kaggle_count,
            "total_inserted": inserted,
        }


def _classify_clause_type(text: str) -> str:
    """Classify a text block into a clause type based on keyword presence."""
    t = text.lower()
    if any(w in t for w in ("exclusion", "excluded", "not covered", "does not cover")):
        return "exclusion"
    if any(w in t for w in ("coverage", "covers", "insured amount", "limit of indemnity")):
        return "coverage"
    if any(w in t for w in ("cancellation", "cancel", "termination", "terminate")):
        return "cancellation"
    if any(w in t for w in ("claim", "notify", "notification", "report the loss")):
        return "claims_procedure"
    if any(w in t for w in ("condition", "warranted", "warranty", "shall not")):
        return "condition"
    return "general"
