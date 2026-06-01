"""
alembic/env.py — Alembic migration environment for InsureIntel Zimbabwe.

Import order matters:
  1. app.core.db (Base, engine) must come first
  2. All model modules must be imported before target_metadata is referenced
     so that SQLAlchemy knows about every table for autogenerate to work
"""
from __future__ import annotations

import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# ─── Project imports ─────────────────────────────────────────────────────────
from app.core.db import Base  # noqa: E402

# Import all models so their tables are visible to Alembic autogenerate
import app.modules.insurers.model          # noqa: F401
import app.modules.insurers.claims_model   # noqa: F401
import app.modules.insurers.scrape_model   # noqa: F401
import app.modules.financials.model        # noqa: F401
import app.modules.news.model              # noqa: F401
import app.modules.qa.model                # noqa: F401
import app.modules.comparison.model        # noqa: F401
import app.modules.feedback.model          # noqa: F401
import app.modules.deviation.model         # noqa: F401
import app.modules.batch.model             # noqa: F401
import app.modules.tracker.model           # noqa: F401
import app.modules.audit.model             # noqa: F401
import app.modules.multilingual.model      # noqa: F401
import app.modules.documents.model         # noqa: F401
import app.modules.users.model             # noqa: F401
import app.modules.circulars.model         # noqa: F401
import app.modules.intel.model             # noqa: F401
import app.modules.csp.model               # noqa: F401
import app.modules.clients.model           # noqa: F401
import app.modules.compliance.model        # noqa: F401

target_metadata = Base.metadata


def _use_batch_mode(url: str) -> bool:
    """
    render_as_batch is required for SQLite (which cannot ALTER columns directly).
    PostgreSQL supports full ALTER TABLE, so batch mode must be off — it wraps
    statements in a table-copy approach that breaks PostgreSQL-specific DDL.
    """
    return url.startswith("sqlite")


# ─── Migration runners ────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL script)."""
    from app.core.config import settings

    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_use_batch_mode(url),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    from app.core.db import engine

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=(connection.dialect.name == "sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
