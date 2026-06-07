"""Database connection and session management."""

import logging
from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.config import get_settings

logger = logging.getLogger(__name__)

Base: Any = declarative_base()

_engine = None
_SessionLocal = None


def _get_engine():
    """Lazy-init the database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            echo=settings.debug,
        )
    return _engine


def _get_session_factory():
    """Lazy-init the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=_get_engine()
        )
    return _SessionLocal


def SessionLocal() -> Session:
    """Public session factory for use outside of FastAPI dependency injection (ETL tasks, scripts)."""
    factory = _get_session_factory()
    return factory()


def _migrate_add_columns(engine) -> None:
    """Add missing columns to existing tables (lightweight schema migration)."""
    migrations: list[tuple[str, str, str]] = [
        ("users", "phone_number", "VARCHAR(15)"),
        ("users", "date_of_birth", "DATE"),
        ("users", "address", "TEXT"),
        ("users", "pan_card_number", "VARCHAR(10)"),
        ("users", "aadhaar_number", "VARCHAR(12)"),
        ("users", "profile_pic_url", "TEXT"),
        ("users", "kyc_status", "VARCHAR(20) DEFAULT 'not_started'"),
        ("users", "kyc_submitted_at", "TIMESTAMP"),
    ]
    with engine.connect() as conn:
        for table, column, col_type in migrations:
            try:
                conn.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {col_type}"
                ))
            except Exception as exc:
                logger.debug("Migration skip %s.%s: %s", table, column, exc)
        conn.commit()


def init_db() -> None:
    """Initialize database (create tables if not exist, then migrate columns)."""
    from src.db import models  # noqa: F401 - Import to register models

    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
    _migrate_add_columns(engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI: yield database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
