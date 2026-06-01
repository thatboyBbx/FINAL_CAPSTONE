"""
app/core/db.py
==============
SQLAlchemy engine, session factory, and declarative base.

Supports SQLite (development) and PostgreSQL (staging/production) transparently.

- SQLite: single StaticPool connection, FK pragma enabled per-connection.
- PostgreSQL: QueuePool with pre-ping, configurable size/overflow/recycle.
- get_db(): FastAPI dependency — yields a session with explicit rollback on error.
- validate_db_connection(): call once at startup to confirm the DB is reachable.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

# ── Engine ────────────────────────────────────────────────────────────────────

if _is_sqlite:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        """
        Apply per-connection pragmas for FK enforcement and write concurrency.

        - foreign_keys=ON: enforce FK constraints (SQLite default is OFF).
        - journal_mode=WAL: readers and writers do not block each other; multiple
          workers + API can commit without serialising on the journal file.
        - synchronous=NORMAL: WAL-safe durability with much lower fsync cost.
        - busy_timeout=5000: when the writer lock is held, wait up to 5s before
          raising "database is locked" — eliminates spurious errors under burst load.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

else:
    engine = create_engine(
        settings.database_url,
        future=True,
        # Validate stale connections before handing them to a request
        pool_pre_ping=True,
        # Pool sizing — tune via DB_POOL_SIZE / DB_MAX_OVERFLOW env vars
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        # Drop idle connections after 30 minutes (keeps DB server tidy)
        pool_recycle=settings.db_pool_recycle,
        # Raise after this many seconds if no connection is available
        pool_timeout=settings.db_pool_timeout,
    )

# ── Session factory ───────────────────────────────────────────────────────────

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)

# ── Declarative base ──────────────────────────────────────────────────────────

Base = declarative_base()

# ── FastAPI dependency ────────────────────────────────────────────────────────


def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session for the duration of a request.

    Rolls back explicitly on any unhandled exception so the connection is
    returned to the pool in a clean state regardless of what the caller did.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── Startup validation ────────────────────────────────────────────────────────


@contextmanager
def session_scope() -> Iterator[Session]:
    """
    Provide a transactional session for background jobs and manual DB access.

    FastAPI request handlers should keep using get_db(); this helper is for
    code paths that create their own session outside dependency injection.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def validate_db_connection() -> None:
    """
    Confirm the database is reachable.  Call once at application startup.

    Raises sqlalchemy.exc.OperationalError (or similar) if the DB is down,
    so the process exits with a clear error instead of failing on the first
    request.
    """
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
