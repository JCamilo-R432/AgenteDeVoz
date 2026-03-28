from __future__ import annotations
"""
Order management API endpoints.
Public endpoints allow order lookup by number, phone, email, and tracking number.
Admin endpoints (JWT required) allow creating/updating orders and listing them.
"""


import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_admin, get_order_service, get_tenant_id
from database import get_db
from schemas.order import (
    CreateOrderRequest,
    OrderDetailResponse,
    UpdateOrderStatusRequest,
)
from schemas.customer import CustomerOrdersResponse, CustomerResponse
from schemas.responses import PaginatedResponse, OrderStatistics
from services.order_service import OrderService

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Public endpoints ───────────────────────────────────────────────────────────

@router.get(
    "/{order_number}",
    response_model=OrderDetailResponse,
    summary="Get order by order number",
    tags=["orders"],
)
async def get_order_by_number(
    order_number: str,
    include_items: bool = Query(default=True),
    include_shipment: bool = Query(default=True),
    service: OrderService = Depends(get_order_service),
) -> OrderDetailResponse:
    """
    Retrieve full order detail by order number (e.g. ECO-2026-123456).
    No authentication required — suitable for customer self-service.
    """
    order = await service.get_by_order_number(order_number)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_number}' not found",
        )
    return OrderDetailResponse.from_order(
        order,
        include_items=include_items,
        include_shipment=include_shipment,
    )


@router.get(
    "/customer/phone/{phone}",
    response_model=CustomerOrdersResponse,
    summary="Get orders by customer phone",
    tags=["orders"],
)
async def get_orders_by_phone(
    phone: str,
    service: OrderService = Depends(get_order_service),
    db: AsyncSession = Depends(get_db),
    tenant_id: Optional[str] = Depends(get_tenant_id),
) -> CustomerOrdersResponse:
    """
    List recent orders for a customer identified by phone number.
    Results are scoped to the tenant identified by X-API-Key.
    """
    from sqlalchemy import select, and_
    from models.customer import Customer
    from schemas.order import OrderSummary

    orders = await service.get_by_customer_phone(phone)

    # Fetch customer scoped to tenant when available
    cust_filters = [Customer.phone == phone]
    if tenant_id:
        cust_filters.append(Customer.tenant_id == tenant_id)
    result = await db.execute(select(Customer).where(and_(*cust_filters)))
    customer = result.scalar_one_or_none()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No customer found with phone '{phone}'",
        )

    summaries = [OrderSummary.from_order(o) for o in orders]
    return CustomerOrdersResponse(
        customer=CustomerResponse(
            id=str(customer.id),
            phone=customer.phone,
            full_name=customer.full_name,
            email=customer.email,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        ),
        orders=summaries,
        total_orders=len(summaries),
    )


@router.get(
    "/customer/email/{email}",
    response_model=CustomerOrdersResponse,
    summary="Get orders by customer email",
    tags=["orders"],
)
async def get_orders_by_email(
    email: str,
    service: OrderService = Depends(get_order_service),
    db: AsyncSession = Depends(get_db),
    tenant_id: Optional[str] = Depends(get_tenant_id),
) -> CustomerOrdersResponse:
    """List recent orders for a customer identified by email, scoped to tenant."""
    from sqlalchemy import select, and_
    from models.customer import Customer
    from schemas.order import OrderSummary

    orders = await service.get_by_customer_email(email)

    cust_filters = [Customer.email == email.lower()]
    if tenant_id:
        cust_filters.append(Customer.tenant_id == tenant_id)
    result = await db.execute(select(Customer).where(and_(*cust_filters)))
    customer = result.scalar_one_or_none()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No customer found with email '{email}'",
        )

    summaries = [OrderSummary.from_order(o) for o in orders]
    return CustomerOrdersResponse(
        customer=CustomerResponse(
            id=str(customer.id),
            phone=customer.phone,
            full_name=customer.full_name,
            email=customer.email,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        ),
        orders=summaries,
        total_orders=len(summaries),
    )


@router.get(
    "/tracking/{tracking_number}",
    response_model=OrderDetailResponse,
    summary="Get order by shipment tracking number",
    tags=["orders"],
)
async def get_by_tracking(
    tracking_number: str,
    service: OrderService = Depends(get_order_service),
) -> OrderDetailResponse:
    """Find an order using the shipment tracking number."""
    order = await service.get_by_tracking_number(tracking_number)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No order found for tracking number '{tracking_number}'",
        )
    return OrderDetailResponse.from_order(order)


# ── Admin endpoints ────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=OrderDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order (admin)",
    tags=["orders"],
)
async def create_order(
    payload: CreateOrderRequest,
    service: OrderService = Depends(get_order_service),
    _admin: dict = Depends(get_current_admin),
) -> OrderDetailResponse:
    """Create a new order. Requires admin JWT."""
    try:
        order = await service.create_order(payload)
        return OrderDetailResponse.from_order(order)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )


@router.put(
    "/{order_id}/status",
    response_model=OrderDetailResponse,
    summary="Update order status (admin)",
    tags=["orders"],
)
async def update_order_status(
    order_id: str,
    payload: UpdateOrderStatusRequest,
    service: OrderService = Depends(get_order_service),
    admin: dict = Depends(get_current_admin),
) -> OrderDetailResponse:
    """Update the status of an existing order. Requires admin JWT."""
    try:
        changed_by = admin.get("sub", payload.changed_by)
        order = await service.update_status(
            order_id=order_id,
            status=payload.status.value,
            notes=payload.notes,
            changed_by=changed_by,
        )
        return OrderDetailResponse.from_order(order)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "",
    response_model=PaginatedResponse,
    summary="List orders with pagination (admin)",
    tags=["orders"],
)
async def list_orders(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    service: OrderService = Depends(get_order_service),
    _admin: dict = Depends(get_current_admin),
) -> PaginatedResponse:
    """Return a paginated and filterable list of order summaries. Requires admin JWT."""
    filters: dict = {"page": page, "limit": limit}
    if status_filter:
        filters["status"] = status_filter

    return await service.list_orders(**filters)
