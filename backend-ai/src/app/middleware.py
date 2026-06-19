"""Shared middleware registration."""

import logging
import time
import os
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.utils.request_context import clear_request_context, set_request_id
from src.config import get_settings

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach correlation IDs and isolate request-scoped context."""

    async def dispatch(self, request: Request, call_next):
        clear_request_context()
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        set_request_id(request_id)
        request.state.request_id = request_id

        started = time.perf_counter()
        logger.info("request-start request_id=%s path=%s", request_id, request.url.path)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                "request-end request_id=%s path=%s duration_ms=%s",
                request_id,
                request.url.path,
                elapsed_ms,
            )
            clear_request_context()


class AuthorizationMiddleware(BaseHTTPMiddleware):
    """Enforce that the session user only touches their own data.

    Closes the IDOR gap: endpoints historically trusted a ``user_id`` from the
    query string / JSON body / path. This middleware decodes the JWT access
    cookie and rejects any request whose ``user_id`` doesn't match the session.

    Rules:
    - ``/auth/*``, health/docs, and public market-data endpoints stay open.
    - Requests under PROTECTED_PREFIXES require a valid session.
    - Any request carrying a ``user_id`` (query, JSON body, or ``/users/{id}``
      path) must have a session whose subject matches it.
    """

    PROTECTED_PREFIXES = ("/portfolios", "/watchlists", "/simulator", "/users", "/chat")
    EXEMPT_PREFIXES = ("/auth", "/health", "/docs", "/openapi", "/redoc", "/api/v1/status")

    @staticmethod
    def _session_user(request: Request) -> str | None:
        token = request.cookies.get("access_token")
        if not token:
            return None
        try:
            import jwt as _jwt

            from src.config import get_settings

            s = get_settings()
            payload = _jwt.decode(token, s.jwt_secret_key, algorithms=[s.jwt_algorithm])
            if payload.get("type") != "access":
                return None
            return payload.get("sub")
        except Exception:
            return None

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or path == "/" or path.startswith(self.EXEMPT_PREFIXES):
            return await call_next(request)

        session_user = self._session_user(request)

        # Collect any user_id claims on the request.
        claimed: set[str] = set()
        qid = request.query_params.get("user_id")
        if qid:
            claimed.add(qid)
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "users":
            claimed.add(parts[1])
        # NOTE: reading the request body in BaseHTTPMiddleware breaks downstream
        # StreamingResponse (SSE) — so skip body inspection on streaming paths.
        # Those endpoints are still session-gated by the protected-prefix check.
        is_streaming = path.endswith("/stream") or "stream" in path.rsplit("/", 1)[-1]
        if (
            not is_streaming
            and request.method in ("POST", "PUT", "PATCH")
            and "json" in (request.headers.get("content-type") or "")
        ):
            body = await request.body()
            if body:
                try:
                    import json as _json

                    data = _json.loads(body)
                    if isinstance(data, dict) and data.get("user_id"):
                        claimed.add(str(data["user_id"]))
                except Exception:
                    pass

                # Re-inject the consumed body for downstream handlers.
                async def receive():
                    return {"type": "http.request", "body": body}

                request._receive = receive  # noqa: SLF001

        protected = path.startswith(self.PROTECTED_PREFIXES)
        if (protected or claimed) and not session_user:
            return Response(
                content='{"detail":"Not authenticated"}',
                status_code=401,
                media_type="application/json",
            )
        if claimed and any(c != session_user for c in claimed):
            return Response(
                content='{"detail":"Forbidden: user mismatch"}',
                status_code=403,
                media_type="application/json",
            )
        return await call_next(request)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Validate CSRF double-submit cookie on mutating requests."""

    EXEMPT_PATHS = {
        "/auth/send-otp",
        "/auth/verify-otp",
        "/auth/register",
        "/auth/login",
        "/auth/demo",
        "/auth/refresh",
        "/health",
        "/",
        "/api/v1/status",
    }

    async def dispatch(self, request: Request, call_next):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        path = request.url.path
        if path in self.EXEMPT_PATHS or path.startswith("/uploads"):
            return await call_next(request)

        cookie_token = request.cookies.get("csrf_token")
        header_token = request.headers.get("x-csrf-token")

        if not cookie_token or not header_token:
            return Response(
                content='{"detail":"Missing CSRF token"}',
                status_code=403,
                media_type="application/json",
            )

        import secrets

        if not secrets.compare_digest(cookie_token, header_token):
            return Response(
                content='{"detail":"Invalid CSRF token"}',
                status_code=403,
                media_type="application/json",
            )

        return await call_next(request)


def register_middleware(app: FastAPI) -> None:
    """Attach middleware stack to the FastAPI app."""
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(AuthorizationMiddleware)
    app.add_middleware(CSRFMiddleware)

    allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

    if os.getenv("APP_ENV") == "development":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://localhost:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
