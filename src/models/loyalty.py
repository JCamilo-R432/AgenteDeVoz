from __future__ import annotations
"""
Loyalty / Fidelidad — modelos SQLAlchemy.
Tiers: Bronze (0-999), Silver (1000-4999), Gold (5000-9999), Platinum (10000+).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _new_id() -> str:
    return str(uuid.uuid4())


class LoyaltyAccount(Base):
    __tablename__ = "loyalty_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), unique=True, nullable=False
    )
    total_points_earned: Mapped[int] = mapped_column(Integer, default=0)
    available_points: Mapped[int] = mapped_column(Integer, default=0)
    redeemed_points: Mapped[int] = mapped_column(Integer, default=0)
    tier: Mapped[str] = mapped_column(String(20), default="bronze")
    referral_code: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)
    referred_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    birthday_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.utcnow().isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.utcnow().isoformat()
    )

    # Relationships
    transactions: Mapped[List["LoyaltyTransaction"]] = relationship(
        "LoyaltyTransaction", back_populates="account", lazy="select"
    )

    @property
    def tier_multiplier(self) -> float:
        return {"bronze": 1.0, "silver": 1.2, "gold": 1.5, "platinum": 2.0}.get(
            self.tier, 1.0
        )

    @property
    def points_to_next_tier(self) -> Optional[int]:
        thresholds = {"bronze": 1000, "silver": 5000, "gold": 10000, "platinum": None}
        nxt = thresholds.get(self.tier)
        if nxt is None:
            return None
        return max(0, nxt - self.total_points_earned)


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("loyalty_accounts.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # earn|redeem|expire|bonus
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    order_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.utcnow().isoformat()
    )

    account: Mapped["LoyaltyAccount"] = relationship("LoyaltyAccount", back_populates="transactions")


class LoyaltyReward(Base):
    """Catálogo de recompensas canjeables con puntos."""
    __tablename__ = "loyalty_rewards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    points_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_type: Mapped[str] = mapped_column(String(50), nullable=False)  # discount|free_shipping|product|experience
    discount_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    min_tier: Mapped[str] = mapped_column(String(20), default="bronze")
    stock: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    valid_until: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
