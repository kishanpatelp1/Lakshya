"""Async MongoDB client using Motor. Connection is lazy — initialized on first use."""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_mongo_db = None


def get_mongo_db():
    """Return the Motor database handle, or None if MONGODB_URI is not configured."""
    global _mongo_db
    if _mongo_db is not None:
        return _mongo_db

    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        return None

    try:
        from motor.motor_asyncio import AsyncIOMotorClient

        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        db_name = os.getenv("MONGODB_DB", "equity_research")
        _mongo_db = client[db_name]
        logger.info("MongoDB connected to database '%s'", db_name)
    except Exception as exc:
        logger.warning("MongoDB unavailable: %s", exc)
        return None

    return _mongo_db
