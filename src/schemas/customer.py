from __future__ import annotations
"""
Pydantic v2 schemas for Customer-related API request/response models.
"""


from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict, EmailStr

from schemas.order import OrderSummary


class CustomerCreate(BaseModel):
    email: Optional[str] = Field(None, description="Optional customer email")
    phone: str = Field(..., min_length=7, max_length=20, description="Customer phone number")
    full_name: str = Field(..., min_length=2, max_length=255, description="Customer full name")
    metadata_json: Optional[dict] = Field(None, description="Additional metadata")

    model_config = ConfigDict(from_attributes=True)


class CustomerResponse(BaseModel):
    id: str
    phone: str
    full_name: str
    email: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CustomerOrdersResponse(BaseModel):
    customer: CustomerResponse
    orders: List[OrderSummary]
    total_orders: int

    model_config = ConfigDict(from_attributes=True)
