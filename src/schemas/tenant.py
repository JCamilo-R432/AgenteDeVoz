from __future__ import annotations
"""
Pydantic v2 schemas for Tenant API request / response models.
"""


from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ── Request schemas ────────────────────────────────────────────────────────────

class TenantRegisterRequest(BaseModel):
    """Payload to register a new tenant (client onboarding)."""

    name: str = Field(..., min_length=2, max_length=255, description="Company name")
    subdomain: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$",
        description="Unique subdomain slug (e.g. 'mi-tienda')",
    )
    plan: str = Field(default="basic", description="Subscription plan")
    settings: Optional[dict] = Field(default=None, description="Initial settings / branding")

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: str) -> str:
        allowed = {"basic", "pro", "enterprise"}
        if v not in allowed:
            raise ValueError(f"plan must be one of {allowed}")
        return v

    model_config = ConfigDict(from_attributes=True)


class TenantUpdateSettingsRequest(BaseModel):
    """Payload to update a tenant's settings/branding."""

    settings: dict = Field(..., description="Partial or full settings object")

    model_config = ConfigDict(from_attributes=True)


class TenantUpdatePlanRequest(BaseModel):
    """Change the subscription plan of a tenant."""

    plan: str = Field(..., description="New plan: basic | pro | enterprise")

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: str) -> str:
        allowed = {"basic", "pro", "enterprise"}
        if v not in allowed:
            raise ValueError(f"plan must be one of {allowed}")
        return v

    model_config = ConfigDict(from_attributes=True)


# ── Response schemas ───────────────────────────────────────────────────────────

class TenantResponse(BaseModel):
    """Full tenant detail returned after registration or lookup."""

    id: str
    name: str
    subdomain: str
    api_key: str
    plan: str
    is_active: bool
    created_at: datetime
    settings: Optional[dict] = None
    plan_limits: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_tenant(cls, tenant: object) -> "TenantResponse":
        from models.tenant import Tenant  # avoid circular import at module level
        t: Tenant = tenant  # type: ignore[assignment]
        return cls(
            id=t.id,
            name=t.name,
            subdomain=t.subdomain,
            api_key=t.api_key,
            plan=t.plan,
            is_active=t.is_active,
            created_at=t.created_at,
            settings=t.settings,
            plan_limits=t.get_plan_limits(),
        )


class TenantPublicResponse(BaseModel):
    """Tenant info returned to public/client requests (no API key exposed)."""

    id: str
    name: str
    subdomain: str
    plan: str
    is_active: bool
    created_at: datetime
    settings: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class TenantUsageResponse(BaseModel):
    """Usage metrics for a tenant."""

    tenant_id: str
    plan: str
    limits: dict
    usage: dict

    model_config = ConfigDict(from_attributes=True)


class TenantListResponse(BaseModel):
    """Paginated list of tenants (admin only)."""

    items: List[TenantPublicResponse]
    total: int
    page: int
    limit: int

    model_config = ConfigDict(from_attributes=True)
