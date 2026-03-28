from typing import Dict, List, Optional, Any, Union
"""
SQLAlchemy model for Customer entity.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, JSON, ForeignKey, UniqueConstraint, func
from typing import Dict, List, Optional, Any, Union
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Dict, List, Optional, Any, Union

from database import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Customer(Base):
    """Represents a customer who can place orders, scoped to a tenant."""

    __tablename__ = "customers"

    # phone + email uniqueness is now per-tenant (see __table_args__)
    __table_args__ = (
        UniqueConstraint("tenant_id", "phone", name="uq_customers_tenant_phone"),
        UniqueConstraint("tenant_id", "email", name="uq_customers_tenant_email"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
        index=True,
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,   # nullable for backward compat with existing rows
        index=True,
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now_utc,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime ] = mapped_column(
        DateTime(timezone=True),
        onupdate=_now_utc,
        nullable=True,
    )
    metadata_json: Mapped[Optional[Dict]] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant "] = relationship(  # noqa: F821
        "Tenant",
        back_populates="customers",
        lazy="select",
    )
    orders: Mapped[List["Order"]] = relationship(  # noqa: F821
        "Order",
        back_populates="customer",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Customer id={self.id} phone={self.phone} name={self.full_name!r}>"
