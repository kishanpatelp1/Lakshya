"""Auth domain — email-OTP login, JWT session cookies, CSRF protection."""

from .routes import router as auth_router

__all__ = ["auth_router"]
