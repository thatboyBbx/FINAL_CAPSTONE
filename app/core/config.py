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

    # Connection pool — ignored for SQLite, applied for PostgreSQL
    db_pool_size: int = int(os.getenv("DB_POOL_SIZE", "5"))
    db_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    db_pool_timeout: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    db_pool_recycle: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))

    # JWT — access tokens
    secret_key: str = os.getenv("SECRET_KEY", _DEV_FALLBACK_KEY)
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )

    # JWT — refresh tokens
    refresh_token_expire_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # Cookies — secure flag auto-resolves to True in production if not explicitly set
    cookie_secure: bool = False

    # Rate limits (slowapi format: "N/period")
    rate_limit_login: str = os.getenv("RATE_LIMIT_LOGIN", "5/minute")
    rate_limit_register: str = os.getenv("RATE_LIMIT_REGISTER", "10/minute")

    # Per-staff_id lockout (defends against distributed credential stuffing where
    # IP-based slowapi limits are not enough). N failures within the window =
    # lockout for the same window length.
    auth_lockout_max_failures: int = int(os.getenv("AUTH_LOCKOUT_MAX_FAILURES", "10"))
    auth_lockout_window_seconds: int = int(os.getenv("AUTH_LOCKOUT_WINDOW_SECONDS", "900"))

    # In-process TTL cache for JWT JTI blacklist lookups (seconds). Blacklist
    # additions are rare so eventual consistency within this window is fine.
    jti_blacklist_cache_ttl_seconds: int = int(os.getenv("JTI_BLACKLIST_CACHE_TTL_SECONDS", "60"))

    # Trusted reverse-proxy IPs for X-Forwarded-For (comma-separated)
    trusted_proxy_ips: str = os.getenv("TRUSTED_PROXY_IPS", "127.0.0.1,::1")

    # Storage paths
    demo_dataset_dir: str = os.getenv("DEMO_DATASET_DIR", "storage/datasets/demo")
    app_dataset_dir: str = os.getenv("APP_DATASET_DIR", "storage/datasets/app")
    demo_model_dir: str = os.getenv("DEMO_MODEL_DIR", "storage/models/demo")
    app_model_dir: str = os.getenv("APP_MODEL_DIR", "storage/models/app")

    # LLM — intentionally empty; chatbot uses offline engine (see Job C)
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # ── Async job queue ───────────────────────────────────────────────────────
    # queue_backend: "sqlite" (default, no Redis required) | "arq" (Redis-backed)
    queue_backend: str = os.getenv("QUEUE_BACKEND", "sqlite")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Worker concurrency targets (used in deployment docs and future supervisor config)
    ocr_worker_count: int = int(os.getenv("OCR_WORKER_COUNT", "2"))
    ingestion_worker_count: int = int(os.getenv("INGESTION_WORKER_COUNT", "4"))
    embedding_worker_count: int = int(os.getenv("EMBEDDING_WORKER_COUNT", "1"))

    # Retry policy
    job_max_attempts: int = int(os.getenv("JOB_MAX_ATTEMPTS", "3"))
    job_retry_backoff_base_seconds: int = int(os.getenv("JOB_RETRY_BACKOFF_BASE_SECONDS", "15"))
    # Absolute cap on retry delay so a misconfigured max_attempts cannot push
    # retries into the next day. base * 2^(attempt-1) is clamped to this.
    job_retry_backoff_max_seconds: int = int(os.getenv("JOB_RETRY_BACKOFF_MAX_SECONDS", "1800"))
    # A claimed/processing job whose claimed_at is older than
    # stuck_job_timeout_multiplier * job_timeout_seconds is considered abandoned
    # by a dead worker and is reset back to queued by the janitor.
    stuck_job_timeout_multiplier: int = int(os.getenv("STUCK_JOB_TIMEOUT_MULTIPLIER", "2"))
    # How often the worker runs the stuck-job janitor (seconds).
    stuck_job_reclaim_interval_seconds: int = int(os.getenv("STUCK_JOB_RECLAIM_INTERVAL_SECONDS", "60"))

    # Memory limits per worker type (MB); 0 = disabled
    ocr_worker_max_rss_mb: int = int(os.getenv("OCR_WORKER_MAX_RSS_MB", "800"))
    ingestion_worker_max_rss_mb: int = int(os.getenv("INGESTION_WORKER_MAX_RSS_MB", "600"))
    embedding_worker_max_rss_mb: int = int(os.getenv("EMBEDDING_WORKER_MAX_RSS_MB", "0"))

    # Per-job timeout in seconds; 0 = disabled (worker blocks until job completes)
    job_timeout_seconds: int = int(os.getenv("JOB_TIMEOUT_SECONDS", "300"))

    # Reject documents larger than this before loading pdfplumber/spaCy; 0 = no limit
    max_document_size_mb: int = int(os.getenv("MAX_DOCUMENT_SIZE_MB", "50"))

    # Embedding
    embedding_model_name: str = os.getenv(
        "EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"
    )
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
    embedding_version: str = os.getenv("EMBEDDING_VERSION", "v1")

    # RAG chunking
    rag_chunk_size: int = int(os.getenv("RAG_CHUNK_SIZE", "400"))
    rag_chunk_overlap: int = int(os.getenv("RAG_CHUNK_OVERLAP", "80"))

    # RAG governance
    rag_min_confidence: float = float(os.getenv("RAG_MIN_CONFIDENCE", "0.30"))
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "5"))

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        """Refuse to start in production with insecure defaults."""
        if self.env == "production":
            if self.secret_key == _DEV_FALLBACK_KEY:
                raise ValueError(
                    "SECRET_KEY must be set to a secure random value in production. "
                    "Generate one with: openssl rand -hex 32"
                )
            if self.database_url.startswith("sqlite"):
                raise ValueError(
                    "SQLite is not supported in production. "
                    "Set DATABASE_URL to a PostgreSQL connection string, e.g. "
                    "postgresql://user:password@host:5432/dbname"
                )

        # cookie_secure: True in production unless caller explicitly overrides
        if os.getenv("COOKIE_SECURE") is None:
            self.cookie_secure = self.env == "production"
        else:
            self.cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() not in (
                "false", "0", "no"
            )

        return self


settings = Settings()
