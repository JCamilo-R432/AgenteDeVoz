from __future__ import annotations
"""
dashboard_routes.py — HTML pages for authenticated user dashboard and auth forms.
Falls back to reading static HTML files when Jinja2 templates are not configured.
"""


import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

logger = APIRouter(prefix="", tags=["dashboard"])  # reuse as router name
router = APIRouter(prefix="", tags=["dashboard"])

_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"
_templates = None
if _TEMPLATE_DIR.exists():
    try:
        from fastapi.templating import Jinja2Templates
        _templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))
    except ImportError:
        pass


def _html(template: str, ctx: dict, request: Request) -> HTMLResponse:
    if _templates:
        try:
            return _templates.TemplateResponse(template, {"request": request, **ctx})
        except Exception:
            pass
    # Fallback: read file directly
    static = _TEMPLATE_DIR / template
    if static.exists():
        return HTMLResponse(static.read_text(encoding="utf-8"))
    return HTMLResponse(f"<h1>Template not found: {template}</h1>", status_code=404)


# ── Auth pages ────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    return _html("auth/login.html", {"title": "Iniciar Sesión | AgenteDeVoz"}, request)


@router.get("/register", response_class=HTMLResponse, include_in_schema=False)
async def register_page(request: Request):
    return _html("auth/register.html", {"title": "Crear cuenta | AgenteDeVoz"}, request)


@router.get("/forgot-password", response_class=HTMLResponse, include_in_schema=False)
async def forgot_password_page(request: Request):
    return _html("auth/forgot_password.html", {"title": "Recuperar contraseña | AgenteDeVoz"}, request)


@router.get("/reset-password", response_class=HTMLResponse, include_in_schema=False)
async def reset_password_page(request: Request):
    return _html("auth/reset_password.html", {"title": "Nueva contraseña | AgenteDeVoz"}, request)


# ── Dashboard pages (require auth — enforced client-side via token check) ─────

@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(request: Request):
    # Token validation is done client-side; server just serves the shell
    return _html("dashboard/user_dashboard.html", {"title": "Dashboard | AgenteDeVoz"}, request)


@router.get("/dashboard/profile", response_class=HTMLResponse, include_in_schema=False)
async def profile_page(request: Request):
    return _html("dashboard/profile.html", {"title": "Mi Perfil | AgenteDeVoz"}, request)


@router.get("/dashboard/subscription", response_class=HTMLResponse, include_in_schema=False)
async def subscription_page(request: Request):
    return _html("dashboard/subscriptions.html", {"title": "Suscripción | AgenteDeVoz"}, request)


@router.get("/dashboard/billing", response_class=HTMLResponse, include_in_schema=False)
async def billing_page(request: Request):
    return _html("dashboard/billing.html", {"title": "Facturación | AgenteDeVoz"}, request)


@router.get("/dashboard/usage", response_class=HTMLResponse, include_in_schema=False)
async def usage_page(request: Request):
    return _html("dashboard/usage.html", {"title": "Uso del Servicio | AgenteDeVoz"}, request)


@router.get("/dashboard/api-keys", response_class=HTMLResponse, include_in_schema=False)
async def api_keys_page(request: Request):
    return _html("dashboard/api_keys.html", {"title": "API Keys | AgenteDeVoz"}, request)


# ── Admin pages ───────────────────────────────────────────────────

@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_dashboard(request: Request):
    return _html("admin/admin_dashboard.html", {"title": "Admin | AgenteDeVoz"}, request)


@router.get("/admin/users", response_class=HTMLResponse, include_in_schema=False)
async def admin_users(request: Request):
    return _html("admin/users_list.html", {"title": "Usuarios | Admin"}, request)


@router.get("/admin/subscriptions", response_class=HTMLResponse, include_in_schema=False)
async def admin_subscriptions(request: Request):
    return _html("admin/subscriptions_list.html", {"title": "Suscripciones | Admin"}, request)


@router.get("/admin/payments", response_class=HTMLResponse, include_in_schema=False)
async def admin_payments(request: Request):
    return _html("admin/payments_list.html", {"title": "Pagos | Admin"}, request)


# ── Pricing ───────────────────────────────────────────────────────

@router.get("/pricing", response_class=HTMLResponse, include_in_schema=False)
async def pricing_page(request: Request):
    return _html("pricing/plans.html", {"title": "Planes y Precios | AgenteDeVoz"}, request)


@router.get("/pricing/checkout", response_class=HTMLResponse, include_in_schema=False)
async def checkout_page(request: Request):
    return _html("pricing/checkout.html", {"title": "Checkout | AgenteDeVoz"}, request)
