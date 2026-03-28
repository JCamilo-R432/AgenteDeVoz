from __future__ import annotations
"""
subscription_model.py — Pydantic schemas for subscription API requests/responses.
"""


from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class SubscriptionCreate(BaseModel):
    plan_id           : str
    billing_cycle     : str = "monthly"    # "monthly" | "yearly"
    payment_method_id : Optional[str] = None  # Stripe payment method ID


class SubscriptionResponse(BaseModel):
    id             : str
    plan_id        : str
    billing_cycle  : str
    status         : str
    price          : str
    currency       : str = "USD"
    current_period_end : Optional[datetime] = None
    cancel_at_period_end: bool = False
    trial_end      : Optional[datetime] = None
    created_at     : datetime

    class Config:
        from_attributes = True


class SubscriptionUpgrade(BaseModel):
    new_plan_id    : str
    billing_cycle  : str = "monthly"
    prorate        : bool = True


class BillingPortalResponse(BaseModel):
    url: str
    expires_at: datetime
