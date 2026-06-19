"""FastAPI application factory."""

import os
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from src.app.lifespan import app_lifespan
from src.app.telemetry import instrument_fastapi
from src.app.middleware import register_middleware
from src.app.routers import register_routers
from src.config import get_settings


class ForceCORSHeadersMiddleware(BaseHTTPMiddleware):
    """Force CORS headers on all responses - runs AFTER other middleware."""

    async def dispatch(self, request, call_next):
        origin = request.headers.get("origin", "")
        allowed_origins = os.getenv("ALLOWED_ORIGINS", "https://frontend-six-lac-70.vercel.app").split(",")
        
        # Handle preflight OPTIONS request directly
        if request.method == "OPTIONS":
            if origin in allowed_origins or "*" in allowed_origins:
                return Response(
                    status_code=200,
                    headers={
                        "Access-Control-Allow-Origin": origin if origin else allowed_origins[0],
                        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Request-ID, X-CSRF-Token, ngrok-skip-browser-warning",
                        "Access-Control-Allow-Credentials": "true",
                        "Access-Control-Max-Age": "3600",
                    },
                )
        
        response = await call_next(request)
        
        if origin in allowed_origins or "*" in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin if origin else allowed_origins[0]
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Request-ID, X-CSRF-Token, ngrok-skip-browser-warning"
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Lakshya",
        description="Backend-only AI-native equity research system for Indian equities.",
        version="0.2.0",
        lifespan=app_lifespan,
    )

    register_middleware(app)
    app.add_middleware(ForceCORSHeadersMiddleware)
    register_routers(app)
    if settings.observability_enabled or settings.otel_exporter_otlp_endpoint:
        instrument_fastapi(app)

    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

    @app.get("/")
    def root():
        """Root status endpoint."""
        return {"status": "ok", "service": "lakshya-research", "version": "0.2.0"}

    @app.get("/health")
    def health():
        """Health endpoint for load balancers."""
        return {"status": "healthy"}

    @app.get("/api/v1/status")
    def api_status():
        """Legacy API status endpoint."""
        return {"api_version": "1.0.0", "status": "active"}

    return app
