from typing import Dict, List, Optional, Any, Union
"""
SQLAlchemy model for Shipment entity.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import String, DateTime, JSON, Text, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class ShipmentStatus(str, Enum):
    pending = "pending"
    picked_up = "picked_up"
    in_transit = "in_transit"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    failed_attempt = "failed_attempt"


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Shipment(Base):
    """Shipping information and tracking for an order."""

    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
        index=True,
    )
    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tracking_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
        index=True,
    )
    carrier: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="e.g. Coordinadora, Servientrega, 90minutos",
    )
    service_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Address info stored as JSON for flexibility
    origin_address: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    destination_address: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)

    current_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ShipmentStatus.pending.value,
    )

    # JSON array of tracking events: [{event, location, timestamp, description}, ...]
    status_history: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)

    estimated_delivery: Mapped[datetime ] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime ] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivery_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship back to order
    order: Mapped["Order"] = relationship(  # noqa: F821
        "Order",
        back_populates="shipments",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Shipment {self.tracking_number} carrier={self.carrier} status={self.status}>"
