"""Application wiring package.

This module hosts app composition primitives (factory, middleware, routers,
lifespan) so runtime behavior stays stable while code ownership is clearer.
"""

from src.app.factory import create_app

__all__ = ["create_app"]
