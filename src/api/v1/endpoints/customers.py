from __future__ import annotations
"""
Customer management API endpoints.
"""


import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_admin, get_db
from models.customer import Customer
from schemas.customer import CustomerCreate, CustomerResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer by ID",
    tags=["customers"],
)
async def get_customer(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
) -> CustomerResponse:
    """Retrieve a customer by their UUID. Returns 404 if not found."""
    result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found",
        )
    return CustomerResponse(
        id=str(customer.id),
        phone=customer.phone,
        full_name=customer.full_name,
        email=customer.email,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer (admin)",
    tags=["customers"],
)
async def create_customer(
    payload: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(get_current_admin),
) -> CustomerResponse:
    """Create a new customer record. Requires admin JWT."""
    # Check uniqueness of phone
    existing_phone = await db.execute(
        select(Customer).where(Customer.phone == payload.phone)
    )
    if existing_phone.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Customer with phone '{payload.phone}' already exists",
        )

    # Check uniqueness of email if provided
    if payload.email:
        existing_email = await db.execute(
            select(Customer).where(Customer.email == payload.email.lower())
        )
        if existing_email.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Customer with email '{payload.email}' already exists",
            )

    now = datetime.now(timezone.utc)
    customer = Customer(
        id=str(uuid.uuid4()),
        email=payload.email.lower() if payload.email else None,
        phone=payload.phone,
        full_name=payload.full_name,
        created_at=now,
        metadata_json=payload.metadata_json,
    )
    db.add(customer)
    await db.flush()
    await db.refresh(customer)

    logger.info(f"Customer created: {customer.id} — {customer.full_name}")
    return CustomerResponse(
        id=str(customer.id),
        phone=customer.phone,
        full_name=customer.full_name,
        email=customer.email,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )
