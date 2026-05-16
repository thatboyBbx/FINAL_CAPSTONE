"""
Multilingual Router — /api/multilingual endpoints.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/multilingual",
    tags=["multilingual"],
    dependencies=[Depends(get_current_user)],
)


class DetectRequest(BaseModel):
    text: str


@router.get("/document/{document_id}")
def get_document_language_analysis(
    document_id: int, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Return stored language analysis for a document."""
    from app.modules.multilingual.model import DocumentLanguageAnalysis

    row = (
        db.query(DocumentLanguageAnalysis)
        .filter(DocumentLanguageAnalysis.document_id == document_id)
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No language analysis found for document id={document_id}.",
        )
    return {
        "document_id": row.document_id,
        "primary_language": row.primary_language,
        "is_mixed_language": row.is_mixed_language,
        "shona_segment_count": row.shona_segment_count,
        "shona_pct": row.shona_pct,
        "segments": row.segments_json,
        "translations": row.translations_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/detect")
def detect_language(payload: DetectRequest) -> Dict[str, Any]:
    """
    Detect the language of arbitrary text.
    Used for testing and validation.
    """
    try:
        from app.ai.multilingual.language_detector import LanguageDetector
        detector = LanguageDetector()
        return detector.detect_language(payload.text)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Language detection unavailable: {exc}",
        )
    except Exception as exc:
        logger.error("Language detection failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
