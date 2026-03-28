"""Modelos de Reseñas y Encuestas de Satisfacción."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    product_id = Column(String(36), nullable=True, index=True)
    rating = Column(Integer, nullable=False)       # 1-5
    delivery_rating = Column(Integer, nullable=True)
    title = Column(String(255), nullable=True)
    body = Column(Text, nullable=True)
    sentiment = Column(String(20), nullable=True)  # positive/neutral/negative
    nps_score = Column(Integer, nullable=True)     # 0-10
    is_verified_purchase = Column(Boolean, default=True)
    is_published = Column(Boolean, default=True)
    admin_response = Column(Text, nullable=True)
    created_at = Column(
        String(30), default=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata_json = Column("metadata", JSON, nullable=True)


class SatisfactionSurvey(Base):
    __tablename__ = "satisfaction_surveys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=False)
    sent_at = Column(String(30), nullable=True)
    completed_at = Column(String(30), nullable=True)
    nps_score = Column(Integer, nullable=True)    # 0-10
    csat_score = Column(Integer, nullable=True)   # 1-5
    comments = Column(Text, nullable=True)
    channel = Column(String(20), default="email")
