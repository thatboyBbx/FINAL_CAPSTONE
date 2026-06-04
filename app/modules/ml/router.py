from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.ml.trainer import MLTrainer
from app.modules.ml.predictor import MLPredictor
from app.modules.ml.explain import MLExplainer
from app.modules.ml.forecaster import get_forecaster
from app.modules.scoring.fusion import compute_fused_risk
from app.modules.auth.dependencies import get_current_user, require_role

router    = APIRouter(
    prefix="/ml",
    tags=["ml"],
    dependencies=[Depends(get_current_user)],
)
trainer   = MLTrainer()
predictor = MLPredictor()
explainer = MLExplainer()


# ---------------------------------------------------------------------------
# Train
# ---------------------------------------------------------------------------

@router.post("/train")
def train_model(
    profile: str = Query("demo", pattern="^(demo|app)$"),
    days: int = 90,
    test_size: float = 0.3,
    labels_csv_path: str | None = None,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    try:
        result = trainer.train(
            db=db,
            profile=profile,
            days=days,
            test_size=test_size,
            labels_csv_path=labels_csv_path,
        )
        return {"status": "ok", "meta": result.meta, "report": result.report}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Predict (tabular ML)
# ---------------------------------------------------------------------------

@router.get("/predict/{insurer_id}")
def predict_insurer(
    insurer_id: int,
    profile: str = Query("demo", pattern="^(demo|app)$"),
    days: int = 90,
    db: Session = Depends(get_db),
):
    try:
        return predictor.predict(db=db, insurer_id=insurer_id, profile=profile, days=days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Explain (SHAP / feature contributions)
# ---------------------------------------------------------------------------

@router.get("/explain/{insurer_id}")
def explain_prediction(
    insurer_id: int,
    profile: str = Query("demo", pattern="^(demo|app)$"),
    days: int = 90,
    db: Session = Depends(get_db),
):
    try:
        return explainer.explain(db=db, insurer_id=insurer_id, profile=profile, days=days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Fused risk score (ML + News + Circular)
# ---------------------------------------------------------------------------

@router.get("/fused-risk/{insurer_id}")
def fused_risk(
    insurer_id: int,
    profile: str = Query("demo", pattern="^(demo|app)$"),
    days: int = 90,
    db: Session = Depends(get_db),
):
    """
    Compute the hybrid risk score fusing:
      - ML tabular model (GBDT)
      - News NLP risk signals
      - Circular deep learning risk signals
    with time-decay weighting.
    """
    try:
        result = compute_fused_risk(db=db, insurer_id=insurer_id, profile=profile, days=days)
        return {
            "insurer_id":               result.insurer_id,
            "fused_score":              result.fused_score,
            "fused_label":              result.fused_label,
            "ml_score":                 result.ml_score,
            "news_score_normalised":    result.news_score_normalised,
            "circular_score_normalised": result.circular_score_normalised,
            "weights": {
                "ml":       result.ml_weight_used,
                "news":     result.news_weight_used,
                "circular": result.circular_weight_used,
            },
            "details": result.details,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Financial Forecaster (DL time-series)
# ---------------------------------------------------------------------------

@router.post("/train-forecaster")
def train_forecaster(
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """
    Train the deep learning (MLP neural network) financial time-series forecaster.
    Requires at least 5 financial snapshots per insurer.
    """
    forecaster = get_forecaster()
    result = forecaster.train(db=db)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result["detail"])
    return result


@router.get("/forecast/{insurer_id}")
def forecast_financials(insurer_id: int, db: Session = Depends(get_db)):
    """
    Predict next-period financial metrics using the DL forecaster.
    Returns predicted values + risk trajectory (improving/stable_risk/deteriorating).
    """
    forecaster = get_forecaster()
    return forecaster.predict(db=db, insurer_id=insurer_id)


# ---------------------------------------------------------------------------
# Document Ingestion + Circular Classifier
# ---------------------------------------------------------------------------

_training_executor = ThreadPoolExecutor(max_workers=1)
_training_status: dict = {"running": False, "last_result": None}


def _run_training_sync(sources=None):
    """Blocking training job — runs in thread pool."""
    global _training_status
    try:
        from app.modules.ml.training_orchestrator import build_and_train
        result = build_and_train(sources=sources)
        _training_status["last_result"] = result
    except Exception as e:
        _training_status["last_result"] = {"status": "error", "error": str(e)}
    finally:
        _training_status["running"] = False


@router.post("/ingest-and-train")
def ingest_and_train(
    background_tasks: BackgroundTasks,
    _admin=Depends(require_role("admin")),
):
    """
    Ingest all PDFs from the configured circular + KB directories,
    build a labelled corpus, and train the circular classifier.
    Runs in background — poll /ml/training-status for progress.
    """
    global _training_status
    if _training_status["running"]:
        return {"status": "already_running", "message": "Training already in progress."}

    _training_status["running"] = True
    background_tasks.add_task(_run_training_sync)
    return {
        "status": "started",
        "message": "Ingestion and training started in background. Poll /ml/training-status.",
    }


@router.get("/training-status")
def training_status():
    """Poll current training / ingestion status."""
    from app.modules.ml.training_orchestrator import get_training_status
    sys_status = get_training_status()
    return {
        "running": _training_status["running"],
        "last_result": _training_status["last_result"],
        "system": sys_status,
    }


@router.post("/classify-circular")
def classify_circular(payload: dict):
    """
    Classify a single document by category.
    Body: {"text": "...", "filename": "Circular 3 of 2024.pdf"}
    """
    from app.modules.ml.circular_classifier import predict_circular_category
    text = payload.get("text", "")
    filename = payload.get("filename", "")
    if not text and not filename:
        raise HTTPException(status_code=400, detail="Provide at least 'text' or 'filename'.")
    return predict_circular_category(text=text, filename=filename)
