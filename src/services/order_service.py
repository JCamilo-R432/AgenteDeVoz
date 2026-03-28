from __future__ import annotations
"""
Order service — business logic layer wrapping the order repository.
"""


import logging
import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.order import Order, OrderStatus
from repositories.order_repository import OrderRepository
from schemas.order import (
    CreateOrderRequest,
    OrderSummary,
    STATUS_TEXT_MAP,
)
from schemas.responses import OrderStatistics, PaginatedResponse

logger = logging.getLogger(__name__)

# Business-day offset for estimated delivery (3 working days)
_DELIVERY_BUSINESS_DAYS = 3
_WEEKENDS = {5, 6}  # Saturday=5, Sunday=6


class OrderService:
    """High-level order operations used by API endpoints and the voice agent."""

    def __init__(self, session: AsyncSession, tenant_id: Optional[str] = None) -> None:
        self.session = session
        self.tenant_id = tenant_id  # None = admin / no scoping
        self.repo = OrderRepository(session)

    # ── Read ───────────────────────────────────────────────────────────────────

    async def get_by_order_number(self, order_number: str) -> Optional[Order]:
        return await self.repo.get_by_order_number(order_number, tenant_id=self.tenant_id)

    async def get_by_customer_phone(self, phone: str) -> List[Order]:
        return await self.repo.get_by_customer_phone(phone, limit=10, tenant_id=self.tenant_id)

    async def get_by_customer_email(self, email: str) -> List[Order]:
        return await self.repo.get_by_customer_email(email, limit=10, tenant_id=self.tenant_id)

    async def get_by_tracking_number(self, tracking_number: str) -> Optional[Order]:
        return await self.repo.get_by_tracking_number(tracking_number, tenant_id=self.tenant_id)

    # ── Write ──────────────────────────────────────────────────────────────────

    async def create_order(
        self,
        data: CreateOrderRequest,
        customer_id: Optional[str] = None,
    ) -> Order:
        """Create a new order from the request payload."""
        resolved_customer_id = customer_id or data.customer_id
        if not resolved_customer_id:
            raise ValueError("customer_id is required to create an order")

        order_number = await self._generate_order_number()
        estimated_delivery = self._calculate_estimated_delivery()

        # Build items list
        items_data = []
        total_amount = Decimal("0.00")
        for item_req in data.items:
            subtotal = item_req.unit_price * item_req.quantity
            total_amount += subtotal
            items_data.append(
                {
                    "id": str(uuid.uuid4()),
                    "product_name": item_req.product_name,
                    "product_sku": item_req.product_sku,
                    "quantity": item_req.quantity,
                    "unit_price": item_req.unit_price,
                    "subtotal": subtotal,
                }
            )

        order = await self.repo.create(
            id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            order_number=order_number,
            customer_id=str(resolved_customer_id),
            status=OrderStatus.pending.value,
            total_amount=total_amount,
            currency=data.currency,
            created_at=datetime.now(timezone.utc),
            estimated_delivery=estimated_delivery,
            items=items_data,
        )

        # Add initial status history
        await self.repo.update_status(
            order_id=order.id,
            status=OrderStatus.pending.value,
            notes="Pedido creado",
            changed_by="system",
        )

        logger.info(f"Order created: {order.order_number} for customer {resolved_customer_id}")
        return order

    async def update_status(
        self,
        order_id: str,
        status: str,
        notes: Optional[str] = None,
        changed_by: str = "system",
    ) -> Order:
        """Update an order's status."""
        order = await self.repo.update_status(
            order_id=str(order_id),
            status=status,
            notes=notes,
            changed_by=changed_by,
        )
        logger.info(f"Order {order.order_number} status updated to {status} by {changed_by}")
        return order

    async def cancel_order(self, order_id: str, reason: str) -> Order:
        """Cancel an order with a provided reason."""
        order = await self.repo.get_by_id(str(order_id))
        if order is None:
            raise ValueError(f"Order {order_id} not found")

        if order.status in (OrderStatus.delivered.value, OrderStatus.cancelled.value):
            raise ValueError(
                f"Cannot cancel order in status '{order.status}'"
            )

        order.cancellation_reason = reason
        await self.session.flush()

        cancelled = await self.repo.update_status(
            order_id=str(order_id),
            status=OrderStatus.cancelled.value,
            notes=reason,
            changed_by="system",
        )
        return cancelled

    # ── Analytics ──────────────────────────────────────────────────────────────

    async def get_order_statistics(self) -> OrderStatistics:
        """Fetch aggregated order statistics, scoped to tenant when set."""
        raw = await self.repo.get_statistics(tenant_id=self.tenant_id)
        return OrderStatistics(
            total_orders=raw["total_orders"],
            orders_by_status=raw["orders_by_status"],
            revenue_today=Decimal(str(raw["revenue_today"])),
            revenue_month=Decimal(str(raw["revenue_month"])),
            avg_delivery_time_hours=None,
        )

    async def list_orders(self, **filters) -> PaginatedResponse[OrderSummary]:
        """Return a paginated list of order summaries."""
        page: int = int(filters.pop("page", 1))
        limit: int = int(filters.pop("limit", 20))

        orders, total = await self.repo.list_orders(
            page=page, limit=limit, tenant_id=self.tenant_id, **filters
        )
        summaries = [OrderSummary.from_order(o) for o in orders]
        return PaginatedResponse.build(items=summaries, total=total, page=page, limit=limit)

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _generate_order_number(self) -> str:
        """Generate a unique order number in ECO-YYYY-NNNNNN format."""
        year = datetime.now(timezone.utc).year
        while True:
            suffix = "".join(random.choices(string.digits, k=6))
            candidate = f"ECO-{year}-{suffix}"
            existing = await self.repo.get_by_order_number(candidate)
            if existing is None:
                return candidate

    def _calculate_estimated_delivery(self) -> datetime:
        """Return estimated delivery date = today + 3 business days."""
        current = datetime.now(timezone.utc)
        business_days_added = 0
        while business_days_added < _DELIVERY_BUSINESS_DAYS:
            current += timedelta(days=1)
            if current.weekday() not in _WEEKENDS:
                business_days_added += 1
        # Set to end of business day (18:00 UTC)
        return current.replace(hour=18, minute=0, second=0, microsecond=0)

    def _format_for_voice(self, order: Order) -> str:
        """Format order details as natural Spanish for TTS."""
        status_text = STATUS_TEXT_MAP.get(order.status, order.status)
        lines: List[str] = [
            f"Tu pedido {order.order_number} está actualmente {status_text.lower()}."
        ]

        # Add date context
        if order.status == OrderStatus.delivered.value and order.actual_delivery:
            date_str = order.actual_delivery.strftime("%d de %B")
            lines.append(f"Fue entregado el {date_str}.")
        elif order.status in (
            OrderStatus.shipped.value,
            OrderStatus.in_transit.value,
            OrderStatus.out_for_delivery.value,
        ):
            if order.shipments:
                s = order.shipments[0]
                if s.carrier:
                    lines.append(f"Transportadora: {s.carrier}.")
                if s.tracking_number:
                    lines.append(f"Número de guía: {s.tracking_number}.")
                if s.current_location:
                    lines.append(f"Última ubicación conocida: {s.current_location}.")
            if order.estimated_delivery:
                date_str = order.estimated_delivery.strftime("%d de %B")
                lines.append(f"Entrega estimada el {date_str}.")
        elif order.status == OrderStatus.cancelled.value:
            if order.cancellation_reason:
                lines.append(f"Motivo de cancelación: {order.cancellation_reason}.")
        elif order.status in (OrderStatus.pending.value, OrderStatus.confirmed.value):
            if order.estimated_delivery:
                date_str = order.estimated_delivery.strftime("%d de %B")
                lines.append(f"Entrega estimada el {date_str}.")

        # Total amount
        lines.append(
            f"Total del pedido: {order.currency} {order.total_amount:,.0f}."
        )

        return " ".join(lines)
