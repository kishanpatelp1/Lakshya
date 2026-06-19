"""CSRF double-submit cookie protection.

The frontend reads the `csrf_token` cookie (NOT HttpOnly) and sends it back
as the `X-CSRF-Token` header on mutating requests.  The backend verifies they
match.
"""

import secrets
from typing import Set

from fastapi import Request, Response

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
CSRF_SECRET = secrets.token_hex(32)

PATHS_EXEMPT_FROM_CSRF: Set[str] = {
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


def set_csrf_cookie(response: Response) -> None:
    """Set the CSRF token cookie on a response.

    Uses the same secure/samesite policy as the session cookies so it is
    reliably set on both localhost (http) and cross-domain production.
    """
    from src.config import get_settings

    settings = get_settings()
    token = secrets.token_hex(32)
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        max_age=604800,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
        domain=settings.cookie_domain,
    )


def validate_csrf(request: Request) -> bool:
    """Validate that the X-CSRF-Token header matches the csrf_token cookie."""
    path = request.url.path

    if request.method in ("GET", "HEAD", "OPTIONS"):
        return True

    if path in PATHS_EXEMPT_FROM_CSRF:
        return True

    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)

    if not cookie_token or not header_token:
        return False

    return secrets.compare_digest(cookie_token, header_token)
