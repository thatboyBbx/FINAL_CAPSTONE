"""
run_corpus_loop.py
------------------
Loops build_corpus_resumable.py until all files are processed,
then runs run_training_pipeline.py for steps 2-5.
"""
import subprocess
import sys
import json
from pathlib import Path

BASE   = Path(__file__).resolve().parent
PYTHON = BASE / ".venv" / "Scripts" / "python.exe"
CORPUS_SCRIPT   = BASE / "build_corpus_resumable.py"
PIPELINE_SCRIPT = BASE / "run_training_pipeline.py"
STATE_PATH = BASE / "storage" / "datasets" / "app" / "corpus_state.json"

def get_progress():
    if STATE_PATH.exists():
        s = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return len(s["processed_paths"]), s["total_files"]
    return 0, 0

def main():
    print("=" * 60, flush=True)
    print("CORPUS LOOP: running batches until complete", flush=True)
    print("=" * 60, flush=True)

    batch = 0
    while True:
        batch += 1
        done, total = get_progress()
        if total and done >= total:
            print(f"\nALL FILES PROCESSED: {done}/{total}. Exiting loop.", flush=True)
            break

        print(f"\n--- Batch {batch} | Progress: {done}/{total} ---", flush=True)
        result = subprocess.run(
            [str(PYTHON), str(CORPUS_SCRIPT)],
            cwd=str(BASE),
        )
        if result.returncode != 0:
            print(f"ERROR: build_corpus_resumable.py exited with code {result.returncode}", flush=True)
            sys.exit(1)

        done, total = get_progress()
        print(f"  After batch {batch}: {done}/{total} ({int(done/total*100) if total else 0}%)", flush=True)
        if total and done >= total:
            print(f"\nALL FILES PROCESSED: {done}/{total}.", flush=True)
            break

    print("\n" + "=" * 60, flush=True)
    print("CORPUS COMPLETE. Starting training pipeline steps 2-5...", flush=True)
    print("=" * 60, flush=True)

    # Patch run_training_pipeline.py to skip step 1 by calling steps 2-5 directly
    # We invoke the functions directly rather than main() to skip step1_build_corpus
    pipeline_runner = BASE / "run_pipeline_steps_2_5.py"
    pipeline_runner.write_text(
        """
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
import run_training_pipeline as p

p.logger.info("Running steps 2-5 only (corpus already built)")

# Step 2
try:
    p.step2_train_circular_classifier()
except Exception as e:
    p.logger.error("STEP 2 FAILED: %s", e)
    import traceback; traceback.print_exc()

# Steps 3 & 4 — need ML CSV
X, y = [], []
try:
    X, y = p._load_ml_csv()
except Exception as e:
    p.logger.error("ML CSV load failed: %s", e)

if X:
    try:
        p.step3_train_demo_model(X, y)
    except Exception as e:
        p.logger.error("STEP 3 FAILED: %s", e)
        import traceback; traceback.print_exc()

    try:
        p.step4_train_app_model(X, y)
    except Exception as e:
        p.logger.error("STEP 4 FAILED: %s", e)
        import traceback; traceback.print_exc()

# Step 5
try:
    p.step5_verify_models()
except Exception as e:
    p.logger.error("STEP 5 FAILED: %s", e)
    import traceback; traceback.print_exc()

p.logger.info("Steps 2-5 complete.")
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(PYTHON), str(pipeline_runner)],
        cwd=str(BASE),
    )
    if result.returncode != 0:
        print(f"ERROR: pipeline steps 2-5 exited with code {result.returncode}", flush=True)
        sys.exit(1)

    print("\n" + "=" * 60, flush=True)
    print("FULL PIPELINE DONE.", flush=True)
    print("=" * 60, flush=True)

if __name__ == "__main__":
    main()
