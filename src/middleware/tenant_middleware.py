from __future__ import annotations
"""
Tenant middleware — resolves X-API-Key to a Tenant and injects tenant_id
into request.state and the async context variable for the duration of
each request.

Public paths (listed in SKIP_PATHS) are processed without API-key validation
so that health checks, docs, admin JWT routes, and auth endpoints work freely.
"""


import logging
import time
from typing import Optional

from fastapi import Request, Response
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from database import AsyncSessionLocal
from models.tenant import Tenant
from utils.tenant_context import set_current_tenant_id

logger = logging.getLogger(__name__)

# Paths that bypass API-key validation (prefix match)
SKIP_PATHS: tuple[str, ...] = (
    "/health",
    "/api/v1/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/openapi.json",
    "/docs",
    "/redoc",
    "/api/v1/auth/",       # SaaS auth (register, login, refresh)
    "/api/v1/admin/",      # Admin uses JWT instead of API key
    "/api/v1/tenants/register",  # Registration doesn't need an existing tenant
)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Reads the X-API-Key header, resolves it to a Tenant record, and:
      - Sets request.state.tenant_id
      - Sets request.state.tenant  (full Tenant ORM object)
      - Sets the async context variable via tenant_context module

    If the path is in SKIP_PATHS: sets tenant_id = None and continues.
    If X-API-Key is absent on a non-skip path: sets tenant_id = None (soft).
    If X-API-Key is present but invalid/inactive: returns HTTP 401.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path: str = request.url.path

        # Default: no tenant
        request.state.tenant_id = None
        request.state.tenant = None

        api_key: Optional[str] = request.headers.get("X-API-Key")

        # Skip validation for public/admin paths
        if self._should_skip(path) or not api_key:
            token = set_current_tenant_id(None)
            try:
                return await call_next(request)
            finally:
                from utils.tenant_context import current_tenant_id_var
                current_tenant_id_var.reset(token)

        # Resolve API key → Tenant
        tenant = await self._resolve_tenant(api_key)

        if tenant is None:
            return Response(
                content='{"detail": "Invalid or unknown X-API-Key"}',
                status_code=401,
                media_type="application/json",
            )

        if not tenant.is_active:
            return Response(
                content='{"detail": "Tenant account is inactive. Contact support."}',
                status_code=403,
                media_type="application/json",
            )

        request.state.tenant_id = tenant.id
        request.state.tenant = tenant

        token = set_current_tenant_id(tenant.id)
        try:
            response = await call_next(request)
        finally:
            from utils.tenant_context import current_tenant_id_var
            current_tenant_id_var.reset(token)

        # Expose tenant plan in response header for debugging
        response.headers["X-Tenant-Plan"] = tenant.plan
        return response

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _should_skip(self, path: str) -> bool:
        return any(path.startswith(skip) for skip in SKIP_PATHS)

    async def _resolve_tenant(self, api_key: str) -> Optional[Tenant]:
        """Look up tenant by API key. Uses a short-lived DB session."""
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Tenant).where(Tenant.api_key == api_key)
                )
                return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"TenantMiddleware DB error: {exc}")
            return None
