"""Modelos de Cupones y uso de cupones."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import relationship

from database import Base


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    type = Column(String(50), nullable=False)  # percentage / fixed_amount / free_shipping
    value = Column(Numeric(10, 2), nullable=False)
    min_purchase_amount = Column(Numeric(10, 2), nullable=True)
    max_discount_amount = Column(Numeric(10, 2), nullable=True)
    valid_from = Column(String(30), nullable=False)
    valid_until = Column(String(30), nullable=True)
    usage_limit = Column(Integer, nullable=True)
    usage_count = Column(Integer, default=0)
    usage_limit_per_customer = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    applicable_categories = Column(JSON, nullable=True)
    metadata_json = Column("metadata", JSON, nullable=True)

    usages = relationship("CouponUsage", back_populates="coupon")


class CouponUsage(Base):
    __tablename__ = "coupon_usages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    coupon_id = Column(String(36), ForeignKey("coupons.id"), nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=False)
    discount_applied = Column(Numeric(10, 2), nullable=False)
    used_at = Column(
        String(30), default=lambda: datetime.now(timezone.utc).isoformat()
    )

    coupon = relationship("Coupon", back_populates="usages")
