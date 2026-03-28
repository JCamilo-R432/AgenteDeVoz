"""Modelo de pago asociado a pedidos."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import relationship

from database import Base


class OrderPayment(Base):
    __tablename__ = "order_payments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    provider_payment_id = Column(String(255), nullable=True, unique=True, index=True)
    provider_payment_url = Column(Text, nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="COP")
    status = Column(String(50), default="pending")  # pending/processing/paid/failed/refunded
    payment_method = Column(String(50), nullable=True)
    paid_at = Column(String(30), nullable=True)
    refunded_at = Column(String(30), nullable=True)
    refund_amount = Column(Numeric(10, 2), nullable=True)
    refund_reason = Column(Text, nullable=True)
    failure_reason = Column(Text, nullable=True)
    metadata_json = Column("metadata", JSON, nullable=True)
    created_at = Column(
        String(30), default=lambda: datetime.now(timezone.utc).isoformat()
    )

    order = relationship("Order", back_populates="payments")
