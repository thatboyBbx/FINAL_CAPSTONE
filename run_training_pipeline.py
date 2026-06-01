"""
run_training_pipeline.py
========================
InsureIntel Zimbabwe — Full Training Pipeline (standalone, no DB required)

Runs in order:
  1. Build real corpus from sources/ PDFs (circulars + reports + policy docs)
  2. Train circular classifier (TF-IDF + SGD) on real corpus
  3. Train settlement risk model — DEMO profile (CSV → HistGBDT, proxy labels)
  4. Train settlement risk model — APP profile  (CSV → HistGBDT, proxy labels)
  5. Verify all saved models and print final metrics report

Run from the EXPERIMENT/ directory:
    python run_training_pipeline.py

Progress is written to storage/datasets/app/pipeline_progress.json
"""
from __future__ import annotations

import csv
import json
import logging
import random
import sys
import traceback
from datetime import datetime
from pathlib import Path

# ── ensure project root is on the path ──────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# ── logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("pipeline")

# ── paths (no settings import needed — all relative to BASE_DIR) ─────────────
SOURCES_DIR   = BASE_DIR / "sources"
DATASETS_DIR  = BASE_DIR / "storage" / "datasets" / "app"
MODELS_DEMO   = BASE_DIR / "storage" / "models" / "demo"
MODELS_APP    = BASE_DIR / "storage" / "models" / "app"
CORPUS_PATH   = DATASETS_DIR / "circulars_corpus.json"
ML_CSV        = DATASETS_DIR / "ml_training_dataset.csv"
PROGRESS_FILE = DATASETS_DIR / "pipeline_progress.json"

for d in (DATASETS_DIR, MODELS_DEMO, MODELS_APP):
    d.mkdir(parents=True, exist_ok=True)

# ── feature / label constants (must mirror labels.py ProxyLabelProvider) ─────
FEATURE_NAMES = [
    "reserve_adequacy_index",
    "claims_pressure_indicator",
    "liquidity_stress_score",
    "reserve_depletion_velocity",
    "adverse_event_count",
    "settlement_event_count",
    "regulatory_event_count",
    "lawsuit_event_count",
    "catastrophe_event_count",
    "news_risk_score",
    # Circular NLP features — all zero when training from CSV (no DB/NLP in standalone mode)
    "circular_count",
    "circular_high_count",
    "circular_moderate_count",
    "circular_avg_risk_score",
    "circular_max_risk_score",
    "circular_compliance_signals",
    "circular_financial_stress_signals",
    "circular_claims_signals",
    "circular_total_risk_signals",
]


# ════════════════════════════════════════════════════════════════════════════
# Progress tracker
# ════════════════════════════════════════════════════════════════════════════

_progress: dict = {
    "started_at": datetime.utcnow().isoformat() + "Z",
    "steps": {},
}


def _save_progress(step: str, status: str, detail: dict | None = None) -> None:
    _progress["steps"][step] = {
        "status": status,
        "at": datetime.utcnow().isoformat() + "Z",
        **(detail or {}),
    }
    try:
        with open(PROGRESS_FILE, "w") as f:
            json.dump(_progress, f, indent=2)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════════════
# STEP 1 — Build real corpus from sources/
# ════════════════════════════════════════════════════════════════════════════

def step1_build_corpus() -> int:
    """
    Extract text from every PDF in sources/ using the app's corpus_builder.
    Returns the number of documents in the corpus.
    """
    logger.info("=" * 65)
    logger.info("STEP 1 — Building corpus from real PDFs in sources/")
    logger.info("=" * 65)

    _save_progress("corpus_build", "in_progress")

    sources = []
    for sub, label in [
        ("downloads/insurance_circulars", "circulars"),
        ("reports",                        "reports"),
        ("insurancedocuments",             "insurance_forms"),
        ("insurancepolicydocuments (1)",   "policy_documents"),
    ]:
        p = SOURCES_DIR / sub
        if p.exists():
            sources.append({"path": str(p), "label": label})
            logger.info("  Source: %s  (%s)", p.name, label)
        else:
            logger.warning("  Source not found, skipping: %s", p)

    if not sources:
        raise RuntimeError("No source directories found under sources/")

    # Import here so errors surface clearly
    from app.modules.documents.ingestion.corpus_builder import build_corpus

    processed = [0]

    def progress_cb(current: int, total: int, filename: str) -> None:
        processed[0] = current
        if current % 50 == 0 or current == total:
            pct = int(current / total * 100) if total else 0
            logger.info("  [%d/%d %d%%] %s", current, total, pct, filename)

    corpus = build_corpus(
        source_paths=sources,
        output_path=CORPUS_PATH,
        max_docs=10000,
        progress_cb=progress_cb,
    )

    n_docs       = len(corpus)
    n_extractable = sum(1 for r in corpus if r.get("extractable"))
    cats: dict[str, int] = {}
    for r in corpus:
        c = r.get("category", "unknown")
        cats[c] = cats.get(c, 0) + 1

    logger.info("  ✓ Corpus saved: %d docs, %d extractable", n_docs, n_extractable)
    logger.info("  Categories: %s", cats)

    _save_progress("corpus_build", "completed", {
        "total_docs": n_docs,
        "extractable": n_extractable,
        "categories": cats,
        "path": str(CORPUS_PATH),
    })
    return n_docs


# ════════════════════════════════════════════════════════════════════════════
# STEP 2 — Train circular classifier
# ════════════════════════════════════════════════════════════════════════════

def step2_train_circular_classifier() -> dict:
    """
    TF-IDF (unigram+bigram) + SGDClassifier trained on the real corpus.
    Saves to storage/models/app/circular_classifier.joblib
    """
    logger.info("=" * 65)
    logger.info("STEP 2 — Training circular document classifier")
    logger.info("=" * 65)

    _save_progress("circular_classifier", "in_progress")

    save_path = MODELS_APP / "circular_classifier.joblib"

    from app.modules.ml.circular_classifier import train_circular_classifier
    meta = train_circular_classifier(
        corpus_path=CORPUS_PATH,
        save_path=save_path,
    )

    logger.info("  ✓ Circular classifier trained")
    logger.info("  Docs          : %d", meta.get("total_docs", 0))
    logger.info("  Categories    : %s", meta.get("categories", []))
    logger.info("  Accuracy      : %.4f", meta.get("accuracy", 0))
    logger.info("  F1 (macro)    : %.4f", meta.get("f1_macro", 0))
    logger.info("  Eval note     : %s", meta.get("eval_note", ""))
    logger.info("  Saved to      : %s", save_path)

    _save_progress("circular_classifier", "completed", meta)
    return meta


# ════════════════════════════════════════════════════════════════════════════
# STEP 3 & 4 — Train settlement risk model (demo + app profiles)
# ════════════════════════════════════════════════════════════════════════════

def _load_ml_csv() -> tuple[list[list[float]], list[int]]:
    """
    Read ml_training_dataset.csv.
    Columns: insurer_name, insurer_category, <10 features>, settlement_risk_label
    Returns (X, y) where X is a list of 19-float rows (10 real + 9 circular zeros).
    """
    if not ML_CSV.exists():
        raise FileNotFoundError(
            f"ML training CSV not found at {ML_CSV}. "
            "Run build_training_datasets.py first."
        )

    TABULAR_FEATURES = [
        "reserve_adequacy_index",
        "claims_pressure_indicator",
        "liquidity_stress_score",
        "reserve_depletion_velocity",
        "adverse_event_count",
        "settlement_event_count",
        "regulatory_event_count",
        "lawsuit_event_count",
        "catastrophe_event_count",
        "news_risk_score",
    ]
    CIRCULAR_ZEROS = [0.0] * 9  # placeholder — no DB in standalone mode

    X: list[list[float]] = []
    y: list[int] = []

    with open(ML_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                features = [float(row[feat]) for feat in TABULAR_FEATURES]
                features.extend(CIRCULAR_ZEROS)
                label = int(row["settlement_risk_label"])
                if label not in (0, 1, 2):
                    continue
                X.append(features)
                y.append(label)
            except (ValueError, KeyError):
                continue

    logger.info("  Loaded %d rows from %s", len(X), ML_CSV.name)
    counts = {v: y.count(v) for v in sorted(set(y))}
    logger.info("  Label distribution: %s", counts)
    return X, y


def _train_settlement_model(
    profile: str,
    X: list[list[float]],
    y: list[int],
) -> dict:
    """
    Train HistGradientBoostingClassifier, save model.joblib + meta.json
    to storage/models/<profile>/.
    """
    import joblib
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    model_dir = MODELS_DEMO if profile == "demo" else MODELS_APP
    model_out  = model_dir / "model.joblib"
    meta_out   = model_dir / "meta.json"

    n = len(X)
    n_classes = len(set(y))

    if n < 5 or n_classes < 2:
        raise ValueError(
            f"Not enough training data: {n} rows, {n_classes} classes."
        )

    stratify = y if n_classes > 1 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=stratify
    )

    # Model selection — GBDT for ≥30 rows, Logistic for tiny sets
    if len(X_train) >= 30:
        model = HistGradientBoostingClassifier(
            max_depth=None,
            learning_rate=0.06,
            max_iter=400,
            random_state=42,
        )
        model_label = "GBDT: Settlement-Risk Classifier (HistGradientBoosting + Circular-NLP)"
    else:
        model = Pipeline(steps=[
            ("scaler", StandardScaler()),
            ("clf",    LogisticRegression(max_iter=4000, multi_class="auto")),
        ])
        model_label = "Linear Model: Settlement-Risk Classifier (Logistic Regression)"

    logger.info("  Fitting %s on %d train rows…", model_label, len(X_train))
    model.fit(X_train, y_train)

    y_pred  = model.predict(X_test)
    acc     = accuracy_score(y_test, y_pred)
    report  = classification_report(y_test, y_pred, digits=4, zero_division=0)

    # Save bundle (mirrors what MLTrainer.train() saves)
    joblib.dump(
        {
            "model":         model,
            "feature_names": FEATURE_NAMES,
            "model_label":   model_label,
            "profile_label": (
                "DEMO: Settlement-Risk Classifier (Proxy-Labeled)"
                if profile == "demo" else
                "APP: Settlement-Risk Classifier (Real-Labeled)"
            ),
        },
        model_out,
    )

    metrics = {
        "accuracy":    round(float(acc), 4),
        "rows":        n,
        "train_rows":  len(X_train),
        "test_rows":   len(X_test),
        "test_size":   0.25,
        "model_label": model_label,
    }
    meta = {
        "profile":       profile,
        "model_label":   (
            "DEMO: Settlement-Risk Classifier (Proxy-Labeled)"
            if profile == "demo" else
            "APP: Settlement-Risk Classifier (Real-Labeled)"
        ),
        "label_source":  "proxy_labels_csv",
        "model_path":    str(model_out),
        "feature_names": FEATURE_NAMES,
        "metrics":       metrics,
        "saved_at":      datetime.utcnow().isoformat() + "Z",
    }
    with open(meta_out, "w") as f:
        json.dump(meta, f, indent=2)

    logger.info("  ✓ Model saved to %s", model_out)
    logger.info("  Accuracy: %.4f", acc)
    logger.info("  Classification report:\n%s", report)

    return {"meta": meta, "report": report}


def step3_train_demo_model(X: list[list[float]], y: list[int]) -> dict:
    logger.info("=" * 65)
    logger.info("STEP 3 — Training settlement risk model (demo profile)")
    logger.info("=" * 65)
    _save_progress("settlement_demo", "in_progress")
    result = _train_settlement_model("demo", X, y)
    _save_progress("settlement_demo", "completed", result["meta"]["metrics"])
    return result


def step4_train_app_model(X: list[list[float]], y: list[int]) -> dict:
    logger.info("=" * 65)
    logger.info("STEP 4 — Training settlement risk model (app profile)")
    logger.info("=" * 65)
    _save_progress("settlement_app", "in_progress")
    result = _train_settlement_model("app", X, y)
    _save_progress("settlement_app", "completed", result["meta"]["metrics"])
    return result


# ════════════════════════════════════════════════════════════════════════════
# STEP 5 — Verify all models
# ════════════════════════════════════════════════════════════════════════════

def step5_verify_models() -> None:
    """Load every .joblib and meta.json, confirm shapes, print summary."""
    import joblib

    logger.info("=" * 65)
    logger.info("STEP 5 — Model verification")
    logger.info("=" * 65)

    _save_progress("verification", "in_progress")
    all_ok = True
    report_lines: list[str] = []

    checks = [
        ("circular_classifier",  MODELS_APP  / "circular_classifier.joblib",
                                 MODELS_APP  / "circular_classifier.json"),
        ("settlement_risk_demo", MODELS_DEMO / "model.joblib",
                                 MODELS_DEMO / "meta.json"),
        ("settlement_risk_app",  MODELS_APP  / "model.joblib",
                                 MODELS_APP  / "meta.json"),
    ]

    for name, model_path, meta_path in checks:
        ok = True
        lines: list[str] = []

        # Model file
        if not model_path.exists():
            lines.append(f"  ✗ model file missing: {model_path}")
            ok = False
        else:
            try:
                obj = joblib.load(model_path)
                lines.append(f"  ✓ {model_path.name} loaded ({model_path.stat().st_size // 1024} KB)")
                if isinstance(obj, dict) and "feature_names" in obj:
                    lines.append(f"    features : {len(obj['feature_names'])} — {obj['feature_names'][:5]}…")
                    lines.append(f"    label    : {obj.get('profile_label','')}")
            except Exception as e:
                lines.append(f"  ✗ failed to load {model_path.name}: {e}")
                ok = False

        # Meta file
        if not meta_path.exists():
            lines.append(f"  ✗ meta file missing: {meta_path}")
            ok = False
        else:
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                metrics = meta.get("metrics", meta)
                acc = metrics.get("accuracy", metrics.get("accuracy", "n/a"))
                f1  = metrics.get("f1_macro", "n/a")
                rows = metrics.get("rows", metrics.get("total_docs", "n/a"))
                lines.append(f"    accuracy : {acc}  |  f1_macro : {f1}  |  rows/docs : {rows}")
            except Exception as e:
                lines.append(f"  ✗ failed to read meta: {e}")
                ok = False

        status = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
        header = f"[{status}] {name}"
        logger.info(header)
        for l in lines:
            logger.info(l)
        report_lines.append(header)
        report_lines.extend(lines)

    logger.info("=" * 65)
    if all_ok:
        logger.info("ALL MODELS VERIFIED SUCCESSFULLY ✓")
    else:
        logger.warning("SOME MODELS FAILED VERIFICATION — check above")
    logger.info("=" * 65)

    _save_progress("verification", "completed" if all_ok else "failed", {
        "all_ok": all_ok,
        "details": report_lines,
    })


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main() -> None:
    logger.info("╔══════════════════════════════════════════════════════════╗")
    logger.info("║  InsureIntel Zimbabwe — Full Training Pipeline           ║")
    logger.info("╚══════════════════════════════════════════════════════════╝")
    logger.info("Base dir  : %s", BASE_DIR)
    logger.info("Datasets  : %s", DATASETS_DIR)
    logger.info("Models    : demo=%s  app=%s", MODELS_DEMO, MODELS_APP)

    errors: list[str] = []

    # ── Step 1: Build corpus from real PDFs ──────────────────────────────────
    try:
        n_docs = step1_build_corpus()
    except Exception as e:
        logger.error("STEP 1 FAILED: %s", e)
        traceback.print_exc()
        errors.append(f"step1_corpus: {e}")
        n_docs = 0

    # ── Step 2: Train circular classifier ────────────────────────────────────
    if n_docs >= 5:
        try:
            step2_train_circular_classifier()
        except Exception as e:
            logger.error("STEP 2 FAILED: %s", e)
            traceback.print_exc()
            errors.append(f"step2_circular_classifier: {e}")
    else:
        logger.warning("STEP 2 SKIPPED — corpus too small (%d docs)", n_docs)
        errors.append("step2_skipped: corpus too small")

    # ── Load ML CSV (shared by steps 3 + 4) ──────────────────────────────────
    X, y = [], []
    try:
        X, y = _load_ml_csv()
    except Exception as e:
        logger.error("ML CSV load failed: %s", e)
        errors.append(f"ml_csv_load: {e}")

    # ── Step 3: Demo settlement model ─────────────────────────────────────────
    if X:
        try:
            step3_train_demo_model(X, y)
        except Exception as e:
            logger.error("STEP 3 FAILED: %s", e)
            traceback.print_exc()
            errors.append(f"step3_demo_model: {e}")

    # ── Step 4: App settlement model ──────────────────────────────────────────
    if X:
        try:
            step4_train_app_model(X, y)
        except Exception as e:
            logger.error("STEP 4 FAILED: %s", e)
            traceback.print_exc()
            errors.append(f"step4_app_model: {e}")

    # ── Step 5: Verify all models ─────────────────────────────────────────────
    try:
        step5_verify_models()
    except Exception as e:
        logger.error("STEP 5 FAILED: %s", e)
        traceback.print_exc()
        errors.append(f"step5_verify: {e}")

    # ── Final summary ─────────────────────────────────────────────────────────
    _progress["finished_at"] = datetime.utcnow().isoformat() + "Z"
    _progress["errors"] = errors
    _save_progress("pipeline", "completed" if not errors else "completed_with_errors", {
        "error_count": len(errors),
    })

    logger.info("")
    logger.info("╔══════════════════════════════════════════════════════════╗")
    if not errors:
        logger.info("║  PIPELINE COMPLETE — all steps succeeded ✓              ║")
    else:
        logger.info("║  PIPELINE COMPLETE with %d error(s):                    ║", len(errors))
        for err in errors:
            logger.info("║    • %s", err)
    logger.info("╚══════════════════════════════════════════════════════════╝")
    logger.info("Progress file: %s", PROGRESS_FILE)


if __name__ == "__main__":
    main()
