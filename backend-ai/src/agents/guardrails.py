"""Guardrails for the chat agent: input validation, prompt-injection defence,
per-user rate limiting, and output grounding.

Kept deliberately lightweight and dependency-free (Redis when available, with an
in-process fallback) so it can wrap both the blocking and streaming chat paths.
"""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from typing import Any, Optional

from src.config import get_settings

logger = logging.getLogger(__name__)

# ── Tunables ──────────────────────────────────────────────────────────────
MAX_QUERY_CHARS = 2000
RATE_LIMIT_MAX_REQUESTS = 20
RATE_LIMIT_WINDOW_SECONDS = 60

# High-confidence prompt-injection markers. Kept tight to avoid blocking
# legitimate finance questions — these phrasings have no place in an equity query.
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(the\s+)?(previous|prior|above|earlier)\s+instructions", re.I),
    re.compile(r"disregard\s+(all\s+)?(the\s+)?(previous|prior|above|system)", re.I),
    re.compile(r"reveal\s+(your\s+)?(system\s+)?(prompt|instructions)", re.I),
    re.compile(r"(what('| i)s|show me|print)\s+your\s+(system\s+)?(prompt|instructions)", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an|in)\b", re.I),
    re.compile(r"\b(developer|dan)\s+mode\b", re.I),
    re.compile(r"\bjailbreak\b", re.I),
]

_DISCLAIMER = (
    "\n\n---\n*AI-generated research for informational purposes only — not "
    "investment advice. Verify figures against primary sources before acting.*"
)

# Strip the internal context block the pipeline injects, if it ever leaks through.
_CONTEXT_LEAK = re.compile(r"\n*\[Context:[^\]]*\]", re.S)


class GuardrailError(Exception):
    """Raised when a request is blocked by a guardrail. ``status`` maps to HTTP."""

    def __init__(self, detail: str, status: int = 400, retry_after: Optional[int] = None):
        super().__init__(detail)
        self.detail = detail
        self.status = status
        self.retry_after = retry_after


def validate_input(query: str) -> None:
    """Validate a user query. Raises ``GuardrailError`` if it must be blocked."""
    if not query or not query.strip():
        raise GuardrailError("Query must not be empty.")
    if len(query) > MAX_QUERY_CHARS:
        raise GuardrailError(f"Query too long (>{MAX_QUERY_CHARS} characters).")
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(query):
            logger.warning("Blocked prompt-injection attempt: %s", query[:120])
            raise GuardrailError("Query rejected: it looks like a prompt-injection attempt.")


def apply_output_guardrail(text: str) -> str:
    """Ground the model output: strip leaked context and append a disclaimer."""
    if not text:
        return text
    cleaned = _CONTEXT_LEAK.sub("", text).rstrip()
    if "not investment advice" not in cleaned.lower():
        cleaned += _DISCLAIMER
    return cleaned


# ── Rate limiting (Redis sliding window, in-process fallback) ──────────────

_redis: Any = None
_redis_tried = False
_local_hits: dict[str, deque] = {}


def _get_redis():
    global _redis, _redis_tried
    if _redis_tried:
        return _redis
    _redis_tried = True
    try:
        settings = get_settings()
        if settings.redis_url:
            import redis as redis_lib

            client = redis_lib.from_url(settings.redis_url, decode_responses=True, socket_timeout=2)
            client.ping()
            _redis = client
    except Exception as e:
        logger.debug("Rate limiter: Redis unavailable, using in-process fallback: %s", e)
        _redis = None
    return _redis


def check_rate_limit(user_id: str) -> None:
    """Enforce a per-user sliding-window limit. Raises ``GuardrailError`` (429)."""
    now = time.time()
    window = RATE_LIMIT_WINDOW_SECONDS
    limit = RATE_LIMIT_MAX_REQUESTS
    client = _get_redis()

    if client is not None:
        key = f"ratelimit:chat:{user_id}"
        try:
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zadd(key, {f"{now}": now})
            pipe.zcard(key)
            pipe.expire(key, window)
            count = pipe.execute()[2]
            if count > limit:
                raise GuardrailError(
                    "Rate limit exceeded. Please slow down.", status=429, retry_after=window
                )
            return
        except GuardrailError:
            raise
        except Exception as e:  # Redis hiccup -> fail open to the local limiter
            logger.debug("Rate limiter Redis error, falling back to local: %s", e)

    hits = _local_hits.setdefault(user_id, deque())
    while hits and hits[0] <= now - window:
        hits.popleft()
    if len(hits) >= limit:
        raise GuardrailError("Rate limit exceeded. Please slow down.", status=429, retry_after=window)
    hits.append(now)
