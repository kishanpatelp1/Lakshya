"""Chat domain routers."""

from src.domains.chat.routes import router as chat_router
from src.domains.chat.upload_routes import router as upload_router

__all__ = ["chat_router", "upload_router"]
