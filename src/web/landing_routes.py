from __future__ import annotations
"""
landing_routes.py — FastAPI router for landing page & static-ish pages.
Serves Jinja2 templates for SEO-friendly server-side rendering.
If templates/ directory is absent, falls back to serving public/ directly.
"""


import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["landing"])

# Template directory (optional — falls back gracefully)
_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"
_templates: Jinja2Templates  = None
if _TEMPLATE_DIR.exists():
    _templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))


def _render(request: Request, template: str, ctx: dict) -> HTMLResponse:
    """Render a Jinja2 template, or return a 404 if templates not available."""
    if _templates is None:
        return HTMLResponse("<h1>Templates not configured</h1>", status_code=404)
    return _templates.TemplateResponse(template, {"request": request, **ctx})


# ── Routes ────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page(request: Request):
    """Landing page — served from templates/landing.html (SSR) or public/index.html."""
    if _templates is None:
        # Serve static file directly
        static = Path(__file__).parent.parent.parent / "public" / "index.html"
        if static.exists():
            return HTMLResponse(static.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>404 — index.html not found</h1>", status_code=404)

    return _render(request, "landing.html", {
        "title"      : "AgenteDeVoz — Agente de Atención al Cliente con IA",
        "description": "Automatiza el 70 % de tus consultas con un agente de voz inteligente. Responde en menos de 1 segundo, 24/7.",
        "canonical"  : str(request.url),
    })


@router.get("/agent", response_class=HTMLResponse, include_in_schema=False)
async def agent_page(request: Request):
    """Interactive voice-agent demo page."""
    if _templates is None:
        static = Path(__file__).parent.parent.parent / "public" / "agent.html"
        if static.exists():
            return HTMLResponse(static.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>404 — agent.html not found</h1>", status_code=404)

    return _render(request, "agent-interface.html", {
        "title"      : "Agente de Voz - Prueba Gratis | AgenteDeVoz",
        "description": "Prueba el Agente de Voz Inteligente — habla o escribe para interactuar con nuestra IA.",
        "canonical"  : str(request.url),
    })


@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy_page(request: Request):
    """Privacy policy page."""
    if _templates and (_TEMPLATE_DIR / "privacy.html").exists():
        return _render(request, "privacy.html", {
            "title": "Política de Privacidad | AgenteDeVoz",
        })
    # Redirect to compliance doc as fallback
    return RedirectResponse("/", status_code=302)


@router.get("/health-web", include_in_schema=False)
async def web_health():
    return {"status": "ok", "service": "landing"}
