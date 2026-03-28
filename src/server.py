"""
Servidor principal de AgenteDeVoz.
Monta la API REST, el Dashboard, y los endpoints WebSocket.
"""

import sys
import os

# Asegurar que src/ esté en el path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from starlette.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocket

from api.routes import router as api_router
from api.voice_routes import router as voice_router
from api.websocket import handle_web_client, handle_twilio_media_stream
from utils.logger import setup_logger

# ── SaaS routers ──────────────────────────────────────────────────────────────
try:
    from api.auth_routes         import router as auth_router
    from api.user_routes         import router as user_router
    from api.subscription_routes import router as subscription_router
    from api.payment_routes      import router as payment_router
    from api.license_routes      import router as license_router
    from admin.admin_panel       import router as admin_router
    from web.dashboard_routes    import router as dashboard_router
    _saas_routers_available = True
except ImportError as _e:
    import logging
    logging.getLogger("server").warning(f"SaaS routers not loaded: {_e}")
    _saas_routers_available = False

# ── SaaS middleware ────────────────────────────────────────────────────────────
try:
    from middleware.auth_middleware         import AuthMiddleware, RateLimitMiddleware
    from middleware.subscription_middleware import SubscriptionMiddleware
    from middleware.audit_middleware        import AuditMiddleware
    _middleware_available = True
except ImportError:
    _middleware_available = False

# ── Dashboard (legacy) ────────────────────────────────────────────────────────
try:
    from dashboard.app import dashboard as _legacy_dashboard
    _legacy_dashboard_available = True
except ImportError:
    _legacy_dashboard_available = False

try:
    from core.logging_config import configure_logging
    configure_logging()
except ImportError:
    pass

logger = setup_logger("server")

# ── App principal ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="AgenteDeVoz API",
    description="API del Agente de Voz con autenticación SaaS y monetización",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── SaaS middleware stack ──────────────────────────────────────────────────────
if _middleware_available:
    app.add_middleware(AuditMiddleware)
    app.add_middleware(SubscriptionMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuthMiddleware)

# ── Montar rutas ──────────────────────────────────────────────────────────────

# Core API (voz, tickets, FAQ, etc.)
app.include_router(api_router, prefix="/api/v1")

# Twilio Voice webhooks
app.include_router(voice_router, prefix="/api/v1")

# SaaS API routes
if _saas_routers_available:
    app.include_router(auth_router,         prefix="/api/v1/auth",          tags=["auth"])
    app.include_router(user_router,         prefix="/api/v1/users",         tags=["users"])
    app.include_router(subscription_router, prefix="/api/v1/subscriptions", tags=["subscriptions"])
    app.include_router(payment_router,      prefix="/api/v1/payments",      tags=["payments"])
    app.include_router(license_router,      prefix="/api/v1/licenses",      tags=["licenses"])
    app.include_router(admin_router,        prefix="/api/v1/admin",         tags=["admin"])
    app.include_router(dashboard_router)

# ── Archivos estáticos ────────────────────────────────────────────────────────
_static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# ── Orders v1 router ──────────────────────────────────────────────────────────
try:
    from api.v1.router import router as orders_v1_router
    _orders_router_available = True
except ImportError as _e:
    import logging as _logging
    _logging.getLogger("server").warning(f"Orders v1 router not loaded: {_e}")
    _orders_router_available = False

if _orders_router_available:
    app.include_router(orders_v1_router, prefix="/api/v1", tags=["orders-v1"])

# ── Legacy dashboard (mount last) ─────────────────────────────────────────────
# Agent demo page
@app.get("/agent")
async def agent_page():
    return FileResponse("public/agent.html")

# Landing page
@app.get("/")
async def landing_page():
    return FileResponse("public/index.html")


if _legacy_dashboard_available and not _saas_routers_available:
    app.mount("/", _legacy_dashboard)

# ── WebSocket endpoints ───────────────────────────────────────────────────────

@app.websocket("/ws/chat/{session_id}")
async def ws_chat(websocket: WebSocket, session_id: str):
    """WebSocket para clientes web del chat en vivo."""
    await handle_web_client(websocket, session_id)

@app.websocket("/ws/twilio/media")
async def ws_twilio(websocket: WebSocket):
    """WebSocket para Twilio Media Streams (audio en tiempo real)."""
    await handle_twilio_media_stream(websocket)

# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "version": "2.0.0", "saas": _saas_routers_available}

# ── Startup / Shutdown ────────────────────────────────────────────────────────

@app.on_event("startup")
async def init_orders_db():
    """Create order management tables on startup if they don't exist."""
    try:
        from database import engine, Base
        import models  # noqa: F401 — registers all ORM models
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Orders DB tables verified/created.")
    except Exception as e:
        logger.warning(f"Orders DB init skipped: {e}")


@app.on_event("startup")
async def startup():
    logger.info("AgenteDeVoz v2.0 iniciando...")
    logger.info("API disponible en /api/v1")
    logger.info(f"SaaS routers: {'activos' if _saas_routers_available else 'no disponibles'}")
    logger.info(f"Middleware SaaS: {'activo' if _middleware_available else 'no disponible'}")
    logger.info("Docs en /api/docs")

@app.on_event("shutdown")
async def shutdown():
    logger.info("AgenteDeVoz cerrando conexiones...")


