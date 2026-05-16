from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from datetime import date

from app.core.db import get_db
from app.modules.financials.schemas import FinancialSnapshotRead
from app.modules.financials.repo import FinancialRepo
from app.modules.financials.service import FinancialService
from app.modules.financials.features import FinancialFeatureEngineer
from app.modules.financials.dev_seed import seed_financials_for_all_insurers, SeedConfig
from app.modules.auth.dependencies import get_current_user


router = APIRouter(
    prefix="/financials",
    tags=["financials"],
    dependencies=[Depends(get_current_user)],
)
repo = FinancialRepo()
service = FinancialService()


@router.post("/upload")
async def upload_financials_csv(
    file: UploadFile = File(...),
    create_missing_insurers: bool = Query(True),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    content = await file.read()
    try:
        result = service.upload_csv(db, content, create_missing_insurers=create_missing_insurers)
        return {"status": "ok", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{insurer_id}", response_model=list[FinancialSnapshotRead])
def list_financials(insurer_id: int, skip: int = 0, limit: int = 200, db: Session = Depends(get_db)):
    return repo.list_by_insurer(db, insurer_id, skip=skip, limit=limit)


@router.get("/{insurer_id}/latest", response_model=FinancialSnapshotRead)
def latest_financial(insurer_id: int, db: Session = Depends(get_db)):
    snap = repo.latest(db, insurer_id)
    if not snap:
        raise HTTPException(status_code=404, detail="No financial snapshots found for this insurer.")
    return snap


@router.get("/{insurer_id}/range", response_model=list[FinancialSnapshotRead])
def range_financials(insurer_id: int, start: date, end: date, db: Session = Depends(get_db)):
    return repo.list_by_range(db, insurer_id, start=start, end=end)

@router.get("/{insurer_id}/features")
def compute_financial_features(
    insurer_id: int,
    days: int = 90,
    db: Session = Depends(get_db),
):
    snapshots = repo.list_last_days(db, insurer_id, days=days)

    if not snapshots:
        raise HTTPException(
            status_code=404,
            detail="No financial snapshots found for this insurer in the requested window.",
        )

    engineer = FinancialFeatureEngineer(snapshots)
    features = engineer.compute_feature_vector()

    return {
        "insurer_id": insurer_id,
        "window_days": days,
        "snapshots_used": len(snapshots),
        "features": features,
    }

@router.post("/dev/seed")
def dev_seed_financials(months: int = 6, db: Session = Depends(get_db)):
    """
    DEV ONLY: seeds synthetic financial snapshots for all insurers
    so the ML demo model has enough training rows.
    """
    return seed_financials_for_all_insurers(db, SeedConfig(months=months))
