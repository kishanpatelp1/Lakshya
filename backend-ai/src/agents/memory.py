"""Persistent memory for the LangGraph research pipeline.

Provides a Postgres-backed checkpointer (conversation continuity across restarts
and workers) and store (long-term ``/memories/``), with in-memory fallbacks when
Postgres is unavailable. Both share one psycopg3 connection pool.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from src.config import get_settings

logger = logging.getLogger(__name__)

_store: Any = None
_checkpointer: Any = None
_pool: Any = None


def _pg_conninfo() -> str | None:
    """Return a psycopg3-compatible connection string, or None if unset."""
    url = get_settings().database_url
    if not url:
        return None
    # psycopg3 wants a bare postgresql:// URL, not a SQLAlchemy driver form.
    return url.replace("postgresql+psycopg2://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )


def _get_pool():
    """Return a shared psycopg3 connection pool for the checkpointer + store.

    ``autocommit`` and ``dict_row`` are required by langgraph's Postgres
    backends; ``prepare_threshold=0`` keeps it compatible with poolers.
    Returns None (callers fall back to in-memory) if a pool can't be opened.
    """
    global _pool
    if _pool is not None:
        return _pool
    conninfo = _pg_conninfo()
    if not conninfo:
        return None
    try:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        pool = ConnectionPool(
            conninfo=conninfo,
            max_size=20,
            kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": 0},
            open=True,
        )
        pool.wait(timeout=5.0)
        _pool = pool
    except Exception as e:
        logger.warning("Postgres connection pool unavailable (%s); using in-memory backends", e)
        _pool = None
    return _pool


def _get_store():
    """Return a singleton long-term-memory store (Postgres-backed, in-memory fallback)."""
    global _store
    if _store is None:
        pool = _get_pool()
        if pool is not None:
            try:
                from langgraph.store.postgres import PostgresStore

                store = PostgresStore(pool)
                store.setup()
                _store = store
                logger.info("Using PostgresStore for long-term memory")
            except Exception as e:
                logger.warning("PostgresStore unavailable (%s), falling back to InMemoryStore", e)
                _store = InMemoryStore()
        else:
            _store = InMemoryStore()
            logger.info("Using InMemoryStore for long-term memory (no Postgres pool)")
    return _store


def _get_checkpointer():
    """Return a singleton checkpointer for conversation continuity.

    Prefers a Postgres-backed checkpointer so session threads survive restarts
    and are shared across workers; falls back to in-process ``MemorySaver``.
    """
    global _checkpointer
    if _checkpointer is None:
        pool = _get_pool()
        if pool is not None:
            try:
                from langgraph.checkpoint.postgres import PostgresSaver

                saver = PostgresSaver(pool)
                saver.setup()
                _checkpointer = saver
                logger.info("Using PostgresSaver checkpointer for session continuity")
            except Exception as e:
                logger.warning("PostgresSaver unavailable (%s), falling back to MemorySaver", e)
                _checkpointer = MemorySaver()
        else:
            _checkpointer = MemorySaver()
            logger.info("Using in-memory MemorySaver checkpointer (no Postgres pool)")
    return _checkpointer


def get_memory_config() -> dict[str, Any]:
    """Return ``{store, checkpointer}`` for compiling the LangGraph pipeline."""
    return {"store": _get_store(), "checkpointer": _get_checkpointer()}
