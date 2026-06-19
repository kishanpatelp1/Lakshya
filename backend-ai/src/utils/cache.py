"""Analysis response cache — 1-hour TTL.

Uses Redis when available (preferred), falls back to an in-process TTL dict
for local dev environments without Redis configured.

Cache keys are SHA-256 hashes of the serialised inputs so identical queries
for the same company/companies always return the stored response without
touching the LLM.
"""

import hashlib
import json
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_SENTINEL = object()


class AnalysisCache:
    """Thread-safe, TTL-aware cache for expensive AI analysis results."""

    DEFAULT_TTL = 3600  # 1 hour

    def __init__(self) -> None:
        self._redis: Any = None
        self._mem: dict[str, tuple[Any, float]] = {}
        self._try_connect_redis()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _try_connect_redis(self) -> None:
        try:
            from src.config import get_settings

            settings = get_settings()
            if not settings.redis_url:
                logger.debug("AnalysisCache: no Redis URL configured, using in-memory")
                return

            import redis as redis_lib

            client = redis_lib.from_url(settings.redis_url, decode_responses=True, socket_timeout=2)
            client.ping()
            self._redis = client
            logger.info("AnalysisCache: connected to Redis at %s", settings.redis_url)
        except Exception as exc:
            logger.info("AnalysisCache: Redis unavailable (%s) — using in-memory TTL cache", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def make_key(*parts: Any) -> str:
        """Produce a stable, opaque cache key from the given inputs.

        Inputs are JSON-serialised (sorted keys, str fallback for UUIDs etc.)
        then SHA-256'd.  The prefix ``analysis:`` keeps keys scoped.
        """
        raw = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
        digest = hashlib.sha256(raw.encode()).hexdigest()[:32]
        return f"analysis:{digest}"

    def get(self, key: str) -> Optional[Any]:
        """Return cached value or ``None`` if missing/expired."""
        if self._redis is not None:
            try:
                data = self._redis.get(key)
                if data is not None:
                    return json.loads(data)
                return None
            except Exception as exc:
                logger.warning("AnalysisCache Redis GET error: %s", exc)

        # In-memory fallback
        entry = self._mem.get(key)
        if entry is not None:
            value, expires_at = entry
            if time.monotonic() < expires_at:
                return value
            del self._mem[key]
        return None

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
        """Store *value* under *key* with the given TTL (seconds)."""
        if self._redis is not None:
            try:
                self._redis.setex(key, ttl, json.dumps(value, default=str, ensure_ascii=False))

                return
            except Exception as exc:
                logger.warning("AnalysisCache Redis SET error: %s", exc)

        # In-memory fallback — cap at 512 entries to prevent unbounded growth
        if len(self._mem) >= 512:
            oldest_key = next(iter(self._mem))
            del self._mem[oldest_key]
        self._mem[key] = (value, time.monotonic() + ttl)

    def invalidate(self, key: str) -> None:
        """Remove a single key from the cache."""
        if self._redis is not None:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        self._mem.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        """Remove all in-memory keys that start with *prefix*.

        For Redis, only works when the key scan is feasible (small keyspace).
        """
        if self._redis is not None:
            try:
                keys = self._redis.keys(f"{prefix}*")
                if keys:
                    self._redis.delete(*keys)
            except Exception:
                pass
        for k in list(self._mem.keys()):
            if k.startswith(prefix):
                del self._mem[k]


# ---------------------------------------------------------------------------
# Module-level singleton — import and use directly
# ---------------------------------------------------------------------------

_instance: Optional[AnalysisCache] = None


def get_analysis_cache() -> AnalysisCache:
    """Return the process-wide AnalysisCache singleton (lazy init)."""
    global _instance
    if _instance is None:
        _instance = AnalysisCache()
    return _instance
