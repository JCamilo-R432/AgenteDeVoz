from typing import Dict, List, Optional, Any, Union
"""
SQLAlchemy models for Order, OrderItem, and OrderStatusHistory.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    String,
    DateTime,
    JSON,
    Text,
    Integer,
    Numeric,
    ForeignKey,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

# Forward-reference guard: Tenant is defined in models.tenant
# The relationship is declared below via string name.


class OrderStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    processing = "processing"
    shipped = "shipped"
    in_transit = "in_transit"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    cancelled = "cancelled"
    refunded = "refunded"


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ── Order ──────────────────────────────────────────────────────────────────────

class Order(Base):
    """Represents a customer order."""

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
        index=True,
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,   # nullable for backward compat; enforced at service layer
        index=True,
    )
    order_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )
    customer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=OrderStatus.pending.value,
        index=True,
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="COP",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now_utc,
        server_default=func.now(),
        nullable=False,
    )
    confirmed_at: Mapped[datetime ] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    shipped_at: Mapped[datetime ] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime ] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    estimated_delivery: Mapped[datetime ] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_delivery: Mapped[datetime ] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[Dict]] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant "] = relationship(  # noqa: F821
        "Tenant",
        back_populates="orders",
        lazy="select",
    )
    customer: Mapped["Customer"] = relationship(  # noqa: F821
        "Customer",
        back_populates="orders",
        lazy="select",
    )
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="select",
    )
    shipments: Mapped[List["Shipment"]] = relationship(  # noqa: F821
        "Shipment",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="select",
    )
    status_history: Mapped[List["OrderStatusHistory"]] = relationship(
        "OrderStatusHistory",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusHistory.changed_at.asc()",
        lazy="select",
    )
    payments: Mapped[List["OrderPayment"]] = relationship(  # noqa: F821
        "OrderPayment",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Order {self.order_number} status={self.status}>"


# ── OrderItem ──────────────────────────────────────────────────────────────────

class OrderItem(Base):
    """A line item within an order."""

    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
    )
    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_sku: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    metadata_json: Mapped[Optional[Dict]] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )

    order: Mapped["Order"] = relationship("Order", back_populates="items")

    def __repr__(self) -> str:
        return f"<OrderItem {self.product_name} x{self.quantity}>"


# ── OrderStatusHistory ─────────────────────────────────────────────────────────

class OrderStatusHistory(Base):
    """Audit log of every status change on an order."""

    __tablename__ = "order_status_history"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
    )
    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now_utc,
        server_default=func.now(),
        nullable=False,
    )
    changed_by: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="system",
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="status_history")

    def __repr__(self) -> str:
        return f"<StatusHistory {self.previous_status}→{self.new_status} at {self.changed_at}>"
