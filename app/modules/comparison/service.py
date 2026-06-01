"""
ComparisonService — orchestrates document comparison end-to-end.
Extracts clauses from existing circular_analyses, aligns them,
and generates the delta report.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.modules.comparison.clause_aligner import ClauseAligner
from app.modules.comparison.delta_reporter import DeltaReporter
from app.modules.shared.clause_classifier import classify_clause_type as _classify_clause_type

logger = logging.getLogger(__name__)


class ComparisonService:
    """Orchestrates the full clause comparison pipeline."""

    def __init__(self) -> None:
        self._aligner = ClauseAligner()
        self._reporter = DeltaReporter()

    def compare(
        self, doc_a_id: int, doc_b_id: int, db: Session
    ) -> Dict[str, Any]:
        """
        Compare two documents clause-by-clause.
        Returns the full delta report dict.
        """
        # Step 1 — extract clauses for both documents
        clauses_a = self._extract_clauses(doc_a_id, db)
        clauses_b = self._extract_clauses(doc_b_id, db)

        # Step 2 — align clauses
        alignments = self._aligner.align(clauses_a, clauses_b)

        # Step 3 — generate and persist report
        report = self._reporter.generate_report(doc_a_id, doc_b_id, alignments, db)
        return report

    # ------------------------------------------------------------------
    # Clause extraction
    # ------------------------------------------------------------------

    def _extract_clauses(
        self, document_id: int, db: Session
    ) -> List[Dict[str, Any]]:
        """
        Extract clause-like structures for a document.
        Primary: parse circular_analyses.extracted_text using NLP patterns.
        Fallback: chunk the raw text into 400-char blocks if < 3 clauses found.
        """
        from app.modules.circulars.model import CircularAnalysis

        analysis = (
            db.query(CircularAnalysis)
            .filter(CircularAnalysis.document_id == document_id)
            .first()
        )

        text = ""
        if analysis and analysis.extracted_text:
            text = analysis.extracted_text

        if not text:
            # Try to re-extract from file
            from app.modules.documents.model import Document
            from app.modules.circulars.extractor import extract_text, clean_text
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                text = clean_text(extract_text(doc.file_path))

        if not text:
            return []

        clauses = self._parse_clauses_from_text(text, document_id)

        # Fallback to chunked comparison if not enough clause structure found
        if len(clauses) < 3:
            clauses = self._chunk_as_clauses(text, document_id)

        return clauses

    def _parse_clauses_from_text(
        self, text: str, document_id: int
    ) -> List[Dict[str, Any]]:
        """
        Parse the extracted text into clause-like dicts using heuristics.
        Looks for numbered sections, headers, and keyword-delimited blocks.
        """
        clauses = []
        # Split on numbered section patterns: "1.", "1.1", "Section 1", "CLAUSE 1"
        section_pattern = re.compile(
            r"(?:^|\n)(?:CLAUSE\s+\d+|Section\s+\d+|\d+\.\d*\s+[A-Z]|\d+\.\s+[A-Z])",
            re.IGNORECASE,
        )
        boundaries = [m.start() for m in section_pattern.finditer(text)]
        boundaries.append(len(text))

        for idx in range(len(boundaries) - 1):
            start = boundaries[idx]
            end = boundaries[idx + 1]
            chunk = text[start:end].strip()
            if len(chunk) < 20:  # skip very short fragments
                continue
            # Classify the clause type by keywords in the chunk
            ctype = _classify_clause_type(chunk)
            clauses.append({
                "clause_id": f"doc{document_id}_clause_{idx}",
                "clause_type": ctype,
                "text": chunk[:2000],  # cap length for embedding
                "char_start": start,
                "char_end": end,
                "section_number": str(idx),
            })

        return clauses

    def _chunk_as_clauses(
        self, text: str, document_id: int
    ) -> List[Dict[str, Any]]:
        """Fall back to 400-char overlapping chunks treated as clauses."""
        chunk_size = 400
        overlap = 80
        clauses = []
        pos = 0
        idx = 0
        while pos < len(text):
            end = min(pos + chunk_size, len(text))
            chunk = text[pos:end].strip()
            if chunk:
                ctype = _classify_clause_type(chunk)
                clauses.append({
                    "clause_id": f"doc{document_id}_chunk_{idx}",
                    "clause_type": ctype,
                    "text": chunk,
                    "char_start": pos,
                    "char_end": end,
                    "section_number": str(idx),
                })
                idx += 1
            pos = end - overlap if end - overlap > pos else pos + 1
        return clauses

