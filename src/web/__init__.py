"""
src/web — Landing page & voice interface web layer.
Exports FastAPI routers that mount onto the main server.
"""

from src.web.landing_routes import router as landing_router
from src.web.voice_interface import router as voice_router

__all__ = ["landing_router", "voice_router"]
