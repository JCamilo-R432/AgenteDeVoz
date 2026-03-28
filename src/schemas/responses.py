from __future__ import annotations
"""
Generic and utility Pydantic v2 response schemas.
"""


import math
from decimal import Decimal
from typing import Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated list response."""

    items: List[T]
    total: int
    page: int
    limit: int
    pages: int

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def build(cls, items: List[T], total: int, page: int, limit: int) -> "PaginatedResponse[T]":
        pages = math.ceil(total / limit) if limit > 0 else 0
        return cls(items=items, total=total, page=page, limit=limit, pages=pages)


class ErrorResponse(BaseModel):
    detail: str
    code: str

    model_config = ConfigDict(from_attributes=True)


class OrderStatistics(BaseModel):
    total_orders: int
    orders_by_status: Dict[str, int]
    revenue_today: Decimal
    revenue_month: Decimal
    avg_delivery_time_hours: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)
