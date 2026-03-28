from __future__ import annotations
from typing import Dict, List, Any
"""
Pydantic v2 schemas for Order-related API request/response models.
"""


from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ── Status Enum ────────────────────────────────────────────────────────────────

class OrderStatusEnum(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    processing = "processing"
    shipped = "shipped"
    in_transit = "in_transit"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    cancelled = "cancelled"
    refunded = "refunded"


STATUS_TEXT_MAP: Dict[str, str] = {
    "pending": "Pendiente de confirmación",
    "confirmed": "Confirmado",
    "processing": "En preparación",
    "shipped": "Enviado",
    "in_transit": "En camino",
    "out_for_delivery": "En reparto",
    "delivered": "Entregado",
    "cancelled": "Cancelado",
    "refunded": "Reembolsado",
}


# ── Item Schemas ───────────────────────────────────────────────────────────────

class OrderItemCreate(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=255)
    product_sku: Optional[str] = Field(None, max_length=50)
    quantity: int = Field(..., ge=1)
    unit_price: Decimal = Field(..., ge=Decimal("0.01"))

    model_config = ConfigDict(from_attributes=True)


class OrderItemResponse(BaseModel):
    id: str
    product_name: str
    product_sku: Optional[str]
    quantity: int
    unit_price: Decimal
    subtotal: Decimal

    model_config = ConfigDict(from_attributes=True)


# ── Request Schemas ────────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    customer_id: Optional[str] = None
    customer_phone: Optional[str] = Field(None, description="Used to look up customer if customer_id not given")
    items: List[OrderItemCreate] = Field(..., min_length=1)
    currency: str = Field(default="COP", max_length=3)
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UpdateOrderStatusRequest(BaseModel):
    status: OrderStatusEnum
    notes: Optional[str] = None
    changed_by: str = Field(default="admin")

    model_config = ConfigDict(from_attributes=True)


# ── Summary & Nested Schemas ───────────────────────────────────────────────────

class OrderSummary(BaseModel):
    id: str
    order_number: str
    status: str
    status_text: Optional[str] = None
    total_amount: Decimal
    currency: str
    created_at: datetime
    estimated_delivery: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_order(cls, order: object) -> "OrderSummary":
        return cls(
            id=str(order.id),  # type: ignore[attr-defined]
            order_number=order.order_number,  # type: ignore[attr-defined]
            status=order.status,  # type: ignore[attr-defined]
            status_text=STATUS_TEXT_MAP.get(order.status, order.status),  # type: ignore[attr-defined]
            total_amount=order.total_amount,  # type: ignore[attr-defined]
            currency=order.currency,  # type: ignore[attr-defined]
            created_at=order.created_at,  # type: ignore[attr-defined]
            estimated_delivery=order.estimated_delivery,  # type: ignore[attr-defined]
        )


class ShipmentInfo(BaseModel):
    id: str
    tracking_number: Optional[str]
    carrier: Optional[str]
    current_location: Optional[str]
    status: str
    estimated_delivery: Optional[datetime]
    delivered_at: Optional[datetime]
    delivery_attempts: int

    model_config = ConfigDict(from_attributes=True)


class StatusHistoryEntry(BaseModel):
    status: str
    status_text: Optional[str] = None
    date: datetime
    description: Optional[str] = None
    changed_by: str

    model_config = ConfigDict(from_attributes=True)


class OrderDetailResponse(BaseModel):
    id: str
    order_number: str
    status: str
    status_text: str
    total_amount: Decimal
    currency: str
    created_at: datetime
    confirmed_at: Optional[datetime]
    shipped_at: Optional[datetime]
    delivered_at: Optional[datetime]
    estimated_delivery: Optional[datetime]
    actual_delivery: Optional[datetime]
    cancellation_reason: Optional[str]

    items: List[OrderItemResponse] = []
    shipment: Optional[ShipmentInfo] = None
    status_history: List[StatusHistoryEntry] = []

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_order(
        cls,
        order: object,
        include_items: bool = True,
        include_shipment: bool = True,
    ) -> "OrderDetailResponse":
        """Build a full response from an ORM Order object."""
        items: List[OrderItemResponse] = []
        if include_items and hasattr(order, "items") and order.items:  # type: ignore[attr-defined]
            items = [
                OrderItemResponse(
                    id=str(item.id),
                    product_name=item.product_name,
                    product_sku=item.product_sku,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    subtotal=item.subtotal,
                )
                for item in order.items  # type: ignore[attr-defined]
            ]

        shipment: Optional[ShipmentInfo] = None
        if include_shipment and hasattr(order, "shipments") and order.shipments:  # type: ignore[attr-defined]
            s = order.shipments[0]  # type: ignore[attr-defined]
            shipment = ShipmentInfo(
                id=str(s.id),
                tracking_number=s.tracking_number,
                carrier=s.carrier,
                current_location=s.current_location,
                status=s.status,
                estimated_delivery=s.estimated_delivery,
                delivered_at=s.delivered_at,
                delivery_attempts=s.delivery_attempts or 0,
            )

        history: List[StatusHistoryEntry] = []
        if hasattr(order, "status_history") and order.status_history:  # type: ignore[attr-defined]
            history = [
                StatusHistoryEntry(
                    status=h.new_status,
                    status_text=STATUS_TEXT_MAP.get(h.new_status, h.new_status),
                    date=h.changed_at,
                    description=h.notes,
                    changed_by=h.changed_by,
                )
                for h in order.status_history  # type: ignore[attr-defined]
            ]

        return cls(
            id=str(order.id),  # type: ignore[attr-defined]
            order_number=order.order_number,  # type: ignore[attr-defined]
            status=order.status,  # type: ignore[attr-defined]
            status_text=STATUS_TEXT_MAP.get(order.status, order.status),  # type: ignore[attr-defined]
            total_amount=order.total_amount,  # type: ignore[attr-defined]
            currency=order.currency,  # type: ignore[attr-defined]
            created_at=order.created_at,  # type: ignore[attr-defined]
            confirmed_at=order.confirmed_at,  # type: ignore[attr-defined]
            shipped_at=order.shipped_at,  # type: ignore[attr-defined]
            delivered_at=order.delivered_at,  # type: ignore[attr-defined]
            estimated_delivery=order.estimated_delivery,  # type: ignore[attr-defined]
            actual_delivery=order.actual_delivery,  # type: ignore[attr-defined]
            cancellation_reason=order.cancellation_reason,  # type: ignore[attr-defined]
            items=items,
            shipment=shipment,
            status_history=history,
        )
