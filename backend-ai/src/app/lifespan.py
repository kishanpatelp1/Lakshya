"""Application lifespan and startup tasks."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from src.db.database import init_db

logger = logging.getLogger(__name__)


def _bootstrap_universe() -> None:
    """Background-thread helper: sync stock universe if DB is empty."""
    from sqlalchemy import func

    from src.db.database import SessionLocal
    from src.db.models import Company

    db = SessionLocal()
    try:
        count = db.query(func.count(Company.id)).scalar() or 0
        if count < 100:
            logger.info("Database has only %d companies — triggering universe sync …", count)
            from src.services.stock_universe import StockUniverseService

            svc = StockUniverseService(db)
            stats = svc.sync_full_universe()
            logger.info("Startup universe sync complete: %s", stats)
        else:
            logger.info("Database already has %d companies, skipping startup sync.", count)
    except Exception as e:
        logger.warning("Startup universe sync failed (non-fatal): %s", e)
    finally:
        db.close()


@asynccontextmanager
async def app_lifespan(_app):
    """Application startup/shutdown lifespan context."""
    # Start services: docker-compose up -d postgres redis qdrant
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as db_err:
        logger.error("Database unavailable at startup — running in degraded mode: %s", db_err)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _bootstrap_universe)

    yield
