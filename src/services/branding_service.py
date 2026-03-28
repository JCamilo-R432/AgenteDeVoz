from __future__ import annotations
"""
Branding service — manages white-label configuration stored in Tenant.settings.
No separate table needed: branding lives in the settings JSON column.
"""


from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.tenant import Tenant
from schemas.branding import BrandingConfig, BrandingUpdateRequest, BrandingResponse


_SETTINGS_KEY = "branding"


class BrandingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Read ───────────────────────────────────────────────────────────────────

    async def get_branding(self, tenant_id: str) -> BrandingResponse:
        """Return current branding for a tenant (with defaults for unset fields)."""
        tenant = await self._get_tenant(tenant_id)
        config = self._extract_config(tenant)
        return BrandingResponse(
            **config.model_dump(),
            tenant_id=tenant.id,
            tenant_name=tenant.name,
        )

    async def get_public_branding(self, subdomain: str) -> Optional[BrandingResponse]:
        """
        Return branding by subdomain — used by the agent UI before auth.
        Returns None if subdomain not found.
        """
        result = await self._session.execute(
            select(Tenant).where(
                Tenant.subdomain == subdomain,
                Tenant.is_active.is_(True),
            )
        )
        tenant = result.scalar_one_or_none()
        if tenant is None:
            return None
        config = self._extract_config(tenant)
        return BrandingResponse(
            **config.model_dump(),
            tenant_id=tenant.id,
            tenant_name=tenant.name,
        )

    # ── Write ──────────────────────────────────────────────────────────────────

    async def update_branding(
        self, tenant_id: str, data: BrandingUpdateRequest
    ) -> BrandingResponse:
        """
        Partially update branding — only supplied (non-None) fields are changed.
        """
        tenant = await self._get_tenant(tenant_id)
        current = self._extract_config(tenant)

        # Merge non-None fields from update request
        current_dict = current.model_dump()
        for field, value in data.model_dump(exclude_none=True).items():
            current_dict[field] = value

        new_config = BrandingConfig(**current_dict)

        # Persist back into settings JSON
        settings = dict(tenant.settings or {})
        settings[_SETTINGS_KEY] = new_config.model_dump()
        tenant.settings = settings

        await self._session.flush()
        await self._session.refresh(tenant)

        return BrandingResponse(
            **new_config.model_dump(),
            tenant_id=tenant.id,
            tenant_name=tenant.name,
        )

    async def reset_branding(self, tenant_id: str) -> BrandingResponse:
        """Reset branding to platform defaults."""
        tenant = await self._get_tenant(tenant_id)
        settings = dict(tenant.settings or {})
        settings.pop(_SETTINGS_KEY, None)
        tenant.settings = settings
        await self._session.flush()

        defaults = BrandingConfig()
        return BrandingResponse(
            **defaults.model_dump(),
            tenant_id=tenant.id,
            tenant_name=tenant.name,
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _get_tenant(self, tenant_id: str) -> Tenant:
        result = await self._session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if tenant is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Tenant not found")
        return tenant

    @staticmethod
    def _extract_config(tenant: Tenant) -> BrandingConfig:
        """Extract branding config from tenant.settings, filling defaults."""
        raw: dict = {}
        if tenant.settings and _SETTINGS_KEY in tenant.settings:
            raw = tenant.settings[_SETTINGS_KEY]
        return BrandingConfig(**raw)
