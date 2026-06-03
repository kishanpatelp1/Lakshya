"""FastAPI application entrypoint."""

from src.app.telemetry import configure_observability
from src.config import get_settings


def _build_app():
    settings = get_settings()
    configure_observability(settings)

    from src.app import create_app

    return create_app()


app = _build_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app_env == "development",
    )
