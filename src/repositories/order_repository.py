from __future__ import annotations
from typing import Dict, List, Any
"""
Async repository for Order-related database operations.
Uses SQLAlchemy 2.0 select() style exclusively.
"""


import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.order import Order, OrderItem, OrderStatusHistory
from models.customer import Customer
from models.shipment import Shipment

logger = logging.getLogger(__name__)


class OrderRepository:
    """Data access layer for orders."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Read ───────────────────────────────────────────────────────────────────

    async def get_by_id(
        self, order_id: str, tenant_id: Optional[str] = None
    ) -> Optional[Order]:
        """Retrieve an order by its UUID, scoped to tenant when provided."""
        filters = [Order.id == str(order_id)]
        if tenant_id:
            filters.append(Order.tenant_id == tenant_id)

        stmt = (
            select(Order)
            .where(and_(*filters))
            .options(
                selectinload(Order.items),
                selectinload(Order.shipments),
                selectinload(Order.status_history),
                selectinload(Order.customer),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_order_number(
        self, order_number: str, tenant_id: Optional[str] = None
    ) -> Optional[Order]:
        """Retrieve a fully-loaded order by order number, scoped to tenant."""
        filters = [Order.order_number == order_number.upper()]
        if tenant_id:
            filters.append(Order.tenant_id == tenant_id)

        stmt = (
            select(Order)
            .where(and_(*filters))
            .options(
                selectinload(Order.items),
                selectinload(Order.shipments),
                selectinload(Order.status_history),
                selectinload(Order.customer),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_tracking_number(
        self, tracking_number: str, tenant_id: Optional[str] = None
    ) -> Optional[Order]:
        """Find an order by shipment tracking number, scoped to tenant."""
        filters = [Shipment.tracking_number == tracking_number]
        if tenant_id:
            filters.append(Order.tenant_id == tenant_id)

        stmt = (
            select(Order)
            .join(Shipment, Shipment.order_id == Order.id)
            .where(and_(*filters))
            .options(
                selectinload(Order.items),
                selectinload(Order.shipments),
                selectinload(Order.status_history),
                selectinload(Order.customer),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_customer_phone(
        self, phone: str, limit: int = 5, tenant_id: Optional[str] = None
    ) -> List[Order]:
        """Get recent orders for a customer identified by phone, scoped to tenant."""
        filters = [Customer.phone == phone]
        if tenant_id:
            filters.append(Order.tenant_id == tenant_id)

        stmt = (
            select(Order)
            .join(Customer, Customer.id == Order.customer_id)
            .where(and_(*filters))
            .order_by(Order.created_at.desc())
            .limit(limit)
            .options(
                selectinload(Order.items),
                selectinload(Order.shipments),
                selectinload(Order.status_history),
                selectinload(Order.customer),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_customer_email(
        self, email: str, limit: int = 5, tenant_id: Optional[str] = None
    ) -> List[Order]:
        """Get recent orders for a customer identified by email, scoped to tenant."""
        filters = [Customer.email == email.lower()]
        if tenant_id:
            filters.append(Order.tenant_id == tenant_id)

        stmt = (
            select(Order)
            .join(Customer, Customer.id == Order.customer_id)
            .where(and_(*filters))
            .order_by(Order.created_at.desc())
            .limit(limit)
            .options(
                selectinload(Order.items),
                selectinload(Order.shipments),
                selectinload(Order.status_history),
                selectinload(Order.customer),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_orders(
        self,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        limit: int = 20,
        tenant_id: Optional[str] = None,
    ) -> Tuple[List[Order], int]:
        """List orders with optional filters, returns (items, total_count).
        When tenant_id is provided, results are scoped to that tenant.
        """
        filters = []
        if tenant_id:
            filters.append(Order.tenant_id == tenant_id)
        if status:
            filters.append(Order.status == status)
        if date_from:
            filters.append(Order.created_at >= date_from)
        if date_to:
            filters.append(Order.created_at <= date_to)

        # Count query
        count_stmt = select(func.count(Order.id))
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        # Data query
        offset = (page - 1) * limit
        data_stmt = (
            select(Order)
            .order_by(Order.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if filters:
            data_stmt = data_stmt.where(and_(*filters))
        data_result = await self.session.execute(data_stmt)
        orders = list(data_result.scalars().all())

        return orders, total

    # ── Write ──────────────────────────────────────────────────────────────────

    async def create(self, **kwargs) -> Order:
        """Create a new Order (and its items if provided in kwargs)."""
        items_data: List[dict] = kwargs.pop("items", [])
        order = Order(**kwargs)
        self.session.add(order)
        await self.session.flush()  # Assigns PK without committing

        for item_data in items_data:
            item = OrderItem(order_id=order.id, **item_data)
            self.session.add(item)

        await self.session.flush()
        await self.session.refresh(order)
        return order

    async def update_status(
        self,
        order_id: str,
        status: str,
        notes: Optional[str],
        changed_by: str = "system",
    ) -> Order:
        """Update order status and append to status history."""
        order = await self.get_by_id(order_id)
        if order is None:
            raise ValueError(f"Order {order_id} not found")

        previous_status = order.status
        order.status = status

        # Set timestamp fields based on new status
        now = datetime.now(timezone.utc)
        if status == "confirmed":
            order.confirmed_at = now
        elif status == "shipped":
            order.shipped_at = now
        elif status == "delivered":
            order.delivered_at = now
            order.actual_delivery = now

        # Write history record
        history_entry = OrderStatusHistory(
            order_id=order.id,
            previous_status=previous_status,
            new_status=status,
            changed_at=now,
            changed_by=changed_by,
            notes=notes,
        )
        self.session.add(history_entry)
        await self.session.flush()
        await self.session.refresh(order)
        return order

    # ── Statistics ─────────────────────────────────────────────────────────────

    async def get_statistics(self, tenant_id: Optional[str] = None) -> dict:
        """Return aggregated order statistics."""
        from decimal import Decimal as D
        from sqlalchemy import cast, Date

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Build base tenant filter
        tenant_filter = [Order.tenant_id == tenant_id] if tenant_id else []

        # Total count
        count_stmt = select(func.count(Order.id))
        if tenant_filter:
            count_stmt = count_stmt.where(and_(*tenant_filter))
        total_result = await self.session.execute(count_stmt)
        total_orders: int = total_result.scalar_one() or 0

        # Count by status
        status_stmt = select(Order.status, func.count(Order.id)).group_by(Order.status)
        if tenant_filter:
            status_stmt = status_stmt.where(and_(*tenant_filter))
        status_result = await self.session.execute(status_stmt)
        orders_by_status: Dict[str, int] = {
            row[0]: row[1] for row in status_result.all()
        }

        # Revenue today
        today_filters = tenant_filter + [
            Order.created_at >= today_start,
            Order.status.notin_(["cancelled", "refunded"]),
        ]
        today_revenue_stmt = select(func.sum(Order.total_amount)).where(
            and_(*today_filters)
        )
        today_rev_result = await self.session.execute(today_revenue_stmt)
        revenue_today: D = today_rev_result.scalar_one() or D("0.00")

        # Revenue this month
        month_filters = tenant_filter + [
            Order.created_at >= month_start,
            Order.status.notin_(["cancelled", "refunded"]),
        ]
        month_revenue_stmt = select(func.sum(Order.total_amount)).where(
            and_(*month_filters)
        )
        month_rev_result = await self.session.execute(month_revenue_stmt)
        revenue_month: D = month_rev_result.scalar_one() or D("0.00")

        return {
            "total_orders": total_orders,
            "orders_by_status": orders_by_status,
            "revenue_today": revenue_today,
            "revenue_month": revenue_month,
        }
