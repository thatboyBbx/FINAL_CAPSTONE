import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[2]  # app/
MODELS_DIR = BASE_DIR / "storage" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_PROFILES = {"demo", "app"}


def _assert_profile(profile: str) -> None:
    if profile not in ALLOWED_PROFILES:
        raise ValueError("profile must be 'demo' or 'app'")


def profile_dir(profile: str) -> Path:
    _assert_profile(profile)
    p = (MODELS_DIR / profile).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def model_path(profile: str) -> Path:
    return profile_dir(profile) / "model.joblib"


def meta_path(profile: str) -> Path:
    return profile_dir(profile) / "meta.json"


def save_meta(profile: str, feature_names: list[str], metrics: dict, label_source: str, model_label: str) -> dict:
    meta = {
        "profile": profile,
        "model_label": model_label,       # <- your explicit human-readable label
        "label_source": label_source,     # proxy vs real
        "model_path": str(model_path(profile)),
        "feature_names": feature_names,
        "metrics": metrics,
        "saved_at": datetime.utcnow().isoformat() + "Z",
    }
    with open(meta_path(profile), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return meta


def load_meta(profile: str) -> dict | None:
    _assert_profile(profile)
    p = meta_path(profile)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)
