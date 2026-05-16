"""
app/core/config.py
==================
Centralised application settings, loaded once from the .env file.

SECRET_KEY note:
  Development uses a fixed fallback so JWTs survive server restarts.
  Production MUST set SECRET_KEY in .env to a real random value.
  The app refuses to start in production with the dev fallback.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, model_validator

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

# Fixed dev-only fallback — stable across restarts, never used in production
_DEV_FALLBACK_KEY = (
    "insure-intel-dev-only-secret-key-do-not-use-in-production-minimum64chars!!"
)


class Settings(BaseModel):
    model_config = ConfigDict(extra="allow")

    app_name: str = os.getenv("APP_NAME", "Insurance Documents Intelligence Platform")
    env: str = os.getenv("ENV", "dev")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    api_base: str = os.getenv("API_BASE", "http://127.0.0.1:8000")
    model_storage_dir: str = os.getenv("MODEL_STORAGE_DIR", "app/storage/models")

    # JWT
    secret_key: str = os.getenv("SECRET_KEY", _DEV_FALLBACK_KEY)
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )

    # Storage paths
    demo_dataset_dir: str = os.getenv("DEMO_DATASET_DIR", "storage/datasets/demo")
    app_dataset_dir: str = os.getenv("APP_DATASET_DIR", "storage/datasets/app")
    demo_model_dir: str = os.getenv("DEMO_MODEL_DIR", "storage/models/demo")
    app_model_dir: str = os.getenv("APP_MODEL_DIR", "storage/models/app")

    # LLM — intentionally empty; chatbot uses offline engine (see Job C)
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    @model_validator(mode="after")
    def _block_dev_key_in_production(self) -> "Settings":
        """Refuse to start in production with the insecure dev fallback key."""
        if self.env == "production" and self.secret_key == _DEV_FALLBACK_KEY:
            raise ValueError(
                "SECRET_KEY must be set to a secure random value in production. "
                "Generate one with: openssl rand -hex 32"
            )
        return self


settings = Settings()
