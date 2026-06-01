"""
generate_all_production_data.py
================================
Master runner — generates all production datasets for InsureIntel Zimbabwe.

Run from the EXPERIMENT directory:
    python scripts/generate_all_production_data.py

This script orchestrates all individual generators and produces a summary report.
Output directory: storage/datasets/production/

Datasets generated:
  1. document_classifier_training.json   — 540 samples, 9 categories
  2. document_classifier_training.csv    — same data, CSV format
  3. financial_forecaster_timeseries.csv — 83 insurers × 20 quarters = 1,660 rows
  4. csp_xgboost_fsr1_ratios.csv         — 600 rows (450 healthy / 150 at-risk)
  5. settlement_risk_app_financials.csv  — 83 insurer feature vectors (app mode)
  6. insurer_risk_labels.csv             — 83 rows: insurer_id, label (0/1/2)
  7. standard_clauses_library.json       — 60+ standard insurance clauses

Requirements: Python 3.9+ standard library only (no external packages needed)
"""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent


def _run_module(script_name: str) -> float:
    """Dynamically import and run a generator script's main() function."""
    script_path = SCRIPTS_DIR / script_name
    spec = importlib.util.spec_from_file_location(
        script_name.replace(".py", "").replace("-", "_"),
        script_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {script_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod

    t0 = time.time()
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    if hasattr(mod, "main"):
        mod.main()
    return time.time() - t0


def main() -> None:
    print("=" * 65)
    print("  InsureIntel Zimbabwe — Production Dataset Generator")
    print("=" * 65)
    print()

    generators = [
        ("gen_document_training.py",   "Document Classifier Training Data (9 categories, 540+ samples)"),
        ("gen_financial_timeseries.py", "Financial Forecaster Time Series (83 insurers × 20 quarters)"),
        ("gen_csp_fsr1.py",            "CSP XGBoost FSR-1 Solvency Dataset (600 rows, 75/25 split)"),
        ("gen_settlement_risk.py",     "Settlement Risk Classifier Datasets (features + labels CSV)"),
        ("gen_standard_clauses.py",    "Standard Clauses Knowledge Base (60+ clauses, 10 types)"),
    ]

    total_elapsed = 0.0
    results = []
    for script, description in generators:
        print(f"\n{'─' * 65}")
        print(f"  {description}")
        print(f"{'─' * 65}")
        try:
            elapsed = _run_module(script)
            total_elapsed += elapsed
            results.append((description, "✓ OK", f"{elapsed:.1f}s"))
        except Exception as exc:
            print(f"  ERROR: {exc}")
            results.append((description, "✗ FAILED", str(exc)))

    # Summary
    print(f"\n{'=' * 65}")
    print("  GENERATION SUMMARY")
    print(f"{'=' * 65}")
    for desc, status, detail in results:
        print(f"  {status}  {desc}")
        if status != "✓ OK":
            print(f"       Detail: {detail}")

    out_dir = Path("storage/datasets/production")
    if out_dir.exists():
        files = sorted(out_dir.glob("*"))
        print(f"\nOutput files in {out_dir.resolve()}:")
        for f in files:
            size_kb = f.stat().st_size / 1024
            print(f"  {f.name:<55} {size_kb:>8.1f} KB")

    print(f"\nTotal time: {total_elapsed:.1f}s")
    print("\nNext steps:")
    print("  1. Copy insurer_risk_labels.csv to storage/datasets/production/ (already done)")
    print("  2. Start the app and seed the DB:")
    print("     POST /api/insurers/seed")
    print("     POST /api/financials/seed")
    print("  3. Train the Financial Forecaster:")
    print("     POST /api/ml/train-forecaster")
    print("  4. Train the Settlement Risk Classifier (app mode):")
    print("     POST /api/ml/train?profile=app&labels_csv_path=storage/datasets/production/insurer_risk_labels.csv")
    print("  5. Train the CSP XGBoost model:")
    print("     python -m app.ai.training.csp_training_pipeline")
    print("  6. Load standard clauses into the database:")
    print("     POST /api/deviation/seed-knowledge-base")
    print("  7. Retrain the Document Classifier with the expanded dataset:")
    print("     POST /api/documents/retrain")
    print()


if __name__ == "__main__":
    main()
