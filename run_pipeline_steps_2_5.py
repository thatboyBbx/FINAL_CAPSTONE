
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
