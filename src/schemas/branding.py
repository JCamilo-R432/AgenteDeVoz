from __future__ import annotations
"""
Branding schemas for white-label customization.
Stored in Tenant.settings['branding'] JSON column.
"""


from typing import Optional
from pydantic import BaseModel, Field, field_validator


class BrandingConfig(BaseModel):
    """
    White-label branding configuration for a tenant.
    All fields are optional — unset fields fall back to platform defaults.
    """

    # Identity
    brand_name: str = Field(
        default="AgenteDeVoz",
        min_length=2,
        max_length=100,
        description="Name shown in the agent UI and notifications",
    )
    tagline: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Short tagline shown below the brand name",
    )
    logo_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL to the tenant's logo image (HTTPS recommended)",
    )
    favicon_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL to the tenant's favicon",
    )

    # Colors (hex)
    primary_color: str = Field(
        default="#4F46E5",
        description="Primary brand color (hex, e.g. #4F46E5)",
    )
    secondary_color: str = Field(
        default="#7C3AED",
        description="Secondary / accent color (hex)",
    )
    background_color: str = Field(
        default="#F9FAFB",
        description="Page background color (hex)",
    )
    text_color: str = Field(
        default="#111827",
        description="Primary text color (hex)",
    )

    # Agent personality
    agent_name: str = Field(
        default="Asistente",
        max_length=80,
        description="Name the agent uses for itself in conversations",
    )
    welcome_message: str = Field(
        default="¡Hola! Soy tu asistente virtual. ¿En qué puedo ayudarte hoy?",
        max_length=500,
        description="First message the agent sends when a session starts",
    )
    language: str = Field(
        default="es",
        description="Default language code (es / en / pt)",
    )

    # Contact / support
    support_email: Optional[str] = Field(
        default=None,
        max_length=255,
    )
    support_whatsapp: Optional[str] = Field(
        default=None,
        max_length=30,
        description="WhatsApp number with country code (e.g. +573001234567)",
    )
    support_url: Optional[str] = Field(
        default=None,
        max_length=500,
    )

    # UI toggles
    show_powered_by: bool = Field(
        default=True,
        description="Show 'Powered by AgenteDeVoz' footer",
    )
    enable_voice: bool = Field(
        default=True,
        description="Show voice input button in the agent UI",
    )
    enable_file_upload: bool = Field(
        default=False,
        description="Allow users to upload files in chat",
    )

    @field_validator("primary_color", "secondary_color", "background_color", "text_color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith("#") and len(v) in (4, 7)):
            raise ValueError(f"Color must be a hex string like #RRGGBB, got: {v!r}")
        return v.upper()

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        allowed = {"es", "en", "pt", "fr", "de"}
        if v.lower() not in allowed:
            raise ValueError(f"language must be one of {allowed}")
        return v.lower()


class BrandingUpdateRequest(BaseModel):
    """Partial update — only supplied fields are changed."""

    brand_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    tagline: Optional[str] = Field(default=None, max_length=200)
    logo_url: Optional[str] = Field(default=None, max_length=500)
    favicon_url: Optional[str] = Field(default=None, max_length=500)
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    agent_name: Optional[str] = Field(default=None, max_length=80)
    welcome_message: Optional[str] = Field(default=None, max_length=500)
    language: Optional[str] = None
    support_email: Optional[str] = Field(default=None, max_length=255)
    support_whatsapp: Optional[str] = Field(default=None, max_length=30)
    support_url: Optional[str] = Field(default=None, max_length=500)
    show_powered_by: Optional[bool] = None
    enable_voice: Optional[bool] = None
    enable_file_upload: Optional[bool] = None

    @field_validator("primary_color", "secondary_color", "background_color", "text_color", mode="before")
    @classmethod
    def validate_hex_color_opt(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not (v.startswith("#") and len(v) in (4, 7)):
            raise ValueError(f"Color must be a hex string like #RRGGBB, got: {v!r}")
        return v.upper()


class BrandingResponse(BrandingConfig):
    """Full branding config returned in GET responses."""

    tenant_id: str
    tenant_name: str
