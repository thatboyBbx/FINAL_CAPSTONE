"""
DeltaReporter — builds the structured comparison report from clause alignments.
Detects coverage reductions, new exclusions, and high-risk changes.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DeltaReporter:
    """Builds and persists a structured delta report from clause alignments."""

    def generate_report(
        self,
        doc_a_id: int,
        doc_b_id: int,
        alignments: List[Dict[str, Any]],
        db: Session,
    ) -> Dict[str, Any]:
        """
        Build the full comparison delta report and save it to document_comparisons.
        Returns the complete report dict.
        """
        from app.modules.documents.model import Document
        from app.modules.comparison.model import DocumentComparison

        # Fetch document metadata
        doc_a = db.query(Document).filter(Document.id == doc_a_id).first()
        doc_b = db.query(Document).filter(Document.id == doc_b_id).first()

        doc_a_meta = _doc_meta(doc_a)
        doc_b_meta = _doc_meta(doc_b)

        # Count alignment statuses
        counts = {"identical": 0, "modified": 0, "added": 0, "removed": 0}
        for a in alignments:
            counts[a["status"]] = counts.get(a["status"], 0) + 1

        total_a = counts["identical"] + counts["modified"] + counts["removed"]
        total_b = counts["identical"] + counts["modified"] + counts["added"]

        # Overall similarity: weighted average of similarity scores across all alignments
        sim_scores = [a["similarity_score"] for a in alignments if a["similarity_score"] > 0]
        overall_sim = round(sum(sim_scores) / len(sim_scores), 4) if sim_scores else 0.0

        # Classify changes into categories
        coverage_changes = self._find_coverage_changes(alignments)
        exclusion_changes = self._find_exclusion_changes(alignments)
        high_risk_changes = self._find_high_risk_changes(
            coverage_changes, exclusion_changes, alignments
        )

        summary = {
            "total_clauses_a": total_a,
            "total_clauses_b": total_b,
            "identical": counts["identical"],
            "modified": counts["modified"],
            "added": counts["added"],
            "removed": counts["removed"],
            "similarity_score_overall": overall_sim,
        }

        report = {
            "comparison_id": None,  # filled after DB insert
            "document_a": doc_a_meta,
            "document_b": doc_b_meta,
            "summary": summary,
            "coverage_changes": coverage_changes,
            "exclusion_changes": exclusion_changes,
            "high_risk_changes": high_risk_changes,
            "all_changes": alignments,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Persist to DB
        try:
            comp = DocumentComparison(
                document_a_id=doc_a_id,
                document_b_id=doc_b_id,
                status="complete",
                summary=summary,
                coverage_changes=coverage_changes,
                exclusion_changes=exclusion_changes,
                high_risk_changes=high_risk_changes,
                all_changes=alignments,
                overall_similarity_score=overall_sim,
                completed_at=datetime.now(timezone.utc),
            )
            db.add(comp)
            db.commit()
            db.refresh(comp)
            report["comparison_id"] = comp.id
        except Exception as exc:
            logger.error("Failed to save comparison to DB: %s", exc)
            db.rollback()
            report["comparison_id"] = -1

        return report

    # ------------------------------------------------------------------
    # Change classifiers
    # ------------------------------------------------------------------

    def _find_coverage_changes(
        self, alignments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect coverage clauses where the monetary limit changed.
        Flags reductions (coverage in B < coverage in A) as high risk.
        """
        from app.infrastructure.scrapers.scraper_utils import parse_usd_value

        changes = []
        for a in alignments:
            if a["clause_type"] != "coverage":
                continue
            if a["status"] not in ("modified",):
                continue

            ca = a.get("clause_a") or {}
            cb = a.get("clause_b") or {}
            text_a = ca.get("text", "")
            text_b = cb.get("text", "")

            val_a = parse_usd_value(text_a)
            val_b = parse_usd_value(text_b)

            change_entry = {
                "clause_type": "coverage",
                "change_summary": a["change_summary"],
                "similarity_score": a["similarity_score"],
                "value_a": val_a,
                "value_b": val_b,
                "is_reduction": (val_a is not None and val_b is not None and val_b < val_a),
                "clause_a": ca,
                "clause_b": cb,
            }
            changes.append(change_entry)

        return changes

    def _find_exclusion_changes(
        self, alignments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify exclusion clauses that were added or modified."""
        changes = []
        for a in alignments:
            if a["clause_type"] != "exclusion":
                continue
            if a["status"] in ("added", "modified"):
                changes.append({
                    "clause_type": "exclusion",
                    "status": a["status"],
                    "change_summary": a["change_summary"],
                    "similarity_score": a["similarity_score"],
                    "clause_a": a.get("clause_a"),
                    "clause_b": a.get("clause_b"),
                    "is_new_exclusion": a["status"] == "added",
                })
        return changes

    def _find_high_risk_changes(
        self,
        coverage_changes: List[Dict[str, Any]],
        exclusion_changes: List[Dict[str, Any]],
        all_alignments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Compile high-risk changes: coverage reductions + new exclusions."""
        high_risk = []
        for c in coverage_changes:
            if c.get("is_reduction"):
                high_risk.append({**c, "risk_reason": "Coverage limit reduced in document B."})
        for e in exclusion_changes:
            if e.get("is_new_exclusion"):
                high_risk.append({**e, "risk_reason": "New exclusion added in document B."})
        # Also flag removed clauses that were coverage type
        for a in all_alignments:
            if a["status"] == "removed" and a["clause_type"] == "coverage":
                high_risk.append({
                    **a,
                    "risk_reason": "Coverage clause removed in document B.",
                })
        return high_risk


def _doc_meta(doc) -> Dict[str, Any]:
    if not doc:
        return {"id": None, "filename": "Unknown", "document_type": "Unknown"}
    return {
        "id": doc.id,
        "filename": doc.original_filename,
        "document_type": getattr(doc, "document_category", "unknown") or "unknown",
    }
