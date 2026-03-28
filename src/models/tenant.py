"""
SQLAlchemy model for Tenant (multi-tenancy SaaS).
Each tenant is an isolated client organization with its own data.
"""

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, JSON, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Dict, List, Optional, Any, Union

from database import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_api_key() -> str:
    """Generate a cryptographically secure API key."""
    return f"ak_{secrets.token_urlsafe(32)}"


# Plan limits: max requests per minute and per day
PLAN_LIMITS: Dict[str, Dict] = {
    "basic": {
        "requests_per_minute": 60,
        "requests_per_day": 10_000,
        "max_customers": 1_000,
        "max_orders": 50_000,
    },
    "pro": {
        "requests_per_minute": 300,
        "requests_per_day": 50_000,
        "max_customers": 10_000,
        "max_orders": 500_000,
    },
    "enterprise": {
        "requests_per_minute": 1_000,
        "requests_per_day": 200_000,
        "max_customers": -1,       # unlimited
        "max_orders": -1,
    },
}


class Tenant(Base):
    """Represents a SaaS client organization (tenant)."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subdomain: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    api_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        default=_generate_api_key,
        index=True,
    )
    plan: Mapped[str] = mapped_column(
        String(50), nullable=False, default="basic"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now_utc,
        server_default=func.now(),
        nullable=False,
    )
    # Branding / config / billing info stored as JSONB
    settings: Mapped[Optional[Dict]] = mapped_column("settings", JSON, nullable=True)
    metadata_json: Mapped[Optional[Dict]] = mapped_column("metadata", JSON, nullable=True)

    # Billing
    subscription: Mapped[Optional["Subscription"]] = relationship(  # noqa: F821
        "Subscription",
        back_populates="tenant",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    # Relationships — lazy loaded to avoid N+1 in list endpoints
    customers: Mapped[List["Customer"]] = relationship(  # noqa: F821
        "Customer",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="select",
    )
    orders: Mapped[List["Order"]] = relationship(  # noqa: F821
        "Order",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # ── Helpers ────────────────────────────────────────────────────────────────

    def get_plan_limits(self) -> dict:
        """Return rate/quota limits for this tenant's plan."""
        return PLAN_LIMITS.get(self.plan, PLAN_LIMITS["basic"])

    def regenerate_api_key(self) -> str:
        """Rotate the API key and return the new value."""
        self.api_key = _generate_api_key()
        return self.api_key

    def __repr__(self) -> str:
        return f"<Tenant {self.subdomain!r} plan={self.plan} active={self.is_active}>"
