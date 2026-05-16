from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.circulars import service
from app.modules.circulars.schemas import (
    CircularAnalysisRead,
    CircularTrainResponse,
)

router = APIRouter(
    prefix="/circulars",
    tags=["circulars"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/analyse/{document_id}", response_model=CircularAnalysisRead)
def analyse_circular(document_id: int, db: Session = Depends(get_db)):
    """
    Run the deep learning NLP analysis pipeline on an uploaded circular document.
    Extracts text, runs the MLP classifier, and stores results.
    """
    try:
        analysis = service.analyse_document(db, document_id)
        return analysis
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@router.get("/analysis/{document_id}", response_model=CircularAnalysisRead)
def get_analysis(document_id: int, db: Session = Depends(get_db)):
    """Retrieve existing analysis for a document."""
    analysis = service.get_analysis(db, document_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this document.")
    return analysis


@router.get("/analyses", response_model=list[CircularAnalysisRead])
def list_analyses(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List all circular analysis records."""
    return service.list_analyses(db, skip=skip, limit=limit)


@router.get("/risk-summary")
def risk_summary(db: Session = Depends(get_db)):
    """Count of circulars by fused risk level."""
    return service.risk_summary(db)


@router.post("/train-classifier", response_model=CircularTrainResponse)
def train_classifier():
    """
    Train (or retrain) the deep learning circular classifier using proxy labels.
    """
    result = service.train_classifier()
    return result
