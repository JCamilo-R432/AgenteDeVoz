from __future__ import annotations
from typing import Dict, List, Optional, Any
"""
Tenant management endpoints.

  POST   /api/v1/tenants/register          — Register new client
  GET    /api/v1/tenants/{id}              — Get tenant info (admin or self)
  PUT    /api/v1/tenants/{id}/settings     — Update settings
  PUT    /api/v1/tenants/{id}/plan         — Change plan (admin)
  POST   /api/v1/tenants/{id}/rotate-key  — Rotate API key
  GET    /api/v1/tenants/{id}/usage        — Usage / limits
  PUT    /api/v1/tenants/{id}/status       — Activate / deactivate (admin)
  GET    /api/v1/tenants                   — List all tenants (admin)
"""


import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_admin
from database import get_db
from schemas.tenant import (
    TenantRegisterRequest,
    TenantUpdateSettingsRequest,
    TenantUpdatePlanRequest,
    TenantResponse,
    TenantPublicResponse,
    TenantUsageResponse,
    TenantListResponse,
)
from services.tenant_service import TenantService

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _service(db: AsyncSession = Depends(get_db)) -> TenantService:
    return TenantService(db)


def _assert_tenant_access(request: Request, tenant_id: str, admin_payload: Optional[Dict]) -> None:
    """
    Allow access if:
      - caller is admin (JWT), OR
      - caller's API key belongs to this tenant (request.state.tenant_id == tenant_id)
    """
    if admin_payload:
        return  # admin always allowed
    caller_tid = getattr(request.state, "tenant_id", None)
    if caller_tid != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: you can only access your own tenant data",
        )


# ── Public ─────────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new tenant",
    tags=["tenants"],
)
async def register_tenant(
    payload: TenantRegisterRequest,
    svc: TenantService = Depends(_service),
) -> TenantResponse:
    """
    Register a new client/tenant. Returns the tenant record including the API key.
    Store the api_key securely — it is only shown once in full here.
    """
    try:
        tenant = await svc.register(payload)
        return TenantResponse.from_tenant(tenant)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


# ── Authenticated (admin or own tenant) ────────────────────────────────────────

@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Get tenant details",
    tags=["tenants"],
)
async def get_tenant(
    tenant_id: str,
    request: Request,
    svc: TenantService = Depends(_service),
    admin: Optional[Dict] = Depends(get_current_admin),
) -> TenantResponse:
    _assert_tenant_access(request, tenant_id, admin)
    tenant = await svc.get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return TenantResponse.from_tenant(tenant)


@router.put(
    "/{tenant_id}/settings",
    response_model=TenantResponse,
    summary="Update tenant settings/branding",
    tags=["tenants"],
)
async def update_settings(
    tenant_id: str,
    payload: TenantUpdateSettingsRequest,
    request: Request,
    svc: TenantService = Depends(_service),
    admin: Optional[Dict] = Depends(get_current_admin),
) -> TenantResponse:
    _assert_tenant_access(request, tenant_id, admin)
    try:
        tenant = await svc.update_settings(tenant_id, payload.settings)
        return TenantResponse.from_tenant(tenant)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/{tenant_id}/usage",
    response_model=TenantUsageResponse,
    summary="Get tenant usage vs plan limits",
    tags=["tenants"],
)
async def get_usage(
    tenant_id: str,
    request: Request,
    svc: TenantService = Depends(_service),
    admin: Optional[Dict] = Depends(get_current_admin),
) -> TenantUsageResponse:
    _assert_tenant_access(request, tenant_id, admin)
    try:
        return await svc.get_usage(tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/{tenant_id}/rotate-key",
    response_model=TenantResponse,
    summary="Rotate tenant API key (admin only)",
    tags=["tenants"],
)
async def rotate_api_key(
    tenant_id: str,
    svc: TenantService = Depends(_service),
    _admin: dict = Depends(get_current_admin),
) -> TenantResponse:
    """Generate a new API key, invalidating the previous one. Admin only."""
    try:
        tenant = await svc.rotate_api_key(tenant_id)
        return TenantResponse.from_tenant(tenant)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Admin-only ─────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=TenantListResponse,
    summary="List all tenants (admin only)",
    tags=["tenants"],
)
async def list_tenants(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    active_only: bool = Query(default=False),
    svc: TenantService = Depends(_service),
    _admin: dict = Depends(get_current_admin),
) -> TenantListResponse:
    return await svc.list_tenants(page=page, limit=limit, active_only=active_only)


@router.put(
    "/{tenant_id}/plan",
    response_model=TenantResponse,
    summary="Change tenant plan (admin only)",
    tags=["tenants"],
)
async def update_plan(
    tenant_id: str,
    payload: TenantUpdatePlanRequest,
    svc: TenantService = Depends(_service),
    _admin: dict = Depends(get_current_admin),
) -> TenantResponse:
    try:
        tenant = await svc.update_plan(tenant_id, payload.plan)
        return TenantResponse.from_tenant(tenant)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put(
    "/{tenant_id}/status",
    response_model=TenantResponse,
    summary="Activate or deactivate a tenant (admin only)",
    tags=["tenants"],
)
async def set_tenant_status(
    tenant_id: str,
    is_active: bool = Query(..., description="true to activate, false to deactivate"),
    svc: TenantService = Depends(_service),
    _admin: dict = Depends(get_current_admin),
) -> TenantResponse:
    try:
        tenant = await svc.set_active(tenant_id, is_active)
        return TenantResponse.from_tenant(tenant)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
