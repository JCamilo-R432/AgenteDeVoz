"""
Dashboard web del Agente de Voz.
FastAPI + Jinja2 para monitoreo en tiempo real de conversaciones, tickets y alertas.
"""

import os
import time
from fastapi import FastAPI, WebSocket, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from utils.logger import setup_logger

logger = setup_logger("dashboard")

# ── Inicialización ────────────────────────────────────────────────────────────

dashboard = FastAPI(
    title="AgenteDeVoz Dashboard",
    description="Panel de monitoreo del Agente de Voz",
    version="1.0.0",
    docs_url="/dashboard/docs",
    redoc_url=None,
)

dashboard.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Templates y static files
_base_dir = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(_base_dir, "templates"))

static_path = os.path.join(_base_dir, "static")
if os.path.isdir(static_path):
    dashboard.mount("/dashboard/static", StaticFiles(directory=static_path),
                    name="static")

_start_time = time.time()

# ── Datos de demo (reemplazar con DB queries en producción) ───────────────────

def _get_dashboard_stats() -> dict:
    """Retorna estadísticas del sistema para el dashboard."""
    uptime = int(time.time() - _start_time)
    hours, rem = divmod(uptime, 3600)
    minutes, seconds = divmod(rem, 60)
    return {
        "active_calls": 3,
        "calls_today": 127,
        "avg_handle_time": "2:34",
        "resolution_rate": 84,
        "escalation_rate": 16,
        "tickets_open": 23,
        "tickets_resolved_today": 41,
        "uptime": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
        "api_status": "ok",
        "stt_status": "ok",
        "tts_status": "ok",
        "db_status": "ok",
        "redis_status": "ok",
    }

def _get_recent_conversations(limit: int = 10) -> list:
    """Retorna conversaciones recientes (demo)."""
    import datetime
    now = datetime.datetime.now()
    demo = []
    intents = ["faq", "crear_ticket", "consultar_estado", "queja", "escalar_humano"]
    states = ["ESCUCHANDO", "RESPONDIENDO", "FIN", "AUTENTICANDO"]
    phones = ["+573001234567", "+573209876543", "+573151112222", "+573007654321"]
    for i in range(limit):
        minutes_ago = i * 4
        started = now - datetime.timedelta(minutes=minutes_ago)
        demo.append({
            "session_id": f"sess_{i:04d}abcd",
            "phone": phones[i % len(phones)],
            "state": states[i % len(states)],
            "last_intent": intents[i % len(intents)],
            "duration": f"{(i % 5) + 1}:{'30' if i % 2 else '00'}",
            "started_at": started.strftime("%H:%M:%S"),
            "turns": (i % 7) + 2,
        })
    return demo

def _get_recent_tickets(limit: int = 10) -> list:
    """Retorna tickets recientes (demo)."""
    import datetime
    now = datetime.datetime.now()
    categories = ["facturacion", "tecnico", "envio", "garantia", "general"]
    priorities = ["URGENTE", "ALTA", "MEDIA", "BAJA"]
    statuses = ["ABIERTO", "EN_PROGRESO", "RESUELTO", "CERRADO"]
    tickets = []
    for i in range(limit):
        hours_ago = i * 2
        created = now - datetime.timedelta(hours=hours_ago)
        tickets.append({
            "ticket_id": f"TKT-2026-{i+1:06d}",
            "category": categories[i % len(categories)],
            "priority": priorities[i % len(priorities)],
            "status": statuses[i % len(statuses)],
            "created_at": created.strftime("%Y-%m-%d %H:%M"),
            "phone": f"+5730{i}1234567",
        })
    return tickets

def _get_alerts() -> list:
    """Retorna alertas activas del sistema."""
    return [
        {
            "id": "ALT-001",
            "severity": "WARNING",
            "message": "Tasa de escalacion por encima del umbral (>15%)",
            "component": "Clasificador NLP",
            "time": "10:23:15",
            "resolved": False,
        },
        {
            "id": "ALT-002",
            "severity": "INFO",
            "message": "Redis usando 78% de memoria configurada",
            "component": "Cache Redis",
            "time": "09:45:00",
            "resolved": False,
        },
        {
            "id": "ALT-003",
            "severity": "INFO",
            "message": "Google Cloud TTS fallback activado (credenciales expiran pronto)",
            "component": "TTS Engine",
            "time": "08:00:00",
            "resolved": True,
        },
    ]

# ── Rutas del dashboard ───────────────────────────────────────────────────────

@dashboard.get("/dashboard", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Página principal del dashboard."""
    stats = _get_dashboard_stats()
    conversations = _get_recent_conversations(5)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats,
        "recent_conversations": conversations,
        "page": "home",
    })

@dashboard.get("/dashboard/conversations", response_class=HTMLResponse)
async def dashboard_conversations(request: Request):
    """Vista de conversaciones en tiempo real."""
    conversations = _get_recent_conversations(20)
    return templates.TemplateResponse("conversations.html", {
        "request": request,
        "conversations": conversations,
        "page": "conversations",
    })

@dashboard.get("/dashboard/tickets", response_class=HTMLResponse)
async def dashboard_tickets(request: Request):
    """Vista de gestión de tickets."""
    tickets = _get_recent_tickets(20)
    stats = {
        "total_open": 23,
        "total_urgente": 2,
        "total_alta": 7,
        "resolved_today": 41,
    }
    return templates.TemplateResponse("tickets.html", {
        "request": request,
        "tickets": tickets,
        "ticket_stats": stats,
        "page": "tickets",
    })

@dashboard.get("/dashboard/alerts", response_class=HTMLResponse)
async def dashboard_alerts(request: Request):
    """Vista de alertas del sistema."""
    alerts = _get_alerts()
    active_alerts = [a for a in alerts if not a["resolved"]]
    return templates.TemplateResponse("alerts.html", {
        "request": request,
        "alerts": alerts,
        "active_count": len(active_alerts),
        "page": "alerts",
    })

# ── APIs JSON para el dashboard ───────────────────────────────────────────────

@dashboard.get("/dashboard/api/stats")
async def api_stats():
    """API JSON de estadísticas para actualizaciones en tiempo real."""
    return JSONResponse(_get_dashboard_stats())

@dashboard.get("/dashboard/api/conversations")
async def api_conversations():
    return JSONResponse({"conversations": _get_recent_conversations(20)})

@dashboard.get("/dashboard/api/tickets")
async def api_tickets():
    return JSONResponse({"tickets": _get_recent_tickets(20)})

@dashboard.get("/dashboard/api/alerts")
async def api_alerts():
    return JSONResponse({"alerts": _get_alerts()})

# ── WebSocket de actualización en tiempo real ─────────────────────────────────

@dashboard.websocket("/dashboard/ws/live")
async def dashboard_live_updates(websocket: WebSocket):
    """
    Envía actualizaciones de métricas cada 5 segundos al dashboard.
    """
    await websocket.accept()
    logger.info("Cliente dashboard conectado via WS")
    try:
        import asyncio
        while True:
            stats = _get_dashboard_stats()
            await websocket.send_json({"type": "stats", "data": stats})
            await asyncio.sleep(5)
    except Exception as e:
        logger.info(f"Dashboard WS desconectado: {e}")
