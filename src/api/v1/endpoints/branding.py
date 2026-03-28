from __future__ import annotations
from typing import Dict, List, Optional, Any
"""
White-label branding endpoints — Module 5.

GET  /api/v1/branding                  — get own branding (requires API key)
PUT  /api/v1/branding                  — update branding (requires API key)
POST /api/v1/branding/reset            — reset to defaults (requires API key)
GET  /api/v1/branding/public/{subdomain} — public branding (no auth, used by agent UI)
"""


from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from schemas.branding import BrandingResponse, BrandingUpdateRequest
from services.branding_service import BrandingService

router = APIRouter(tags=["branding"])


def _require_tenant_id(request: Request) -> str:
    tenant_id: Optional[str] = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="X-API-Key required")
    return tenant_id


@router.get("", response_model=BrandingResponse)
async def get_branding(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> BrandingResponse:
    """Return current branding configuration for the authenticated tenant."""
    tenant_id = _require_tenant_id(request)
    svc = BrandingService(db)
    return await svc.get_branding(tenant_id)


@router.put("", response_model=BrandingResponse)
async def update_branding(
    data: BrandingUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> BrandingResponse:
    """Partially update branding. Only supplied fields are changed."""
    tenant_id = _require_tenant_id(request)
    svc = BrandingService(db)
    return await svc.update_branding(tenant_id, data)


@router.post("/reset", response_model=BrandingResponse)
async def reset_branding(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> BrandingResponse:
    """Reset branding to platform defaults."""
    tenant_id = _require_tenant_id(request)
    svc = BrandingService(db)
    return await svc.reset_branding(tenant_id)


@router.get("/public/{subdomain}", response_model=BrandingResponse)
async def public_branding(
    subdomain: str,
    db: AsyncSession = Depends(get_db),
) -> BrandingResponse:
    """
    Public endpoint — returns branding for any active subdomain.
    Used by the agent HTML page to dynamically apply tenant colors/logo.
    """
    svc = BrandingService(db)
    branding = await svc.get_public_branding(subdomain)
    if branding is None:
        raise HTTPException(status_code=404, detail="Subdomain not found")
    return branding
